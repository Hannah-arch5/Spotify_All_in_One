#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from difflib import SequenceMatcher
import unicodedata
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP_RE = re.compile(r"\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b")
SECTION_RE = re.compile(r"^####\s+情报\s*(\d+)[：:](.*)$", re.MULTILINE)
TITLE_RE = re.compile(r"原始标题[：:]\s*(.+)")
LINK_RE = re.compile(r"原始链接[：:]\s*(.+)")
TRANSCRIPT_SOURCE_RE = re.compile(r"Transcript\s*来源[：:]\s*(.+)", re.IGNORECASE)
REQUIRED_PARTS = [
    "第一部分",
    "第二部分",
    "第三部分",
    "第四部分",
    "第五部分",
]
QUOTE_CANDIDATE_RE = re.compile(r"[\"“](.{12,240}?)[\"”]")
KEY_QUOTE_BLOCK_RE = re.compile(
    r"关键金句\s*/\s*结论[：:](.*?)(?:\n-\s*证据锚点[：:]|\n证据锚点[：:]|\Z)",
    re.DOTALL,
)


@dataclass
class Finding:
    severity: str
    message: str


def _latest_manifest() -> Path:
    candidates = sorted((ROOT / "data" / "gemini_inputs").glob("*/episode-manifest.json"))
    if not candidates:
        candidates = sorted((ROOT / "data" / "runs").glob("*-manifest.json"))
    if not candidates:
        raise SystemExit("No manifest found.")
    return candidates[-1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[\u2018\u2019\u201c\u201d]", "'", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_sections(report: str) -> list[dict[str, Any]]:
    matches = list(SECTION_RE.finditer(report))
    sections = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(report)
        body = report[start:end]
        sections.append(
            {
                "number": int(match.group(1)),
                "heading": match.group(2).strip(),
                "body": body,
                "start_offset": start,
            }
        )
    return sections


def _extract_field(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip().strip("`")


def _episode_transcript_text(evidence: dict[str, Any] | None, index: int) -> str:
    if not evidence:
        return ""
    for episode in evidence.get("episodes", []):
        if episode.get("index") != index:
            continue
        transcript = episode.get("transcript") or {}
        return str(transcript.get("plain_text") or "")
    return ""


def _quote_support_findings(section: dict[str, Any], transcript_text: str) -> list[Finding]:
    findings: list[Finding] = []
    if not transcript_text:
        return findings
    normalized_transcript = _normalize(transcript_text)
    block_match = KEY_QUOTE_BLOCK_RE.search(section["body"])
    if not block_match:
        return findings
    quote_block = block_match.group(1)
    for raw_quote in QUOTE_CANDIDATE_RE.findall(quote_block):
        quote = raw_quote.strip()
        # Only police likely direct English transcript quotes. Chinese translations and short labels are too noisy.
        ascii_words = re.findall(r"[A-Za-z][A-Za-z']+", quote)
        if len(ascii_words) < 4:
            continue
        normalized_quote = _normalize(quote)
        if not normalized_quote:
            continue
        if normalized_quote in normalized_transcript:
            continue

        quote_words = normalized_quote.split()
        windows = (
            " ".join(normalized_transcript.split()[start : start + len(quote_words) + 12])
            for start in range(0, max(len(normalized_transcript.split()) - len(quote_words), 0), 20)
        )
        best_ratio = max((SequenceMatcher(None, normalized_quote, window).ratio() for window in windows), default=0.0)
        if best_ratio < 0.82:
            findings.append(
                Finding(
                    "warning",
                    f"情报 {section['number']} 的引号内容未在 transcript 中直接找到：{quote[:80]}",
                )
            )
    return findings


def check(report_path: Path, manifest_path: Path, evidence_path: Path | None = None) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    evidence = _read_json(evidence_path) if evidence_path else None
    report = report_path.read_text(encoding="utf-8")
    expected_episodes = manifest["episodes"] if "episodes" in manifest else manifest["new_episodes"]
    sections = _extract_sections(report)

    findings: list[Finding] = []
    missing_parts = [part for part in REQUIRED_PARTS if not re.search(rf"^##\s+{part}", report, re.MULTILINE)]
    for part in missing_parts:
        findings.append(Finding("error", f"研报缺少必要结构：{part}。"))

    expected_count = len(expected_episodes)
    actual_count = len(sections)
    if actual_count != expected_count:
        findings.append(Finding("error", f"Episode 数量不一致：Manifest {expected_count} 篇，研报 {actual_count} 篇。"))

    for expected_index, episode in enumerate(expected_episodes, 1):
        title = episode.get("episode_title") or episode.get("title")
        section = sections[expected_index - 1] if expected_index - 1 < len(sections) else None
        if not section:
            findings.append(Finding("error", f"缺少情报 {expected_index}：{title}"))
            continue

        if section["number"] != expected_index:
            findings.append(
                Finding("error", f"情报编号顺序错误：第 {expected_index} 个 section 写成了 情报 {section['number']}。")
            )

        report_title = _extract_field(TITLE_RE, section["body"])
        if _normalize(report_title) != _normalize(title):
            findings.append(
                Finding(
                    "error",
                    f"情报 {expected_index} 原始标题不匹配：期望 `{title}`，实际 `{report_title or '缺失'}`。",
                )
            )

        report_link = _extract_field(LINK_RE, section["body"])
        allowed_links = {
            str(episode.get("spotify_episode_url") or ""),
            str(episode.get("rss_episode_url") or ""),
            str(episode.get("episode_url") or ""),
            str(episode.get("audio_url") or ""),
        }
        allowed_links.discard("")
        if not report_link:
            findings.append(Finding("error", f"情报 {expected_index} 缺少原始链接。"))
        elif allowed_links and not any(link in report_link for link in allowed_links):
            findings.append(Finding("error", f"情报 {expected_index} 原始链接不在 Manifest 允许链接中：{report_link}"))

        if not _extract_field(TRANSCRIPT_SOURCE_RE, section["body"]):
            findings.append(Finding("error", f"情报 {expected_index} 缺少 Transcript 来源。"))

        timestamps = TIMESTAMP_RE.findall(section["body"])
        if len(timestamps) < 3:
            findings.append(Finding("warning", f"情报 {expected_index} 时间戳证据少于 3 个：{len(timestamps)} 个。"))

        transcript_text = _episode_transcript_text(evidence, expected_index)
        findings.extend(_quote_support_findings(section, transcript_text))

    extra_sections = sections[expected_count:]
    for section in extra_sections:
        findings.append(Finding("error", f"研报包含 Manifest 之外的额外 section：情报 {section['number']}。"))

    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = sum(1 for finding in findings if finding.severity == "warning")
    if errors:
        conclusion = "不通过"
    elif warnings:
        conclusion = "需修改"
    else:
        conclusion = "通过"

    return {
        "created_at": datetime.now().astimezone().isoformat(),
        "report_path": str(report_path),
        "manifest_path": str(manifest_path),
        "evidence_path": str(evidence_path) if evidence_path else None,
        "conclusion": conclusion,
        "episode_count": {"manifest": expected_count, "report": actual_count},
        "errors": errors,
        "warnings": warnings,
        "findings": [finding.__dict__ for finding in findings],
    }


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Gemini Report Review",
        "",
        f"- 复查结论：{result['conclusion']}",
        f"- Episode 数量：Manifest {result['episode_count']['manifest']} 篇，研报 {result['episode_count']['report']} 篇",
        f"- Errors：{result['errors']}",
        f"- Warnings：{result['warnings']}",
        "",
        "## Findings",
        "",
    ]
    if result["findings"]:
        for index, finding in enumerate(result["findings"], 1):
            lines.append(f"{index}. [{finding['severity']}] {finding['message']}")
    else:
        lines.append("No structural issues found.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a Gemini podcast report against the manifest and evidence.")
    parser.add_argument("report", type=Path, help="Gemini report Markdown file.")
    parser.add_argument("--manifest", type=Path, help="Episode manifest JSON. Defaults to the latest package manifest.")
    parser.add_argument("--evidence", type=Path, help="Full transcript evidence JSON.")
    parser.add_argument("--output-json", type=Path, help="Review JSON output path.")
    parser.add_argument("--output-md", type=Path, help="Review Markdown output path.")
    args = parser.parse_args()

    manifest_path = args.manifest or _latest_manifest()
    result = check(args.report, manifest_path, args.evidence)
    run_id = _read_json(manifest_path).get("run_id", "unknown-run")
    output_json = args.output_json or ROOT / "data" / "runs" / f"{run_id}-gemini-review.json"
    output_md = args.output_md or ROOT / "reports" / "markdown" / f"{run_id}-gemini-review.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(output_md, result)

    print(output_json)
    print(output_md)
    print(result["conclusion"])


if __name__ == "__main__":
    main()
