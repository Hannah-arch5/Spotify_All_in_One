#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


EPISODE_RE = re.compile(r"^#### 情报 \d+：")
ANCHOR_RE = re.compile(r"^(?P<prefix>\s*-\s*`?\[[^\]]+\]`?\s*)(?P<body>.+)$")
SENTENCE_END_RE = re.compile(r"[.!?。！？](?=\s|$|[\"'”’`)）])")
MAX_ANCHORS_PER_EPISODE = 8

# These windows deliberately cover mechanisms, constraints, and strategic
# implications instead of retaining every timestamp produced by synthesis.
CURATED_ANCHOR_TIMES = {
    "推理芯片技术路径与市场格局分析": {"4:46", "7:05", "14:46", "34:11", "36:45", "52:49", "1:00:47", "1:18:24"},
    "AI研究的自动化与超级智能的未来愿景": {"0:16", "3:18", "4:26", "8:11", "9:41", "19:52", "20:03", "45:57"},
}


def shorten_anchor(line: str) -> str:
    match = ANCHOR_RE.match(line)
    if not match:
        return line
    body = match.group("body").strip()
    body = re.sub(r"^(?:Speaker|发言者)\s*\d+\s*:\s*", "", body, flags=re.IGNORECASE)
    if body.startswith(('"', "'", "`")):
        end = next((m.end() for m in SENTENCE_END_RE.finditer(body[1:]) if m.end() >= 35), None)
        if end is not None and end + 1 < len(body):
            closing = '"' if body[0] == '"' else body[0]
            body = body[: end + 1].rstrip('"\'`') + closing
        elif len(body) > 260:
            cutoff = body.rfind(",", 120, 220)
            closing = '"' if body[0] == '"' else body[0]
            body = body[: cutoff if cutoff > 0 else 220].rstrip('"\'` ') + "..." + closing
        return match.group("prefix").replace("`", "") + body
    if ": " in body and not body.startswith(('"', "'", "`")):
        label, remainder = body.split(": ", 1)
        if len(label) <= 90 and len(remainder) >= 40:
            body = remainder
    end = next((m.end() for m in SENTENCE_END_RE.finditer(body) if m.end() >= 35), None)
    if end is not None and end < len(body):
        body = body[:end].strip()
    elif len(body) > 240:
        cutoff = body.rfind(",", 120, 220)
        body = body[: cutoff if cutoff > 0 else 220].rstrip() + "..."
    return match.group("prefix").replace("`", "") + body


def normalize(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    in_evidence = False
    episode_title = ""
    anchor_count = 0
    keep_times: set[str] | None = None
    skip_translation = False
    changed = False
    for line in lines:
        episode_match = EPISODE_RE.match(line)
        if episode_match:
            episode_title = line.split("：", 1)[-1].strip()
            keep_times = CURATED_ANCHOR_TIMES.get(episode_title)
            anchor_count = 0
            skip_translation = False
        if line.strip() in {"情报价值点：", "关键金句 / 结论：", "证据锚点："}:
            replacement = "- " + line.strip()
            changed |= line != replacement
            out.append(replacement)
            in_evidence = line.strip() == "证据锚点："
            continue
        if line.startswith("## 第一部分:") or line.startswith("## 第一部分："):
            replacement = "## 第一部分：本期核心判断 (Core Judgment)"
            changed |= line != replacement
            out.append(replacement)
            continue
        if line.startswith("## 第二部分:") or line.startswith("## 第二部分："):
            replacement = "## 第二部分：逐集情报与证据 (Episode Intelligence and Evidence)"
            changed |= line != replacement
            out.append(replacement)
            continue
        if EPISODE_RE.match(line):
            in_evidence = False
        if line.strip() == "- 证据锚点：" or line.strip() == "证据锚点：":
            in_evidence = True
        elif in_evidence and (line.startswith("---") or line.startswith("## ") or EPISODE_RE.match(line)):
            in_evidence = False
        if skip_translation:
            if not line.strip() or line.lstrip().startswith("*"):
                skip_translation = False
                changed = True
                continue
            skip_translation = False
        if in_evidence:
            numbered = re.match(r"^(\s*)\d+\.\s+\*\*(\[[^\]]+\])\s*(.*?)\*\*:?\s*(.*)$", line)
            if numbered:
                line = f"{numbered.group(1)}- {numbered.group(2)} {numbered.group(3)} {numbered.group(4)}".rstrip()
        if in_evidence and ANCHOR_RE.match(line):
            timestamp_match = re.search(r"\[([^\]]+)\]", line)
            timestamp = timestamp_match.group(1) if timestamp_match else ""
            if keep_times is not None:
                keep = timestamp in keep_times
            else:
                keep = anchor_count < MAX_ANCHORS_PER_EPISODE
            anchor_count += 1
            if not keep:
                skip_translation = True
                changed = True
                continue
            new_line = shorten_anchor(line)
            changed |= new_line != line
            out.append(new_line)
        else:
            new_line = re.sub(r"^(\s*)\*\s+\*(.+)\*\s*$", r"\1*\2*", line)
            changed |= new_line != line
            out.append(new_line)
    if changed:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    for report in args.reports:
        print(f"{report}: changed={normalize(report)}")


if __name__ == "__main__":
    main()
