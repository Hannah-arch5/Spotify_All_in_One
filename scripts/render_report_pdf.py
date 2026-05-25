#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import textwrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]


def _clean_markdown(line: str) -> str:
    line = re.sub(r"^<!--.*?-->$", "", line).strip()
    line = re.sub(r"`([^`]+)`", r"\1", line)
    line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
    line = re.sub(r"\*([^*]+)\*", r"\1", line)
    line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return line


def render(markdown_path: Path, output_path: Path | None = None) -> Path:
    markdown_path = markdown_path.resolve()
    output_path = output_path or ROOT / "reports" / "pdf" / f"{markdown_path.stem}.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=9,
        leading=14,
        spaceAfter=5,
    )
    h1 = ParagraphStyle("ChineseH1", parent=base, fontSize=18, leading=24, spaceAfter=9, textColor=colors.HexColor("#222222"))
    h2 = ParagraphStyle("ChineseH2", parent=base, fontSize=14, leading=19, spaceBefore=7, spaceAfter=6, textColor=colors.HexColor("#333333"))
    h3 = ParagraphStyle("ChineseH3", parent=base, fontSize=11, leading=16, spaceBefore=5, spaceAfter=4, textColor=colors.HexColor("#444444"))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=markdown_path.stem,
    )
    story = []
    for raw_line in markdown_path.read_text(encoding="utf-8").splitlines():
        line = _clean_markdown(raw_line)
        if not line:
            story.append(Spacer(1, 3))
            continue
        if line.startswith("# "):
            story.append(Paragraph(line[2:], h1))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], h2))
        elif line.startswith("### "):
            story.append(Paragraph(line[4:], h3))
        elif line.startswith("#### "):
            story.append(Paragraph(line[5:], h3))
        else:
            if line.startswith(("- ", "* ")):
                line = "• " + line[2:]
            line = "<br/>".join(textwrap.wrap(line, width=110, break_long_words=False, replace_whitespace=False))
            story.append(Paragraph(line, base))
    doc.build(story)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Markdown podcast report to a simple PDF.")
    parser.add_argument("markdown_path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(render(args.markdown_path, args.output))


if __name__ == "__main__":
    main()
