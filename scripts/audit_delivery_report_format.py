#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any
import unicodedata

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.oxml.ns import qn
from pypdf import PdfReader


REQUIRED_PARTS = [
    "第一部分：本期核心判断 (Core Judgment)",
    "第二部分：逐集情报与证据 (Episode Intelligence & Evidence)",
    "第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)",
    "第四部分：第二层思维 (Second-Level Thinking)",
    "第五部分：结论与战略意义 (Conclusion & Strategic Implications)",
]

REQUIRED_LABEL_PREFIXES = [
    "原始标题",
    "来源与发布者",
    "原始链接",
    "核心内容摘要",
    "情报价值点",
    "关键金句",
]

REQUIRED_BOLD_FONT = "PingFang SC Semibold"
METADATA_LABELS = ("原始标题", "来源与发布者", "原始链接")
CONTENT_BLOCK_LABELS = ("核心内容摘要", "情报价值点", "关键金句", "证据锚点")
BODY_LINE_SPACING_PT = 14.0
GENERIC_TITLE_PATTERNS = (
    "Spotify 播客情报研报",
    "播客情报研报：AI 时代的颠覆与重塑",
)
LOW_VALUE_ANCHOR_PATTERNS = (
    "互相表达了感谢",
    "表达了感谢和欣赏",
    "播客结束",
    "感谢收听",
    "thanks for listening",
    "thank you for listening",
    "thanks for having me",
    "广告",
    "赞助",
    "片头",
    "片尾",
)
TRANSLATION_LABEL_PATTERNS = (
    "中文解释：",
    "中文翻译：",
    "中文翻译/解释：",
    "中文翻译/解释:",
    "中文解释:",
    "中文翻译:",
    "英文解释：",
    "英文翻译：",
    "英文翻译/解释：",
    "英文翻译/解释:",
    "英文解释:",
    "英文翻译:",
    "英 文 翻译 /解 释 ：",
)


def has_ooxml_bold(run) -> bool:
    r_pr = run._element.rPr
    if r_pr is None:
        return False
    return r_pr.find(qn("w:b")) is not None and r_pr.find(qn("w:bCs")) is not None


def uses_required_bold_font(run) -> bool:
    r_pr = run._element.rPr
    if r_pr is None or r_pr.rFonts is None:
        return False
    values = [r_pr.rFonts.get(qn(f"w:{attr}")) for attr in ("ascii", "hAnsi", "eastAsia", "cs")]
    return all(value == REQUIRED_BOLD_FONT for value in values)


def text_runs(paragraph) -> list[Any]:
    return [run for run in paragraph.runs if run.text.strip()]


def points(value: Any) -> float:
    return value.pt if value is not None and hasattr(value, "pt") else 0.0


def is_label_run(paragraph, run_index: int) -> bool:
    return run_index == 0 and paragraph.text.startswith(METADATA_LABELS + CONTENT_BLOCK_LABELS)


def paragraph_has_blank_before(paragraphs: list[Any], index: int) -> bool:
    return index > 0 and not paragraphs[index - 1].text.strip()


def has_horizontal_rule(paragraph) -> bool:
    p_pr = paragraph._p.pPr
    if p_pr is None:
        return False
    p_bdr = p_pr.find(qn("w:pBdr"))
    return p_bdr is not None and p_bdr.find(qn("w:bottom")) is not None


def part_number(text: str) -> int | None:
    for index, marker in enumerate(("一", "二", "三", "四", "五"), start=1):
        if text.startswith(f"第{marker}部分"):
            return index
    return None


def is_later_part_subtitle_bold(paragraph, run_index: int) -> bool:
    if run_index >= len(paragraph.runs):
        return False
    if not has_ooxml_bold(paragraph.runs[run_index]):
        return False
    before = "".join(run.text for run in paragraph.runs[:run_index]).strip()
    run_text = paragraph.runs[run_index].text.strip()
    after = "".join(run.text for run in paragraph.runs[run_index + 1:]).strip()
    if not run_text:
        return False
    if before and not re.fullmatch(r"\d+\.", before):
        return False
    return bool(run_text.endswith(("：", ":")) or after.startswith(("：", ":")) or not after or paragraph.text.strip().startswith("**"))


def later_part_subtitle_requires_keep(paragraph, run_index: int) -> bool:
    if not is_later_part_subtitle_bold(paragraph, run_index):
        return False
    after = "".join(run.text for run in paragraph.runs[run_index + 1:]).strip()
    return len(after) <= 24


def audit_docx(path: Path) -> dict[str, Any]:
    doc = Document(path)
    paragraphs = doc.paragraphs
    issues: list[str] = []

    markdown_residue = [p.text for p in paragraphs if p.text.strip().startswith("#")]
    if markdown_residue:
        issues.append(f"markdown heading residue remains: {markdown_residue[:3]}")
    transcript_residue = [p.text for p in paragraphs if p.text.startswith("Transcript 来源")]
    if transcript_residue:
        issues.append(f"Transcript 来源 should be removed from delivery reports: {transcript_residue[:3]}")

    h2_texts = [p.text for p in paragraphs if p.style.name == "Heading 2"]
    h1_texts = [p.text.strip() for p in paragraphs if p.style.name == "Heading 1" and p.text.strip()]
    if not h1_texts:
        issues.append("missing main Heading 1 title")
    else:
        title = h1_texts[0]
        if any(pattern == title for pattern in GENERIC_TITLE_PATTERNS):
            issues.append(f"main title is generic and not thesis-led: {title}")
        if "Run ID" in title or re.search(r"\d{6,}|\d{4}-\d{2}-\d{2}", title):
            issues.append(f"main title contains run/date pileup: {title}")
        if not re.search(r"\([A-Za-z][^)]+\)", title):
            issues.append(f"main title must include an English translation in parentheses: {title}")
        if len(title) < 28:
            issues.append(f"main title is too short to communicate a constructive thesis: {title}")

    missing_parts = [part for part in REQUIRED_PARTS if part not in h2_texts]
    if missing_parts:
        issues.append(f"missing required part headings: {missing_parts}")

    episode_headings = [
        (index, p)
        for index, p in enumerate(paragraphs)
        if p.style.name == "Heading 3" and p.text.startswith("情报 ")
    ]
    if not episode_headings:
        issues.append("no episode Heading 3 paragraphs found")

    weak_headings = []
    for p in paragraphs:
        if p.style.name in {"Heading 1", "Heading 2", "Heading 3"}:
            for run in text_runs(p):
                if not has_ooxml_bold(run) or not uses_required_bold_font(run):
                    weak_headings.append((p.style.name, p.text[:80], run.text[:40]))
                    break
    if weak_headings:
        issues.append(f"headings missing strong OOXML bold w:b+w:bCs: {weak_headings[:5]}")

    weak_labels = []
    label_counts = {label: 0 for label in REQUIRED_LABEL_PREFIXES}
    for p in paragraphs:
        for label in REQUIRED_LABEL_PREFIXES:
            if p.text.startswith(label):
                label_counts[label] += 1
                runs = text_runs(p)
                if not runs or not has_ooxml_bold(runs[0]) or not uses_required_bold_font(runs[0]):
                    weak_labels.append((label, p.text[:80]))
    if weak_labels:
        issues.append(f"labels missing strong OOXML bold w:b+w:bCs: {weak_labels[:5]}")

    missing_label_types = [label for label, count in label_counts.items() if count == 0]
    if missing_label_types:
        issues.append(f"missing label types: {missing_label_types}")

    episode_blank_failures = [
        p.text[:80]
        for index, p in episode_headings[1:]
        if not paragraph_has_blank_before(paragraphs, index)
    ]
    if episode_blank_failures:
        issues.append(f"episode headings missing blank paragraph before them: {episode_blank_failures[:5]}")

    missing_episode_rules = []
    for index, p in episode_headings[1:]:
        nearby = paragraphs[max(0, index - 4):index]
        if not any(has_horizontal_rule(item) for item in nearby):
            missing_episode_rules.append(p.text[:80])
    if missing_episode_rules:
        issues.append(f"episode headings missing separator rule before them: {missing_episode_rules[:5]}")

    part_blank_failures = []
    for index, p in enumerate(paragraphs):
        if p.style.name == "Heading 2" and index > 0 and p.text != REQUIRED_PARTS[0]:
            previous_texts = [paragraphs[i].text.strip() for i in range(max(0, index - 3), index)]
            if "" not in previous_texts:
                part_blank_failures.append(p.text)
    if part_blank_failures:
        issues.append(f"part headings missing nearby blank paragraph before them: {part_blank_failures[:5]}")

    loose_headings = []
    heading_pagination_failures = []
    for p in paragraphs:
        if p.style.name in {"Heading 1", "Heading 2", "Heading 3"} and points(p.paragraph_format.space_after) > 3.1:
            loose_headings.append((p.style.name, p.text[:80], points(p.paragraph_format.space_after)))
        if p.style.name in {"Heading 1", "Heading 2", "Heading 3"}:
            if not p.paragraph_format.keep_with_next:
                heading_pagination_failures.append((p.style.name, p.text[:80]))
    if loose_headings:
        issues.append(f"headings have too much space after: {loose_headings[:5]}")
    if heading_pagination_failures:
        issues.append(f"headings must keep with following paragraph: {heading_pagination_failures[:8]}")

    loose_labels = []
    loose_metadata = []
    body_bold_runs = []
    body_line_spacing_failures = []
    current_part_number = 0
    subtitle_pagination_failures = []
    for p in paragraphs:
        if p.style.name == "Heading 2":
            current_part_number = part_number(p.text) or current_part_number
        if p.text.startswith(METADATA_LABELS):
            if points(p.paragraph_format.space_after) > 0.1:
                loose_metadata.append((p.text[:80], points(p.paragraph_format.space_after)))
        if p.text.startswith(CONTENT_BLOCK_LABELS):
            if points(p.paragraph_format.space_after) > 0.1:
                loose_labels.append((p.text[:80], points(p.paragraph_format.space_after)))
        if p.style.name in {"Heading 1", "Heading 2", "Heading 3"}:
            continue
        if current_part_number >= 3 and later_part_subtitle_requires_keep(p, 0):
            if not p.paragraph_format.keep_with_next:
                subtitle_pagination_failures.append(p.text[:80])
        if p.text.strip() and p.style.name in {"Body Text", "Normal", "normal"}:
            rule = p.paragraph_format.line_spacing_rule
            spacing = points(p.paragraph_format.line_spacing)
            if rule != WD_LINE_SPACING.EXACTLY or abs(spacing - BODY_LINE_SPACING_PT) > 0.1:
                body_line_spacing_failures.append((p.text[:80], str(rule), spacing))
        for index, run in enumerate(p.runs):
            if not run.text.strip():
                continue
            visible_index = len([item for item in p.runs[:index] if item.text.strip()])
            if is_label_run(p, visible_index):
                continue
            if has_ooxml_bold(run):
                if current_part_number >= 3 and is_later_part_subtitle_bold(p, index):
                    continue
                body_bold_runs.append((p.text[:80], run.text.strip()[:60]))
    if loose_metadata:
        issues.append(f"metadata lines should be compact with no paragraph space after: {loose_metadata[:5]}")
    if loose_labels:
        issues.append(f"content block labels should touch their content with no paragraph space after: {loose_labels[:5]}")
    if body_bold_runs:
        issues.append(f"body bold emphasis should be removed except structural labels: {body_bold_runs[:8]}")
    if body_line_spacing_failures:
        issues.append(f"body paragraphs must use exact {BODY_LINE_SPACING_PT}pt line spacing: {body_line_spacing_failures[:8]}")
    if subtitle_pagination_failures:
        issues.append(f"later-part subtitles must keep with following paragraph: {subtitle_pagination_failures[:8]}")

    low_value_anchors = []
    for p in paragraphs:
        text = p.text.strip()
        if not text.startswith("[") and not text.startswith("*   [") and not text.startswith("- ["):
            continue
        lowered = text.casefold()
        if any(pattern.casefold() in lowered for pattern in LOW_VALUE_ANCHOR_PATTERNS):
            low_value_anchors.append(text[:120])
    if low_value_anchors:
        issues.append(f"low-value evidence anchors must be removed: {low_value_anchors[:8]}")

    labeled_translation_lines = []
    non_italic_translation_lines = []
    in_key_quote = False
    for p in paragraphs:
        text = p.text.strip()
        if "关键金句" in text and "结论" in text:
            in_key_quote = True
            continue
        if "证据锚点" in text:
            in_key_quote = False
        if in_key_quote and any(pattern in text for pattern in TRANSLATION_LABEL_PATTERNS):
            labeled_translation_lines.append(text[:120])
        if in_key_quote and is_translation_paragraph(text):
            visible_runs = [run for run in p.runs if run.text.strip()]
            if not visible_runs or not all(run.italic for run in visible_runs):
                non_italic_translation_lines.append(text[:120])
    if labeled_translation_lines:
        issues.append(f"Chinese translation/explanation lines must be italicized without prefix labels: {labeled_translation_lines[:8]}")
    if non_italic_translation_lines:
        issues.append(f"translation/explanation lines in key quote blocks must be italicized: {non_italic_translation_lines[:8]}")

    episode_one_quote_issue = audit_episode_one_quote_gate(paragraphs, episode_headings)
    if episode_one_quote_issue:
        issues.append(episode_one_quote_issue)

    return {
        "path": str(path),
        "issues": issues,
        "heading_2_count": len(h2_texts),
        "episode_heading_count": len(episode_headings),
        "label_counts": label_counts,
    }


def audit_episode_one_quote_gate(paragraphs: list[Any], episode_headings: list[tuple[int, Any]]) -> str | None:
    if not episode_headings:
        return None
    start = episode_headings[0][0]
    end = episode_headings[1][0] if len(episode_headings) > 1 else len(paragraphs)
    section = [p.text.strip() for p in paragraphs[start:end] if p.text.strip()]
    quote_index = next((i for i, text in enumerate(section) if text.startswith("关键金句")), None)
    evidence_index = next((i for i, text in enumerate(section) if text.startswith("证据锚点")), None)
    if quote_index is None:
        return "episode 1 missing 关键金句 / 结论 block"
    quote_block = "\n".join(section[quote_index:evidence_index])
    has_english_quote = re.search(r'"[A-Za-z][^"]{12,}"', quote_block)
    has_chinese_quote = re.search(r"[`“\"]?[\u4e00-\u9fff][^`“”\"]{12,}[\u4e00-\u9fff][`”\"]?", quote_block)
    if not has_english_quote and not has_chinese_quote:
        return "episode 1 关键金句 must include at least one source-language original quote"
    italic_translation_lines = []
    for p in paragraphs[start:end]:
        text = p.text.strip()
        if not text:
            continue
        if any(pattern in text for pattern in TRANSLATION_LABEL_PATTERNS):
            return "episode 1 translation/explanation must not include prefix labels"
        if any(run.text.strip() and run.italic for run in p.runs):
            italic_translation_lines.append(text)
    if not italic_translation_lines:
        return "episode 1 关键金句 must include an italicized translation/explanation line"
    return None


def is_translation_paragraph(text: str) -> bool:
    if not text:
        return False
    if text.startswith(("关键金句", "证据锚点", "转述结论")):
        return False
    if re.match(r"^\d+\.", text):
        return False
    if text.startswith(('"', "“", "'")):
        return False
    if re.search(r"\[\d{0,2}:?\d{1,2}:\d{2}\]|\d{1,2}:\d{2}", text):
        return False
    if "Speaker" in text or "发言者" in text:
        return False
    return True


def audit_pdf(path: Path) -> dict[str, Any]:
    reader = PdfReader(str(path))
    text = unicodedata.normalize("NFKC", "\n".join(page.extract_text() or "" for page in reader.pages[:5]))
    issues: list[str] = []
    if "####" in text:
        issues.append("PDF text still contains #### markdown heading residue")
    if "Transcript 来源" in text:
        issues.append("PDF text still contains Transcript 来源")
    for marker in ("本期核心判断", "逐集情报与证据"):
        if marker not in text:
            issues.append(f"PDF first pages missing expected marker: {marker}")
    return {"path": str(path), "issues": issues, "page_count": len(reader.pages)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit generated Spotify delivery DOCX/PDF formatting.")
    parser.add_argument("--docx", action="append", type=Path, default=[])
    parser.add_argument("--pdf", action="append", type=Path, default=[])
    args = parser.parse_args()

    results = {
        "docx": [audit_docx(path) for path in args.docx],
        "pdf": [audit_pdf(path) for path in args.pdf],
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))

    failed = any(item["issues"] for item in results["docx"] + results["pdf"])
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
