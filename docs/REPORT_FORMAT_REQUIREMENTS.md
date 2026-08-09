# Spotify Podcast Report Delivery Format

Updated: 2026-06-01

This is the required final format for generated Spotify podcast intelligence reports. Treat it as the delivery contract for future Word, PDF, Zotero, Google Drive, and Discord outputs.

Discord delivery note: before posting final PDFs, read `/Users/hannah/Documents/Codex/2026-05-22/whatsapp/MEMORY.md` (`Discord Operating Manual`) and use the existing Discord bot / Discord Studio path. Current bot sender: run `npm run send:discord -- 1508163671988109393 "message" <pdf ...>` from `/Users/hannah/Documents/Codex/2026-05-22/whatsapp/`. Do not default to Chrome web Discord or manual file-upload authorization.

## Source And Renderer

- Final delivery PDFs must be exported from Microsoft Word using `scripts/render_delivery_reports.py`.
- Do not silently use the ReportLab fallback for final delivery. Fallback output is allowed only with explicit approval.
- Use the reference Word document at `/Users/hannah/Downloads/科技播客情报分析报告.docx` as the visual target.

## Page And Typography

- Page size: US Letter landscape, `27.94 cm x 21.59 cm`.
- Margins: `2.54 cm` on all sides.
- Normal body font: `Google Sans`, 11 pt.
- Explicit bold font: `PingFang SC Semibold`.
- Body paragraphs, metadata, and content labels must use exact 14 pt line spacing.
- Body text should stay compact and readable. Avoid mixed line-height drift caused by proportional line spacing.

## Heading Structure

- Visible H1 must be the summarized bilingual report title, not the filename.
- Required H2 part titles:
  - `第一部分：摘要与核心洞察总结 (Abstract & Executive Summary)`
  - `第二部分：核心情报深度梳理 (Detailed Intelligence Breakdown)`
  - `第三部分：深度专题分析 (Deep Thematic Analysis)`
  - `第四部分：深度洞察与第二层思维 (Deep Insights & Second-Level Thinking)`
  - `第五部分：结论与战略意义 (Conclusion & Strategic Implications)`
- Episode intelligence headings such as `情报 1：...` must be Heading 3 and strongly bold.
- Third, fourth, and fifth-part subsection titles must be bold:
  - Markdown `### ...` subsections render as Heading 3.
  - Leading subsection labels in those parts, such as `1. **核心结论：**` or `* **技术突破：**`, keep only the label/title bold.

## Spacing And Separators

- A title that wraps across physical lines is one paragraph and must not look double-spaced.
- Every repeated intelligence entry after the first must have a horizontal separator before it.
- Major parts after the first use separator spacing, not forced page breaks.
- Do not force-start third, fourth, or fifth parts on a new page if they can continue naturally.
- `原始标题`, `来源与发布者`, and `原始链接` must be compact with no blank lines between them.
- `核心内容摘要`, `情报价值点`, `关键金句 / 结论`, and `证据锚点` labels must touch their content with no blank line after the label.
- Separate content blocks from each other with section spacing, not blank lines after labels.

## Bold Rules

- Do not automatically bold body keywords.
- If semantic emphasis is uncertain, do not add it.
- Allowed bold:
  - H1/H2/H3 headings.
  - Structural labels: `原始标题`, `来源与发布者`, `原始链接`, `核心内容摘要`, `情报价值点`, `关键金句`, `证据锚点`.
  - Third/fourth/fifth-part leading subsection titles only.
- Disallowed bold:
  - Random professional terms in body paragraphs.
  - Long body phrases.
  - Generic body phrases such as trends, impact, value, transformation, or topic labels outside the later-part subsection-title rule.

## Removed Fields

- `Transcript 来源` must not appear in final Word or PDF delivery.

## Required Audit Before Delivery

Run `scripts/audit_delivery_report_format.py` after every renderer or formatting change. The audit must pass before replacing Zotero/staged files.

Minimum checks:

- Heading hierarchy and required five part titles.
- Strong heading/label boldness.
- No Markdown heading residue such as `####`.
- No `Transcript 来源`.
- Horizontal separators before repeated intelligence entries.
- Compact metadata and content-label spacing.
- No non-structural body bold except later-part leading subsection titles.
- Exact 14 pt line spacing for body paragraphs.
- PDF text sanity.

For Zotero updates, run `scripts/verify_zotero_report_pdfs.py` after copying files and confirm active Zotero PDF hashes match local `reports/pdf/` hashes.
