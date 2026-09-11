#!/usr/bin/env python3
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EPISODE_HEADING_RE = re.compile(r"^####\s+情报\s+(\d+)[：:]")
BRACKET_TIMESTAMP_RE = re.compile(r"^\s*-\s*\[([0-9:]+)\]\s*(.*)$")
PLAIN_TIMESTAMP_RE = re.compile(
    r"^\s*-\s*([0-9:]+)(?:\s*-\s*([0-9:]+))?[：:]\s*(.*)$"
)
TRAILING_CHINESE_NOTE_RE = re.compile(r"\s*[（(][^()]*[\u4e00-\u9fff][^()]*[）)]\s*$")
LEADING_SPEAKER_RE = re.compile(r"^(?:Speaker\s*\d+|[^:]{2,80}):\s*", re.IGNORECASE)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z']+")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_english(value: str) -> str:
    value = value.replace("“", '"').replace("”", '"').replace("’", "'")
    value = re.sub(r"[^A-Za-z0-9']+", " ", value).lower()
    return re.sub(r"\s+", " ", value).strip()


def is_english_anchor(value: str) -> bool:
    return len(WORD_RE.findall(value)) >= 4


def parse_seconds(value: str, duration: float) -> float:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])
    if len(parts) == 3:
        seconds = float(parts[0] * 3600 + parts[1] * 60 + parts[2])
        if seconds > duration + 60 and parts[2] == 0:
            return float(parts[0] * 60 + parts[1])
        return seconds
    return float(parts[0])


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def strip_anchor_text(value: str) -> str:
    value = TRAILING_CHINESE_NOTE_RE.sub("", value).strip()
    value = LEADING_SPEAKER_RE.sub("", value).strip()
    return value.strip(' "“”')


def nearest_segment_index(segments: list[dict[str, Any]], seconds: float) -> int:
    return min(
        range(len(segments)),
        key=lambda index: abs(float(segments[index].get("start") or 0) - seconds),
    )


def window_text(segments: list[dict[str, Any]], start: int, count: int, field: str) -> str:
    values = []
    for segment in segments[start : start + count]:
        value = str(segment.get(field) or "").strip()
        if value:
            values.append(value)
    return " ".join(values)


def best_matching_window(
    segments: list[dict[str, Any]], anchor_text: str, timestamp_index: int,
    *,
    global_search: bool = False,
) -> tuple[int, int, float]:
    target = normalize_english(anchor_text)
    best = (timestamp_index, 1, 0.0)
    search_start = 0 if global_search else max(0, timestamp_index - 10)
    search_end = len(segments) if global_search else min(len(segments), timestamp_index + 11)
    for start in range(search_start, search_end):
        for count in range(1, min(12, len(segments) - start) + 1):
            candidate = normalize_english(window_text(segments, start, count, "text"))
            if not candidate:
                continue
            score = SequenceMatcher(None, target, candidate).ratio()
            if target in candidate or candidate in target:
                score = max(score, min(len(target), len(candidate)) / max(len(target), len(candidate)))
            if score > best[2]:
                best = (start, count, score)
    return best


def meaningful_window(
    segments: list[dict[str, Any]], start_seconds: float, end_seconds: float | None
) -> tuple[int, int]:
    start = nearest_segment_index(segments, start_seconds)
    if end_seconds is not None and end_seconds > start_seconds:
        end = start
        while end + 1 < len(segments) and float(segments[end + 1].get("start") or 0) <= end_seconds:
            end += 1
        return start, max(1, end - start + 1)

    count = 1
    while start + count < len(segments) and count < 5:
        text = window_text(segments, start, count, "text")
        if len(WORD_RE.findall(text)) >= 18 and re.search(r"[.!?]$", text):
            break
        count += 1
    return start, count


def build_episode_sources(evidence_path: Path, audit_path: Path) -> dict[int, tuple[dict[str, Any], dict[str, Any]]]:
    evidence = read_json(evidence_path)
    audit = read_json(audit_path)
    zh_paths = {
        int(item["index"]): Path(item["chinese_match"]["path"])
        for item in audit.get("episodes", [])
        if item.get("chinese_match", {}).get("path")
    }
    sources: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    for item in evidence.get("episodes", []):
        index = int(item.get("index") or 0)
        source_path = item.get("transcript", {}).get("path")
        if not index or not source_path or index not in zh_paths:
            continue
        original = read_json(Path(source_path))
        chinese = read_json(zh_paths[index])
        original_segments = original.get("segments") or []
        chinese_segments = chinese.get("segments") or []
        if len(original_segments) != len(chinese_segments):
            raise ValueError(
                f"Episode {index} segment mismatch: original={len(original_segments)} chinese={len(chinese_segments)}"
            )
        sources[index] = (original, chinese)
    return sources


def enrich(report: str, sources: dict[int, tuple[dict[str, Any], dict[str, Any]]]) -> tuple[str, dict[str, Any]]:
    lines = report.splitlines()
    output: list[str] = []
    episode_index = 0
    in_evidence = False
    translated = 0
    rebuilt = 0
    skipped_chinese = 0
    low_confidence: list[dict[str, Any]] = []
    skip_existing_translation = False

    for line in lines:
        if skip_existing_translation:
            skip_existing_translation = False
            stripped = line.strip()
            if stripped.startswith("*") and stripped.endswith("*"):
                continue
        heading = EPISODE_HEADING_RE.match(line)
        if heading:
            episode_index = int(heading.group(1))
            in_evidence = False
        if "证据锚点" in line and line.lstrip().startswith("-"):
            in_evidence = True
            output.append(line)
            continue
        if in_evidence and (line.startswith("#### ") or line.startswith("## ") or line.strip() == "---"):
            in_evidence = False
        if not in_evidence or not line.lstrip().startswith("-") or episode_index not in sources:
            output.append(line)
            continue

        bracket = BRACKET_TIMESTAMP_RE.match(line)
        plain = PLAIN_TIMESTAMP_RE.match(line)
        if not bracket and not plain:
            output.append(line)
            continue
        timestamp = bracket.group(1) if bracket else plain.group(1)
        end_timestamp = None if bracket else plain.group(2)
        raw_text = bracket.group(2) if bracket else plain.group(3)
        original, chinese = sources[episode_index]
        original_segments = original.get("segments") or []
        chinese_segments = chinese.get("segments") or []
        duration = max((float(item.get("end") or item.get("start") or 0) for item in original_segments), default=0)
        source_language = str(original.get("transcriptLanguage") or "").lower()
        source_is_chinese = "zh" in source_language
        if source_is_chinese:
            output.append(line)
            skipped_chinese += 1
            continue

        start_seconds = parse_seconds(timestamp, duration)
        end_seconds = parse_seconds(end_timestamp, duration) if end_timestamp else None
        timestamp_index = nearest_segment_index(original_segments, start_seconds)
        anchor_text = strip_anchor_text(raw_text)
        if is_english_anchor(anchor_text):
            start, count, score = best_matching_window(original_segments, anchor_text, timestamp_index)
            if score < 0.56:
                global_start, global_count, global_score = best_matching_window(
                    original_segments, anchor_text, timestamp_index, global_search=True
                )
                if global_score > score:
                    start, count, score = global_start, global_count, global_score
            if score < 0.56:
                start, count = meaningful_window(original_segments, start_seconds, end_seconds)
                low_confidence.append({"episode": episode_index, "timestamp": timestamp, "score": round(score, 3)})
        else:
            start, count = meaningful_window(original_segments, start_seconds, end_seconds)
            score = 1.0
            rebuilt += 1

        original_text = window_text(original_segments, start, count, "text")
        translation = window_text(chinese_segments, start, count, "translation")
        if not original_text or not translation:
            raise ValueError(f"Episode {episode_index} anchor {timestamp} could not be aligned")
        speaker = str(original_segments[start].get("speaker") or "").strip()
        speaker_prefix = f"{speaker}: " if speaker else ""
        actual_timestamp = format_timestamp(float(original_segments[start].get("start") or start_seconds))
        output.append(f"- [{actual_timestamp}] {speaker_prefix}{original_text}")
        output.append(f"    *{translation}*")
        skip_existing_translation = True
        translated += 1

    return "\n".join(output).rstrip() + "\n", {
        "translated_english_anchors": translated,
        "rebuilt_paraphrase_anchors": rebuilt,
        "skipped_chinese_anchors": skipped_chinese,
        "low_confidence_fallbacks": low_confidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Add aligned Chinese translations below English evidence anchors.")
    parser.add_argument("report", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--language-audit", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    sources = build_episode_sources(args.evidence, args.language_audit)
    updated, result = enrich(args.report.read_text(encoding="utf-8"), sources)
    result["changed"] = updated != args.report.read_text(encoding="utf-8")
    if args.write:
        args.report.write_text(updated, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
