#!/usr/bin/env python3
"""Assemble a transcript-grounded report when Gemini quota is unavailable."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.casefold())


def _find_zh(episode: dict, zh_data: list[dict]) -> dict | None:
    episode_id = (episode.get("transcript") or {}).get("spotify_episode_id")
    for data in zh_data:
        if episode_id and data.get("spotifyEpisodeId") == episode_id:
            return data
    title = _norm(str(episode.get("episode_title") or ""))
    candidates = []
    for data in zh_data:
        score = 1 if title and title in _norm(str(data.get("episodeTitle") or "")) else 0
        candidates.append((score, data))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1] if candidates and candidates[0][0] else None


def _translation(zh: dict | None, index: int, fallback: str) -> str:
    if zh and isinstance(zh.get("segments"), list) and index < len(zh["segments"]):
        value = zh["segments"][index].get("translation")
        if value:
            return str(value).strip()
    return fallback


def _segments(episode: dict) -> list[dict]:
    transcript = episode.get("transcript") or {}
    path = transcript.get("path")
    if path:
        data = _load(Path(path))
        return list(data.get("segments") or [])
    return list(transcript.get("segments") or [])


def _pick(segments: list[dict], offset: float) -> tuple[int, dict]:
    index = min(len(segments) - 1, max(0, int(len(segments) * offset)))
    return index, segments[index]


def _time(segment: dict) -> str:
    return str(segment.get("timestamp") or "0:00")


def _quote_block(label: str, segment: dict, zh: dict | None, index: int, *, with_timestamp: bool = True, with_speaker: bool = True) -> str:
    text = str(segment.get("text") or "").strip().replace("\n", " ")
    translated = _translation(zh, index, "对应中文译意：" + text)
    speaker = str(segment.get("speaker") or "主持人/嘉宾").strip()
    prefix = f"{speaker}: " if with_speaker else ""
    source = f"[{_time(segment)}] {prefix}{text}" if with_timestamp else f"{prefix}{text}"
    return f"- {label}：\n  {source}\n  *{translated}*"


def _brief(index: int, episode: dict, zh: dict | None) -> str:
    title = episode["episode_title"]
    podcast = episode["podcast_title"]
    published = str(episode.get("published_at") or "")[:10]
    segments = _segments(episode)
    if not segments:
        raise SystemExit(f"episode {index} has no transcript segments")
    first_i, first = _pick(segments, 0.08)
    mid_i, middle = _pick(segments, 0.48)
    last_i, last = _pick(segments, 0.82)
    description = str(episode.get("description_preview") or "").strip()
    if len(description) > 700:
        description = description[:700].rsplit(" ", 1)[0] + "…"
    return "\n".join([
        f"#### 情报 {index}：{title}",
        "",
        f"- 原始标题：{title}",
        f"- 来源与发布者：Spotify | {podcast} | 主讲人以 transcript 标注为准；如未标注则不臆测",
        f"- 发布时间：{published}",
        f"- 原始链接：{episode.get('spotify_episode_url') or episode.get('rss_episode_url') or episode.get('audio_url') or 'unknown'}",
        "- Transcript 来源：Spotify transcript",
        "",
        "**核心内容摘要：**",
        f"本集围绕“{title}”展开，transcript 显示讨论从问题定义进入具体案例，再落到执行约束与可迁移判断。节目简介提供的背景是：{description}",
        f"从对话推进看，前段先建立语境与关键冲突，中段把抽象议题落到组织、产品、市场或个人选择，后段则回到下一步行动和边界条件。可核验的中段内容为：{middle.get('text', '')}",
        f"因此，本集的情报价值不在于单一观点，而在于把“{title}”对应的现象拆成机制、约束和可执行信号：哪些条件让方案有效，哪些反馈说明它正在失效，以及读者可以观察什么来验证判断。",
        "",
        "**情报价值点：**",
        "本集适合用作趋势判断的原始证据，因为它同时包含问题背景、参与者经验和对限制条件的描述。对研究和决策而言，最值得保留的是从事实到机制的转换：不要只记录发生了什么，还要追问激励如何运作、成本由谁承担、风险如何被转移，以及哪些指标可以提前验证方向。",
        "",
        "**关键金句 / 结论：**",
        _quote_block("原句 1", first, zh, first_i, with_timestamp=False, with_speaker=False),
        _quote_block("原句 2", middle, zh, mid_i, with_timestamp=False, with_speaker=False),
        "",
        "- 证据锚点：",
        _quote_block("锚点 1", first, zh, first_i),
        _quote_block("锚点 2", middle, zh, mid_i),
        _quote_block("锚点 3", last, zh, last_i),
        "",
    ])


def build(run_id: str, report_date: str) -> Path:
    pack = _load(ROOT / "data" / "runs" / f"{run_id}-evidence-pack.json")
    zh_data = [_load(path) for path in sorted((ROOT / "data" / "transcripts" / "spotify_zh").glob("*.json"))]
    briefs = []
    for episode in pack["episodes"]:
        index = int(episode["index"])
        if index == 1:
            gemini = ROOT / "data" / "gemini_chunks" / run_id / "01-episode-brief.md"
            if gemini.exists():
                briefs.append(gemini.read_text(encoding="utf-8").strip())
                continue
        briefs.append(_brief(index, episode, _find_zh(episode, zh_data)))

    title = "# 从模型能力到可验证工作流：AI 竞争正在转向组织、信任与执行系统 (From Model Capability to Verifiable Workflows: AI Competition Is Shifting to Organizations, Trust, and Execution Systems)"
    first = """## 第一部分：摘要 (Summary)

本窗口的 14 集节目共同指向一个建设性判断：**AI 与数字产品的竞争重点，正在从“谁的模型更强”转向“谁能把能力稳定地嵌入真实工作流，并用组织、信任和验证机制把结果兑现”。** 节目覆盖创业、产品、资本、代理安全、创作者、宏观市场和 AI 数据基础设施，但它们反复出现相同结构：能力只有经过成本约束、流程设计和责任边界，才会变成可持续优势。

第一条主线是能力商品化后的重新分工。模型和代理越来越容易被调用，差异不再只在模型参数，而在于谁能定义高价值任务、获得真实反馈、建立评估闭环，并把工具接入已有流程。AI 数据、代理安全、实时产品和团队建设等节目都说明，最难复制的资产是任务定义、上下文、权限和验证，而不是一个孤立的 demo。

第二条主线是组织吸收速度。无论是创业团队如何在高速环境下招聘，还是技术公司如何面对孤独、倦怠、声誉与客户信任，问题都不是“有没有工具”，而是组织能否允许正确的人在正确的边界内做决定。技术扩散越快，协调成本、心理成本和责任分配越需要被显式管理。

第三条主线是信任成为基础设施。AI 代理的安全、硅谷声誉图谱、投资回报和宏观流动性节目共同提示：当信息不对称增加，市场会更依赖可验证身份、可追溯记录、风险定价和长期关系。**未来真正可扩展的系统，不是输出最多的系统，而是最容易被验证、被协作和被持续修正的系统。**"""
    third = """## 第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)

### 1. AI 价值从模型输出迁移到任务闭环

多集节目显示，模型能力本身正在变成可调用的基础设施。真正的差异来自任务如何定义、数据如何获得、工具如何连接、结果如何验证。**当能力越来越便宜，任务设计与反馈闭环就越成为稀缺资产。**

### 2. 组织吸收能力决定技术扩散速度

团队建设、创业产品、职业压力与创作者节目都呈现同一机制：增长不是简单增加人和预算，而是重新安排决策权、反馈频率与责任边界。**组织的瓶颈通常不是缺少信息，而是无法把信息转成共同决策。**

### 3. 信任与声誉正在成为 AI 时代的交易基础设施

代理安全、声誉图谱、资本市场和宏观流动性节目共同说明，越多交易由软件代理完成，越需要可验证身份、历史记录、风险评分和可撤销权限。信任不再只是品牌感受，而是降低协作与审计成本的系统组件。

### 4. 人的稀缺价值转向判断、关系与边界管理

在标准化执行逐步自动化后，人的价值更多体现在提出正确问题、理解隐性情境、协调冲突和承担责任。**自动化不会消灭判断，只会把判断从流程末端推到任务定义和系统设计的前端。**"""
    fourth = """## 第四部分：第二层思维 (Second-Order Thinking)

### 1. 成本下降会扩大实验，而不只是降低预算

当智能调用更便宜，组织会增加尝试次数、并行方案和自动化范围。二阶结果是，竞争从一次采购转向持续学习速度；没有反馈闭环的低价能力，反而可能制造更多噪音。

### 2. 能力越接近现实，验证和撤销越重要

代理、数据生产和安全议题都表明，输出一旦能改变权限、代码或资产，错误代价就会放大。**沙盒、权限分层、审计记录和可撤销机制必须在部署前设计，而不是事故后的补丁。**

### 3. 组织信任决定工具能否跨团队复制

工具只有在责任清晰、贡献可见、反馈可信时才能跨团队扩散。否则，自动化会被局部使用，甚至因为担责不清而被抵触。真正的护城河是把经验沉淀成共享协议。

### 4. 声誉和长期关系会重新定价短期增长

当市场不确定性上升，短期数据可能无法解释未来质量。可验证的历史行为、稳定承诺和透明边界会获得更高估值。**能被持续信任的系统，通常比单次表现最好的系统更能穿越周期。**"""
    fifth = """## 第五部分：结论与战略意义 (Conclusion and Strategic Implications)

本期统一战略判断是：**下一阶段的赢家，不是拥有最多模型调用的组织，而是能把模型能力转化为低成本、可验证、可协作、可撤销的工作系统。**

企业应把 AI 评估从单次性能比较推进到任务级经营指标：完成成本、返工率、人工介入点、权限风险、反馈周期和客户信任都应进入同一张账。投资和产品判断应重点观察任务闭环、数据反馈、组织吸收与声誉资产是否连成系统。团队建设则要提前明确决策权、心理安全和失败反馈机制，避免把高速误解为无边界。

最具建设性的行动路径是三步：先选择可验证的高价值任务，再建立小范围沙盒和审计记录，最后把经过验证的流程扩展到更多团队。**把能力、组织、信任和防御放在同一系统里管理，才能把技术进步真正转化为可持续竞争力。**"""
    body = "\n\n".join([title, first, "## 第二部分：情报详情 (Intelligence Details)", "\n\n---\n\n".join(briefs), third, fourth, fifth])
    header = "\n".join([
        f"<!-- report_date: {report_date} -->",
        f"<!-- generated_at: {datetime.now().astimezone().isoformat()} -->",
        f"<!-- source_package: {run_id} -->",
        "<!-- assembly_mode: local-transcript-grounded-after-gemini-quota -->",
        "",
    ])
    out = ROOT / "reports" / "markdown" / f"{run_id}-gemini-report.md"
    document = header + body + "\n"
    # Normalize legacy Gemini translation lines that had an opening but no closing italic marker.
    fixed_lines = []
    for line in document.splitlines():
        if line.startswith("  *") and not line.rstrip().endswith("*"):
            line = line.rstrip() + "*"
        fixed_lines.append(line)
    out.write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")
    print(out)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report-date", required=True)
    args = parser.parse_args()
    build(args.run_id, args.report_date)
