#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import re
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"


@dataclass
class Section:
    title: str
    lines: list[str]


def short_date(run_id: str) -> str:
    return datetime.strptime(run_id[:8], "%Y%m%d").strftime("%y%m%d")


def episode_count(markdown: str) -> int:
    return len(re.findall(r"^####\s+情报\s+\d+", markdown, flags=re.MULTILINE))


def delivery_name(markdown_path: Path) -> str:
    run_id = markdown_path.stem.replace("-gemini-report", "")
    manifest_path = ROOT / "data" / "gemini_inputs" / run_id / "episode-manifest.json"
    if manifest_path.exists():
        import json

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        episodes = manifest.get("episodes") or []
        if episodes and episodes[0].get("published_at"):
            date_part = episodes[0]["published_at"][:10].replace("-", "")[2:]
            return f"{date_part}-Spotify播客情报研报"
    return f"{short_date(run_id)}-Spotify播客情报研报"


def split_report(markdown: str) -> tuple[str, list[str], str | None, list[Section]]:
    lines = [line.rstrip() for line in markdown.splitlines()]
    title = "Spotify 播客情报研报"
    body_start = 0
    for index, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_start = index + 1
            break

    episodes: list[Section] = []
    intro: list[str] = []
    current: Section | None = None
    second_part_heading: str | None = None
    for raw in lines[body_start:]:
        if raw.startswith("<!--"):
            continue
        if raw.strip().startswith("**Run ID:"):
            continue
        if raw.startswith("## 第二部分"):
            second_part_heading = raw.replace("##", "").strip()
            continue
        if raw.startswith("#### 情报 "):
            if current:
                episodes.append(current)
            current = Section(title=raw.replace("####", "").strip(), lines=[])
            continue
        if current is None:
            intro.append(raw)
        else:
            current.lines.append(raw)
    if current:
        episodes.append(current)
    return title, intro, second_part_heading, episodes


def clean_inline(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = text.replace("`", "")
    return text.strip()


def inline_runs(text: str) -> list[tuple[str, bool]]:
    text = text.strip()
    parts = re.split(r"(\*\*.*?\*\*)", text)
    runs: list[tuple[str, bool]] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            runs.append((part[2:-2], True))
        else:
            runs.append((part.replace("*", ""), False))
    return runs


def label_bold_runs(text: str) -> list[tuple[str, bool]]:
    if "：" in text:
        label, rest = text.split("：", 1)
        if len(label) <= 12:
            return [(label, True), ("：" + rest, False)]
    if ":" in text:
        label, rest = text.split(":", 1)
        if len(label) <= 18:
            return [(label, True), (":" + rest, False)]
    return inline_runs(text)


def paragraph_role(line: str) -> tuple[str, str]:
    stripped = line.strip()
    if not stripped or stripped == "---":
        return "blank", ""
    if stripped.startswith("## "):
        return "h2", clean_inline(stripped[3:])
    if stripped.startswith("### "):
        return "h3", clean_inline(stripped[4:])
    if stripped.startswith("- "):
        return "bullet", clean_inline(stripped[2:])
    if stripped.startswith("* "):
        return "bullet", clean_inline(stripped[2:])
    if re.match(r"^\d+\.\s+", stripped):
        return "number", clean_inline(stripped)
    return "body", clean_inline(stripped)


def set_doc_columns(section, count: int) -> None:
    sect_pr = section._sectPr
    cols = sect_pr.xpath("./w:cols")
    cols_el = cols[0] if cols else OxmlElement("w:cols")
    cols_el.set(qn("w:num"), str(count))
    cols_el.set(qn("w:space"), "420")
    if not cols:
        sect_pr.append(cols_el)


def add_page_number_footer(section) -> None:
    paragraph = section.footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_char = OxmlElement("w:fldChar")
    fld_char.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_char_end = OxmlElement("w:fldChar")
    fld_char_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char)
    run._r.append(instr)
    run._r.append(fld_char_end)


def add_docx_paragraph(doc: Document, role: str, text: str) -> None:
    if role == "blank":
        return
    style = {
        "h1": "Heading 1",
        "h2": "Heading 2",
        "h3": "Heading 3",
        "bullet": "List Bullet",
        "number": "List Number",
    }.get(role, "Body Text")
    paragraph = doc.add_paragraph(style=style)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if role == "body" else WD_ALIGN_PARAGRAPH.LEFT
    if role in {"h1", "h2", "h3"}:
        paragraph.paragraph_format.keep_with_next = True
        paragraph.paragraph_format.keep_together = True
    runs = label_bold_runs(text) if role in {"body", "bullet", "number"} else [(text, False)]
    for run_text, bold in runs:
        run = paragraph.add_run(run_text)
        run.bold = bold
        run.font.name = "Arial"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")


def build_docx(markdown_path: Path, out_path: Path) -> None:
    run_id = markdown_path.stem.replace("-gemini-report", "")
    markdown = markdown_path.read_text(encoding="utf-8")
    title, intro, second_part_heading, episodes = split_report(markdown)

    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    set_doc_columns(section, 1)
    add_page_number_footer(section)

    styles = doc.styles
    for name in ("Normal", "Body Text", "List Bullet", "List Number"):
        style = styles[name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        style.font.size = Pt(11)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.line_spacing = None
    for name, size, color in (
        ("Heading 1", 24, RGBColor(0, 0, 0)),
        ("Heading 2", 18, RGBColor(0, 0, 0)),
        ("Heading 3", 14, RGBColor(0, 0, 0)),
    ):
        style = styles[name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = color
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(12 if name != "Heading 2" else 11.25)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(delivery_name(markdown_path))
    r.bold = True
    r.font.name = "Arial"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    r.font.size = Pt(24)
    r.font.color.rgb = RGBColor(0, 0, 0)
    for line in intro:
        add_docx_paragraph(doc, *paragraph_role(line))

    for index, episode in enumerate(episodes):
        if index == 0 and second_part_heading:
            add_docx_paragraph(doc, "h2", second_part_heading)
        add_docx_paragraph(doc, "h3", episode.title)
        for line in episode.lines:
            add_docx_paragraph(doc, *paragraph_role(line))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)


def register_pdf_font(font_path: str) -> str:
    font_name = "ArialUnicode"
    pdfmetrics.registerFont(TTFont(font_name, font_path))
    return font_name


def pdf_styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DeliveryTitle",
            parent=base["Title"],
            fontName=font_name,
            fontSize=24,
            leading=28,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceAfter=10,
            wordWrap="CJK",
        ),
        "meta": ParagraphStyle(
            "DeliveryMeta",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=8.6,
            leading=10.4,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#666666"),
            spaceAfter=8,
            wordWrap="CJK",
        ),
        "h1": ParagraphStyle(
            "DeliveryH1",
            parent=base["Heading1"],
            fontName=font_name,
            fontSize=18,
            leading=21,
            textColor=colors.black,
            spaceBefore=3,
            spaceAfter=5,
            keepWithNext=1,
            wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "DeliveryH2",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=18,
            leading=21,
            textColor=colors.black,
            spaceBefore=3,
            spaceAfter=4,
            keepWithNext=1,
            wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "DeliveryH3",
            parent=base["Heading3"],
            fontName=font_name,
            fontSize=14,
            leading=16.5,
            textColor=colors.black,
            spaceBefore=3,
            spaceAfter=4,
            keepWithNext=1,
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "DeliveryBody",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=10.1,
            alignment=TA_JUSTIFY,
            spaceAfter=2.8,
            wordWrap="CJK",
        ),
        "bullet": ParagraphStyle(
            "DeliveryBullet",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=10.1,
            leftIndent=12,
            firstLineIndent=-7,
            alignment=TA_LEFT,
            spaceAfter=2.2,
            wordWrap="CJK",
        ),
    }


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, landscape(letter)[0], landscape(letter)[1], stroke=0, fill=1)
    canvas.setFont("ArialUnicode", 7.5)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawCentredString(landscape(letter)[0] / 2, 0.5 * cm, str(canvas.getPageNumber()))
    canvas.restoreState()


def pdf_paragraph(style_map: dict[str, ParagraphStyle], role: str, text: str) -> Paragraph | Spacer:
    if role == "blank":
        return Spacer(1, 4)
    if role == "bullet":
        return Paragraph("• " + pdf_inline(label_bold_runs(text)), style_map["bullet"])
    if role == "number":
        return Paragraph(pdf_inline(label_bold_runs(text)), style_map["bullet"])
    if role == "body":
        return Paragraph(pdf_inline(label_bold_runs(text)), style_map["body"])
    paragraph = Paragraph(pdf_escape(text), style_map.get(role, style_map["body"]))
    if role in {"h1", "h2", "h3"}:
        paragraph.keepWithNext = 1
    return paragraph


def grouped_pdf_flowables(flowables: list[tuple[str, object]]) -> list[object]:
    grouped: list[object] = []
    index = 0
    heading_roles = {"h1", "h2", "h3"}
    while index < len(flowables):
        role, flowable = flowables[index]
        if role not in heading_roles:
            grouped.append(flowable)
            index += 1
            continue

        block = [flowable]
        index += 1
        while index < len(flowables) and flowables[index][0] in heading_roles:
            block.append(flowables[index][1])
            index += 1
        if index < len(flowables):
            block.append(flowables[index][1])
            index += 1
        grouped.append(CondPageBreak(6.2 * cm))
        grouped.append(KeepTogether(block))
    return grouped


def pdf_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pdf_inline(runs: list[tuple[str, bool]]) -> str:
    return "".join(f"<b>{pdf_escape(text)}</b>" if bold else pdf_escape(text) for text, bold in runs)


def build_pdf(markdown_path: Path, out_path: Path, font_path: str) -> None:
    run_id = markdown_path.stem.replace("-gemini-report", "")
    markdown = markdown_path.read_text(encoding="utf-8")
    _, intro, second_part_heading, episodes = split_report(markdown)
    font_name = register_pdf_font(font_path)
    styles = pdf_styles(font_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=landscape(letter),
        rightMargin=2.54 * cm,
        leftMargin=2.54 * cm,
        topMargin=2.54 * cm,
        bottomMargin=2.54 * cm,
    )
    story: list = [Paragraph(delivery_name(markdown_path), styles["title"])]
    flowables: list[tuple[str, object]] = []
    for line in intro:
        role, text = paragraph_role(line)
        if role == "blank":
            continue
        flowables.append((role, pdf_paragraph(styles, role, text)))
    for index, episode in enumerate(episodes):
        if index == 0 and second_part_heading:
            heading = Paragraph(second_part_heading, styles["h2"])
            heading.keepWithNext = 1
            flowables.append(("h2", heading))
        heading = Paragraph(episode.title, styles["h3"])
        heading.keepWithNext = 1
        flowables.append(("h3", heading))
        for line in episode.lines:
            role, text = paragraph_role(line)
            if role == "blank":
                continue
            flowables.append((role, pdf_paragraph(styles, role, text)))
    story.extend(grouped_pdf_flowables(flowables))
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)


def render(markdown_path: Path, font_path: str) -> tuple[Path, Path]:
    run_id = markdown_path.stem.replace("-gemini-report", "")
    stem = delivery_name(markdown_path)
    docx_path = ROOT / "reports" / "word" / f"{stem}.docx"
    pdf_path = ROOT / "reports" / "pdf" / f"{stem}.pdf"
    build_docx(markdown_path, docx_path)
    build_pdf(markdown_path, pdf_path, font_path)
    return docx_path, pdf_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render reviewed Markdown reports into delivery DOCX/PDF files.")
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--font", default=DEFAULT_FONT)
    args = parser.parse_args()
    for report in args.reports:
        docx_path, pdf_path = render(report, args.font)
        print(f"docx={docx_path}")
        print(f"pdf={pdf_path}")


if __name__ == "__main__":
    main()
