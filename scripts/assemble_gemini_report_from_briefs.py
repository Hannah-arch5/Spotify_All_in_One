#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re

from generate_chunked_gemini_report import _generate_text


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _compact_brief(brief: str) -> str:
    heading = re.search(r"^####\s+情报\s+\d+[：:].*$", brief, re.MULTILINE)
    title = re.search(r"^- 原始标题[：:]\s*(.+)$", brief, re.MULTILINE)
    summary = re.search(r"^- 核心内容摘要[：:]\s*(.*?)(?=\n-\s+情报价值点|\Z)", brief, re.DOTALL | re.MULTILINE)
    value = re.search(r"^- 情报价值点[：:]\s*(.*?)(?=\n-\s+关键金句|\Z)", brief, re.DOTALL | re.MULTILINE)
    quote = re.search(r"^- 关键金句\s*/\s*结论[：:]\s*(.*?)(?=\n-\s+证据锚点|\Z)", brief, re.DOTALL | re.MULTILINE)
    parts = []
    if heading:
        parts.append(heading.group(0).strip())
    if title:
        parts.append(f"原始标题：{title.group(1).strip()}")
    if summary:
        parts.append("核心内容摘要：" + re.sub(r"\s+", " ", summary.group(1)).strip()[:1600])
    if value:
        parts.append("情报价值点：" + re.sub(r"\s+", " ", value.group(1)).strip()[:900])
    if quote:
        parts.append("关键金句：" + re.sub(r"\s+", " ", quote.group(1)).strip()[:700])
    return "\n".join(parts)


def _synthesis_prompt(run_id: str, report_date: str, report_window: dict, compact_briefs: list[str]) -> str:
    joined = "\n\n---\n\n".join(compact_briefs)
    return f"""你是播客情报研报主编。请基于以下已经完成的 episode brief 摘要，生成最终研报中除第二部分之外的综合内容。

硬性要求：
- 只输出 Markdown。
- 第一行必须是一级标题 `# 中文标题 (English Title)`。标题必须建设性、观点明确，让读者一眼抓住本期研报的核心主题；不要使用日期、run id、窗口信息或“Spotify 播客情报研报”作为主标题。
- 必须输出且只输出这些部分：一级标题、`## 第一部分：摘要 (Summary)`、`## 第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)`、`## 第四部分：第二层思维 (Second-Order Thinking)`、`## 第五部分：结论与战略意义 (Conclusion and Strategic Implications)`。
- 不要输出第二部分；第二部分会由系统用已审核的逐集 brief 原文拼接。
- 第一部分约 700-900 字，必须给出本窗口整体重点。
- 第一部分以三至四个跨节目判断组织，禁止逐集回顾。主标题用一个可操作的完整判断概括重点，避免“价值重塑”“深度洞察”等抽象词堆叠。
- 第三部分必须做真正的跨节目专题分析，抽出贯穿多集的结构性主题，不要按 episode 逐个总结。
- 第四部分必须提出跨节目抽象判断和背后机制，不要复述单集内容。
- 第五部分必须形成统一战略判断，不要写成泛泛建议清单。
- 第三、四、五部分各展开至少三个主题，每个主题至少两段，分别讲清证据关联、作用机制、边界条件及决策含义；不能以几个抽象词或一句话建议代替分析。第五部分还必须写出行动先后顺序、资源约束和可衡量的验证指标。
- 深度要求：第三部分约2000-2600汉字、第四部分约1600-2000汉字、第五部分约1800-2200汉字。用材料里的具体机制和相反观点支撑推论，不用重复和空泛口号凑字数。不要把开放必胜、技术进步必然改善福利、私人分配等同公共问责等未经证明的判断写成事实。
- 小标题和正文中的关键判断使用加粗，不能把小标题写成斜体。分清受访者主张、个案与研报推论，争议性叙述不得写成已验证的事实；不能凭空补充数据或把不同集的背景拼成一个事实。
- 所有日期和语境以 Report Date / Report Window 为准，不要使用当前生成时间。

Run ID: {run_id}
Report Date: {report_date}
Report Window: {json.dumps(report_window, ensure_ascii=False)}

Episode brief 摘要：

{joined}
"""


def _split_synthesis(text: str) -> tuple[str, str, str, str, str]:
    text = _strip_code_fences(text)
    title_match = re.search(r"^#\s+.+$", text, re.MULTILINE)
    if not title_match:
        raise SystemExit("Synthesis output missing H1 title.")
    title = title_match.group(0).strip()

    def section(name: str, next_names: list[str]) -> str:
        next_pattern = "|".join(re.escape(item) for item in next_names)
        pattern = rf"(^##\s+{re.escape(name)}.*?)(?=^##\s+(?:{next_pattern})|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
        if not match:
            raise SystemExit(f"Synthesis output missing {name}.")
        return match.group(1).strip()

    first = section("第一部分", ["第三部分", "第四部分", "第五部分"])
    third = section("第三部分", ["第四部分", "第五部分"])
    fourth = section("第四部分", ["第五部分"])
    fifth = section("第五部分", [])
    return title, first, third, fourth, fifth


def assemble(package_dir: Path, *, model: str, timeout: int) -> Path:
    evidence = _read_json(package_dir / "transcript-evidence-full.json")
    manifest = _read_json(package_dir / "episode-manifest.json")
    run_id = evidence["run_id"]
    chunk_dir = ROOT / "data" / "gemini_chunks" / run_id
    briefs = []
    for episode in evidence["episodes"]:
        brief_path = chunk_dir / f"{int(episode['index']):02d}-episode-brief.md"
        if not brief_path.exists():
            raise SystemExit(f"Missing episode brief: {brief_path}")
        briefs.append(brief_path.read_text(encoding="utf-8").strip())

    report_window = evidence.get("report_window") or manifest.get("report_window") or {}
    report_date = evidence.get("report_date") or manifest.get("report_date") or ""
    compact_briefs = [_compact_brief(brief) for brief in briefs]
    synthesis = _generate_text(
        _synthesis_prompt(run_id, report_date, report_window, compact_briefs),
        model=model,
        max_output_tokens=24576,
        temperature=0.2,
        timeout=timeout,
    )
    title, first, third, fourth, fifth = _split_synthesis(synthesis)

    final_path = ROOT / "reports" / "markdown" / f"{run_id}-gemini-report.md"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(
        [
            title,
            first,
            "## 第二部分：情报详情 (Intelligence Details)",
            "\n\n---\n\n".join(briefs),
            third,
            fourth,
            fifth,
        ]
    )
    header = [
        f"<!-- generated_at: {datetime.now().astimezone().isoformat()} -->",
        f"<!-- gemini_model: {model} -->",
        f"<!-- source_package: {package_dir.resolve()} -->",
        f"<!-- chunk_dir: {chunk_dir} -->",
        "<!-- assembly_mode: synthesis-plus-briefs -->",
        "",
    ]
    final_path.write_text("\n".join(header) + body.strip() + "\n", encoding="utf-8")
    print(final_path)
    return final_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble a Gemini report from completed episode briefs.")
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    assemble(args.package_dir, model=args.model, timeout=args.timeout)


if __name__ == "__main__":
    main()
