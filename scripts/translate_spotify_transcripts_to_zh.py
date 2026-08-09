#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZH_DIR = ROOT / "data" / "transcripts" / "spotify_zh"
TRANSLATE_URLS = [
    "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=zh-CN&dt=t",
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean(value: str | None) -> str:
    return re.sub(r'[\\/:*?"<>|#%]', "_", str(value or "unknown")).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _target_path(source_data: dict[str, Any], chinese_dir: Path) -> Path:
    date = str(source_data.get("publishedDate") or "unknown")[:10]
    podcast = _clean(source_data.get("podcastName"))
    title = _clean(f"{source_data.get('episodeTitle') or 'unknown'}_zh")
    episode_id = _clean(source_data.get("spotifyEpisodeId"))
    return chinese_dir / f"{date} - {podcast} - {title} - {episode_id}.json"


def _is_complete_zh(path: Path, source_hash: str | None = None) -> bool:
    if not path.exists() or "_zh_incomplete" in path.stem.casefold():
        return False
    try:
        data = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    if source_hash and data.get("sourceTranscriptSha256") not in {None, source_hash}:
        return False
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        return False
    return not any(
        isinstance(segment, dict) and segment.get("text") and not segment.get("translation")
        for segment in segments
    )


def _payload_to_text(payload: Any) -> str:
    if isinstance(payload, list) and payload and isinstance(payload[0], str):
        return "".join(str(item) for item in payload)
    if (
        isinstance(payload, list)
        and payload
        and isinstance(payload[0], list)
        and payload[0]
        and isinstance(payload[0][0], str)
    ):
        return str(payload[0][0])
    translated = ""
    if payload and payload[0]:
        for item in payload[0]:
            if item and item[0]:
                translated += str(item[0])
    return translated


def _translate_text_block_with_curl(text: str, url: str, timeout: int) -> str:
    # curl's --max-time gives us a hard wall-clock cap; urllib can hang behind proxies.
    command = [
        "curl",
        "--max-time",
        str(timeout),
        "-sS",
        "-X",
        "POST",
        url,
        "--data-urlencode",
        f"q={text}",
    ]
    env = os.environ.copy()
    env.setdefault("NO_PROXY", "localhost,127.0.0.1")
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout + 5,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"curl exited {result.returncode}")
    return _payload_to_text(json.loads(result.stdout))


def _translate_text_block_with_urllib(text: str, url: str, timeout: int) -> str:
    body = urllib.parse.urlencode({"q": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return _payload_to_text(payload)


def _translate_text_block(text: str, timeout: int, transport: str) -> str:
    last_error: Exception | None = None
    for url in TRANSLATE_URLS:
        try:
            if transport == "curl":
                return _translate_text_block_with_curl(text, url, timeout)
            return _translate_text_block_with_urllib(text, url, timeout)
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            subprocess.TimeoutExpired,
            RuntimeError,
            http.client.RemoteDisconnected,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return ""


def _translate_indices(
    segments: list[dict[str, Any]],
    indices: list[int],
    *,
    timeout: int,
    delay_seconds: float,
    max_retries: int,
    transport: str,
) -> bool:
    if not indices:
        return True
    text = "\n".join(str(segments[index].get("text") or "").strip().replace("\n", " ") for index in indices)
    for attempt in range(1, max_retries + 1):
        try:
            translated = _translate_text_block(text, timeout, transport)
            translations = [line.strip() for line in translated.split("\n")]
            if len(translations) >= len(indices) and all(translations[i] for i in range(len(indices))):
                for offset, index in enumerate(indices):
                    segments[index]["translation"] = translations[offset]
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
                return True
            if len(indices) > 1:
                middle = max(1, len(indices) // 2)
                left = _translate_indices(
                    segments,
                    indices[:middle],
                    timeout=timeout,
                    delay_seconds=delay_seconds,
                    max_retries=max_retries,
                    transport=transport,
                )
                right = _translate_indices(
                    segments,
                    indices[middle:],
                    timeout=timeout,
                    delay_seconds=delay_seconds,
                    max_retries=max_retries,
                    transport=transport,
                )
                return left and right
            raise RuntimeError(f"Translate returned {len([line for line in translations if line])}/{len(indices)} lines")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected, RuntimeError) as exc:
            if attempt == max_retries:
                return False
            time.sleep(min(60, 6 * attempt))
    return False


def _chunk_indices(segments: list[dict[str, Any]], max_chars: int) -> list[list[int]]:
    chunks: list[list[int]] = []
    current: list[int] = []
    current_chars = 0
    for index, segment in enumerate(segments):
        text = str(segment.get("text") or "").strip().replace("\n", " ")
        if not text:
            continue
        text_len = len(text)
        if current and current_chars + text_len + 1 > max_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(index)
        current_chars += text_len + 1
    if current:
        chunks.append(current)
    return chunks


def _cjk_ratio(text: str) -> float:
    letters = [char for char in text if not char.isspace()]
    if not letters:
        return 0.0
    cjk = sum(1 for char in letters if "\u4e00" <= char <= "\u9fff")
    return cjk / len(letters)


def _source_is_already_chinese(segments: list[dict[str, Any]]) -> bool:
    sample_parts: list[str] = []
    for segment in segments:
        text = str(segment.get("text") or "").strip()
        if text:
            sample_parts.append(text)
        if sum(len(part) for part in sample_parts) >= 2000:
            break
    sample = "\n".join(sample_parts)
    return _cjk_ratio(sample) >= 0.35


def translate_file(
    source_path: Path,
    *,
    chinese_dir: Path,
    max_chars: int,
    timeout: int,
    delay_seconds: float,
    max_retries: int,
    transport: str,
    force: bool,
) -> dict[str, Any]:
    source_data = _read_json(source_path)
    source_hash = _sha256(source_path)
    target_path = _target_path(source_data, chinese_dir)
    if not force and _is_complete_zh(target_path, source_hash):
        return {"source": str(source_path), "target": str(target_path), "status": "skipped_complete"}

    segments = source_data.get("segments")
    if not isinstance(segments, list) or not segments:
        return {"source": str(source_path), "target": str(target_path), "status": "blocked_no_segments"}

    translated_segments = [dict(segment) for segment in segments if isinstance(segment, dict)]
    if _source_is_already_chinese(translated_segments):
        for segment in translated_segments:
            if segment.get("text") and not segment.get("translation"):
                segment["translation"] = segment["text"]
        output = dict(source_data)
        output["sourceTranscriptSha256"] = source_hash
        output["translationProvider"] = "source_already_zh"
        output["translationTargetLanguage"] = "zh-CN"
        output["translatedAt"] = datetime.now(timezone.utc).isoformat()
        output["segments"] = translated_segments
        output["debugLogs"] = list(output.get("debugLogs") or []) + [
            f"Source transcript is already Chinese; copied text into translation for {len(translated_segments)} segments."
        ]
        tmp_path = target_path.with_suffix(".json.tmp")
        _write_json(tmp_path, output)
        if not _is_complete_zh(tmp_path, source_hash):
            tmp_path.unlink(missing_ok=True)
            return {"source": str(source_path), "target": str(target_path), "status": "blocked_validation_failed"}
        tmp_path.replace(target_path)
        return {
            "source": str(source_path),
            "target": str(target_path),
            "status": "copied_source_chinese",
            "segments_count": len(translated_segments),
        }

    chunks = _chunk_indices(translated_segments, max_chars)
    for chunk in chunks:
        ok = _translate_indices(
            translated_segments,
            chunk,
            timeout=timeout,
            delay_seconds=delay_seconds,
            max_retries=max_retries,
            transport=transport,
        )
        if not ok:
            missing = [
                index
                for index, segment in enumerate(translated_segments)
                if segment.get("text") and not segment.get("translation")
            ]
            return {
                "source": str(source_path),
                "target": str(target_path),
                "status": "blocked_incomplete_translation",
                "missing_translation_segments_count": len(missing),
                "first_missing_indices": missing[:20],
            }

    missing = [
        index for index, segment in enumerate(translated_segments) if segment.get("text") and not segment.get("translation")
    ]
    if missing:
        return {
            "source": str(source_path),
            "target": str(target_path),
            "status": "blocked_incomplete_translation",
            "missing_translation_segments_count": len(missing),
            "first_missing_indices": missing[:20],
        }

    output = dict(source_data)
    output["sourceTranscriptSha256"] = source_hash
    output["translationProvider"] = f"google_translate_clients5_{transport}"
    output["translationTargetLanguage"] = "zh-CN"
    output["translatedAt"] = datetime.now(timezone.utc).isoformat()
    output["segments"] = translated_segments
    output["debugLogs"] = list(output.get("debugLogs") or []) + [
        f"Translated from {source_path.name} with google_translate_clients5_{transport}; complete={len(translated_segments)} segments."
    ]
    tmp_path = target_path.with_suffix(".json.tmp")
    _write_json(tmp_path, output)
    if not _is_complete_zh(tmp_path, source_hash):
        tmp_path.unlink(missing_ok=True)
        return {"source": str(source_path), "target": str(target_path), "status": "blocked_validation_failed"}
    tmp_path.replace(target_path)
    return {
        "source": str(source_path),
        "target": str(target_path),
        "status": "translated_complete",
        "segments_count": len(translated_segments),
    }


def _source_paths_from_evidence(evidence_pack: Path, only_indices: set[int] | None = None) -> list[Path]:
    pack = _read_json(evidence_pack)
    paths: list[Path] = []
    for episode in pack.get("episodes", []):
        if only_indices is not None and int(episode.get("index") or 0) not in only_indices:
            continue
        transcript = episode.get("transcript")
        if not isinstance(transcript, dict):
            continue
        path_value = transcript.get("path")
        if not path_value:
            continue
        path = Path(str(path_value))
        paths.append(path if path.is_absolute() else ROOT / path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate archived Spotify transcripts to complete zh JSON files.")
    parser.add_argument("--evidence-pack", type=Path, help="Evidence pack whose matched English/original transcripts should be translated.")
    parser.add_argument("--only-index", action="append", type=int, help="Only translate this evidence-pack episode index. Can repeat.")
    parser.add_argument("--source", action="append", type=Path, help="Specific transcript JSON to translate. Can repeat.")
    parser.add_argument("--chinese-dir", type=Path, default=DEFAULT_ZH_DIR)
    parser.add_argument("--status-json", type=Path, help="Write translation status JSON.")
    parser.add_argument("--max-chars", type=int, default=2200)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--delay-seconds", type=float, default=1.5)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--transport", choices=["curl", "urllib"], default="curl")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source_paths: list[Path] = []
    if args.evidence_pack:
        only_indices = set(args.only_index) if args.only_index else None
        source_paths.extend(_source_paths_from_evidence(args.evidence_pack, only_indices))
    if args.source:
        source_paths.extend(args.source)
    source_paths = list(dict.fromkeys(path.resolve() for path in source_paths))
    if not source_paths:
        raise SystemExit("No source transcripts provided.")

    results: list[dict[str, Any]] = []
    max_workers = max(1, args.workers)
    if max_workers == 1:
        for source_path in source_paths:
            result = translate_file(
                source_path,
                chinese_dir=args.chinese_dir,
                max_chars=args.max_chars,
                timeout=args.timeout,
                delay_seconds=args.delay_seconds,
                max_retries=args.max_retries,
                transport=args.transport,
                force=args.force,
            )
            results.append(result)
            print(json.dumps(result, ensure_ascii=False))
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    translate_file,
                    source_path,
                    chinese_dir=args.chinese_dir,
                    max_chars=args.max_chars,
                    timeout=args.timeout,
                    delay_seconds=args.delay_seconds,
                    max_retries=args.max_retries,
                    transport=args.transport,
                    force=args.force,
                ): source_path
                for source_path in source_paths
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print(json.dumps(result, ensure_ascii=False))

    payload = {
        "created_at": datetime.now().astimezone().isoformat(),
        "source_count": len(source_paths),
        "complete_count": sum(
            1
            for item in results
            if item["status"] in {"translated_complete", "skipped_complete", "copied_source_chinese"}
        ),
        "blocked_count": sum(1 for item in results if item["status"].startswith("blocked")),
        "results": sorted(results, key=lambda item: item["source"]),
    }
    if args.status_json:
        _write_json(args.status_json, payload)
    if payload["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
