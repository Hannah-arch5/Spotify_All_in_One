#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


KEY_QUOTE_RE = re.compile(r"关键金句\s*/\s*结论[：:]")
EVIDENCE_RE = re.compile(r"证据锚点[：:]")
TIMESTAMP_TOKEN_RE = re.compile(
    r"\s*(?:\(|（|\[)?(?:Timestamp\s*:\s*)?\[?\d{1,2}:\d{2}(?::\d{2})?\]?"
    r"(?:\s*[-–—]\s*\[?\d{1,2}:\d{2}(?::\d{2})?\]?)?(?:\)|）)?\s*",
    re.IGNORECASE,
)
SPEAKER_RE = re.compile(r"\bSpeaker\s*\d+\b[:：]?\s*|发言者\s*\d+\s*[:：]?\s*", re.IGNORECASE)


def _line_is_timestamp_only(line: str) -> bool:
    stripped = line.strip().strip("*-— ")
    if not stripped:
        return False
    return bool(re.fullmatch(r"(?:Timestamp\s*:\s*)?\[?\d{1,2}:\d{2}(?::\d{2})?\]?", stripped, re.IGNORECASE))


def _clean_key_quote_line(line: str) -> str | None:
    if _line_is_timestamp_only(line):
        return None
    if re.search(r"^\s*\*?\s*Timestamp\s*:", line, re.IGNORECASE):
        return None
    line = SPEAKER_RE.sub("", line)
    line = line.replace("接近原文观点：", "")
    line = line.replace("中文翻译：", "")
    line = re.sub(r"\s*[-—]\s*\[\d{1,2}:\d{2}(?::\d{2})?\]\s*$", "", line)
    line = re.sub(r"\s*Timestamp\s*:\s*\[[^\]]+\]\s*$", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s*\(\s*\d{1,2}:\d{2}(?::\d{2})?\s*\)\s*$", "", line)
    line = re.sub(r"\s*（\s*\d{1,2}:\d{2}(?::\d{2})?\s*）\s*$", "", line)
    line = re.sub(r"\s*\[\s*\d{1,2}:\d{2}(?::\d{2})?\s*\]\s*$", "", line)
    return line.rstrip()


def clean_markdown(text: str) -> str:
    lines = text.splitlines()
    cleaned: list[str] = []
    in_key_quotes = False
    for line in lines:
        if KEY_QUOTE_RE.search(line):
            in_key_quotes = True
            cleaned.append(line)
            continue
        if in_key_quotes and EVIDENCE_RE.search(line):
            in_key_quotes = False
            cleaned.append(line)
            continue
        if in_key_quotes:
            line = _clean_key_quote_line(line)
            if line is None:
                continue
        cleaned.append(line)
    return "\n".join(cleaned) + ("\n" if text.endswith("\n") else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove timestamps and speaker labels from key quote blocks.")
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    for report in args.reports:
        original = report.read_text(encoding="utf-8")
        cleaned = clean_markdown(original)
        if cleaned != original:
            report.write_text(cleaned, encoding="utf-8")
            print(f"cleaned={report}")
        else:
            print(f"unchanged={report}")


if __name__ == "__main__":
    main()
