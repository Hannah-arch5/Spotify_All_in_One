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
- 第一部分约 900-1100 字，必须给出本窗口整体重点。
- 第一部分以三至四个跨节目判断组织，禁止逐集回顾。主标题用一个可操作的完整判断概括重点，避免“价值重塑”“深度洞察”等抽象词堆叠。
- 不要从本期节目数量或共现关系推断“AI 正在重塑一切”。非 AI 节目只在有明确共同机制时作比较，不得硬塞进 AI 主题。
- 第三部分必须做真正的跨节目专题分析，抽出贯穿多集的结构性主题，不要按 episode 逐个总结。
- 第四部分必须提出跨节目抽象判断和背后机制，不要复述单集内容。
- 第五部分必须形成统一战略判断，不要写成泛泛建议清单。
- 每个主题先指出两集以上材料中可核对的具体动作、成本、约束或反例，再解释跨集机制和什么证据会推翻该判断。不要反复使用“深刻重塑”“范式转移”“核心竞争力”“积极拥抱”等空泛语句。
- 明确区分技术演示、公司自述、受访者预测、未经独立核验的数字和研报自己的推论。不得把个人推测写成既成事实；例如融资、药物、模型安全、就业和地缘政治判断均需要范围或条件。
- 第五部分只给能够指定负责人、先后依赖、退出条件和可测指标的行动。不要编造 6-12 个月/1-3 年/3-5 年等统一时间表，也不要建议所有企业自建数据中心或所有国家设立同一种机构。
- 第三、四、五部分各展开至少三个主题，每个主题至少两段，分别讲清证据关联、作用机制、边界条件及决策含义；不能以几个抽象词或一句话建议代替分析。第五部分还必须写出行动先后顺序、资源约束和可衡量的验证指标。
- 深度要求：为校正模型常见的过度压缩，第三部分必须按3000-3600汉字展开、第四部分必须按2400-2800汉字展开、第五部分必须按2600-3000汉字展开。用材料里的具体机制和相反观点支撑推论，不用重复和空泛口号凑字数。不要把开放必胜、技术进步必然改善福利、私人分配等同公共问责等未经证明的判断写成事实。输出前逐项自检每部分字数和每个主题的两段结构，不足时先扩写再回答。
- 主标题禁止使用“范式跃迁”“范式重塑”“结构性重塑”“价值重塑”“深度洞察”等抽象词拼接。标题必须写成完整、建设性、可执行的判断句，明确本期最重要的行动方向和要解决的矛盾。
- 小标题和正文中的关键判断使用加粗，不能把小标题写成斜体。分清受访者主张、个案与研报推论，争议性叙述不得写成已验证的事实；不能凭空补充数据或把不同集的背景拼成一个事实。
- 所有日期和语境以 Report Date / Report Window 为准，不要使用当前生成时间。

Run ID: {run_id}
Report Date: {report_date}
Report Window: {json.dumps(report_window, ensure_ascii=False)}

Episode brief 摘要：

{joined}
"""


def _section_prompt(
    run_id: str,
    report_date: str,
    report_window: dict,
    compact_briefs: list[str],
    section_key: str,
) -> str:
    joined = "\n\n---\n\n".join(compact_briefs)
    requirements = {
        "title_first": """只输出一级标题和 `## 第一部分：摘要 (Summary)`。标题必须是建设性、可执行的完整判断句并附英文翻译，禁止日期、run id、“Spotify 播客情报研报”以及“范式跃迁/范式重塑/结构性重塑/价值重塑/深度洞察”等抽象拼词。摘要写 900-1100 汉字，以三至四个跨节目判断组织，覆盖本期最重要的共同机制、主要矛盾、边界和决策方向，禁止逐集回顾。""",
        "third": """只输出 `## 第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)`。写 3000-3600 汉字，至少四个主题，每个主题至少两段。先连接两集以上可核对的具体动作、成本、约束或反例，再解释跨集机制、边界条件、决策含义以及什么证据会推翻判断。不得按 episode 逐个总结。""",
        "fourth": """只输出 `## 第四部分：第二层思维 (Second-Order Thinking)`。写 2400-2800 汉字，至少四个主题，每个主题至少两段。提出跨节目二阶效应、反馈回路、利益冲突与失败模式；区分受访者主张、个案和研报推论，说明不确定性及反证条件，不得复述单集内容。""",
        "fifth": """只输出 `## 第五部分：结论与战略意义 (Conclusion and Strategic Implications)`。写 2600-3000 汉字，至少四个主题，每个主题至少两段。形成统一战略判断，并给出可以指定负责人、先后依赖、资源约束、退出条件和可测指标的行动顺序；禁止泛泛建议、统一时间表或无条件技术乐观。""",
    }[section_key]
    return f"""你是播客情报研报主编。请只基于下列 episode brief 摘要完成指定部分，不得添加 brief 之外的事实。

{requirements}

共同硬规则：只输出 Markdown；五大部分标题使用 `##`，部分内部的小标题只能写成独立的 `**加粗小标题**`，不得使用 `##`、`###` 或斜体；关键判断用加粗；使用具体材料与相反观点支撑推论；不得把公司自述、预测、未经独立核验的数字或争议叙述写成事实。不要输出 Run ID、Report Date、Word Count、“第X部分完”等内部自检或收尾文字。所有日期语境以 Report Date / Report Window 为准。输出前自检字数、主题数与每主题两段结构，不足时先扩写再回答。

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


def _synthesis_issues(parts: tuple[str, str, str, str, str]) -> list[str]:
    title, first, third, fourth, fifth = parts
    issues: list[str] = []
    if any(term in title for term in ["范式跃迁", "范式重塑", "结构性重塑", "价值重塑", "深度洞察"]):
        issues.append(f"主标题仍含抽象拼词：{title}")
    for label, section, minimum in [
        ("第一部分", first, 800),
        ("第三部分", third, 2000),
        ("第四部分", fourth, 1600),
        ("第五部分", fifth, 1800),
    ]:
        if len(section) < minimum:
            issues.append(f"{label}当前 {len(section)} 字，最低要求 {minimum} 字")
    return issues


def _title_issues(title: str) -> list[str]:
    issues: list[str] = []
    if re.search(r"20\d{2}|\b\d{6}\b|11月|岁末", title):
        issues.append("主标题含日期或时间标签")
    if any(term in title for term in ["范式", "重塑", "价值重塑", "深度洞察"]):
        issues.append("主标题含抽象拼词")
    if not re.search(r"\([A-Za-z][^()]{8,}\)\s*$", title):
        issues.append("主标题缺少括号内英文翻译")
    return issues


def rewrite_title_only(package_dir: Path, *, model: str, timeout: int) -> Path:
    evidence = _read_json(package_dir / "transcript-evidence-full.json")
    run_id = evidence["run_id"]
    report_path = ROOT / "reports" / "markdown" / f"{run_id}-gemini-report.md"
    report = report_path.read_text(encoding="utf-8")
    first_match = re.search(r"^## 第一部分.*?(?=^## 第二部分)", report, re.DOTALL | re.MULTILINE)
    if not first_match:
        raise SystemExit("Existing report is missing the first section.")
    prompt = f"""你是播客情报研报主编。请只输出一个 Markdown 一级标题，不要解释。

标题必须是建设性、可执行的完整判断句，让读者一眼抓住本期最重要的行动方向与核心矛盾，并在末尾用括号给出自然英文翻译。禁止日期、月份、run id、窗口信息、“Spotify 播客情报研报”，也禁止使用“范式”“重塑”“价值重塑”“深度洞察”等抽象拼词。格式严格为：`# 中文完整判断 (Natural English Translation)`。

本期第一部分：
{first_match.group(0)}
"""
    issues: list[str] = []
    title = ""
    for _ in range(2):
        candidate = _strip_code_fences(_generate_text(
            prompt + (("\n上一版问题：" + "；".join(issues)) if issues else ""),
            model=model,
            max_output_tokens=1024,
            temperature=0.2,
            timeout=timeout,
        ))
        match = re.search(r"^#\s+.+$", candidate, re.MULTILINE)
        title = match.group(0).strip() if match else ""
        issues = _title_issues(title) if title else ["未输出 Markdown 一级标题"]
        if not issues:
            break
    if issues:
        raise SystemExit("Gemini title failed quality gates: " + "; ".join(issues))
    report = re.sub(r"^#\s+.+$", title, report, count=1, flags=re.MULTILINE)
    report_path.write_text(report, encoding="utf-8")
    print(report_path)
    return report_path


def assemble(package_dir: Path, *, model: str, timeout: int, synthesis_file: Path | None = None) -> Path:
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
    if synthesis_file:
        synthesis = synthesis_file.read_text(encoding="utf-8")
        parts = _split_synthesis(synthesis)
        issues = _synthesis_issues(parts)
    else:
        outputs: list[str] = []
        minimums = {"title_first": 800, "third": 2000, "fourth": 1600, "fifth": 1800}
        headings = {
            "title_first": "第一部分",
            "third": "第三部分",
            "fourth": "第四部分",
            "fifth": "第五部分",
        }
        for section_key in ["title_first", "third", "fourth", "fifth"]:
            base_prompt = _section_prompt(run_id, report_date, report_window, compact_briefs, section_key)
            section_issues: list[str] = []
            output = ""
            for attempt in range(2):
                prompt = base_prompt
                if section_issues:
                    prompt += (
                        "\n\n上一版未通过硬性质量门槛。请从 brief 摘要重新生成这一完整部分，"
                        "不要只补充说明。未通过项：\n- " + "\n- ".join(section_issues)
                    )
                output = _strip_code_fences(_generate_text(
                    prompt,
                    model=model,
                    max_output_tokens=16384,
                    temperature=0.2,
                    timeout=timeout,
                ))
                section_issues = []
                heading = headings[section_key]
                match = re.search(rf"^##\s+{heading}.*?\n(.*)\Z", output, re.DOTALL | re.MULTILINE)
                body_length = len(match.group(1).strip()) if match else 0
                if not match:
                    section_issues.append(f"输出缺少 {heading} 标题")
                elif body_length < minimums[section_key]:
                    section_issues.append(
                        f"{heading}正文当前 {body_length} 字，最低要求 {minimums[section_key]} 字"
                    )
                if section_key == "title_first":
                    title_match = re.search(r"^#\s+.+$", output, re.MULTILINE)
                    if not title_match:
                        section_issues.append("输出缺少一级主标题")
                    elif any(term in title_match.group(0) for term in [
                        "范式跃迁", "范式重塑", "结构性重塑", "价值重塑", "深度洞察"
                    ]):
                        section_issues.append(f"主标题仍含抽象拼词：{title_match.group(0)}")
                if not section_issues:
                    break
                print(f"{section_key} quality retry: " + "; ".join(section_issues))
            if section_issues:
                raise SystemExit(
                    f"Synthesis section {section_key} failed quality gates: " + "; ".join(section_issues)
                )
            outputs.append(output)
        synthesis = "\n\n".join(outputs)
        parts = _split_synthesis(synthesis)
        issues = _synthesis_issues(parts)
    if issues:
        raise SystemExit("Synthesis failed quality gates: " + "; ".join(issues))
    title, first, third, fourth, fifth = parts

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
        f"<!-- assembly_mode: {'editorial-synthesis-plus-briefs' if synthesis_file else 'synthesis-plus-briefs'} -->",
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
    parser.add_argument("--synthesis-file", type=Path)
    parser.add_argument("--title-only", action="store_true", help="Rewrite only the existing report title with Gemini.")
    args = parser.parse_args()
    if args.title_only:
        rewrite_title_only(args.package_dir, model=args.model, timeout=args.timeout)
    else:
        assemble(args.package_dir, model=args.model, timeout=args.timeout, synthesis_file=args.synthesis_file)


if __name__ == "__main__":
    main()
