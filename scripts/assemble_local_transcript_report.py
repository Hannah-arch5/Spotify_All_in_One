#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


def build(run_id: str, report_date: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    chunk_dir = root / "data" / "gemini_chunks" / run_id
    briefs = []
    for index in range(1, 18):
        path = chunk_dir / f"{index:02d}-episode-brief.md"
        if not path.exists():
            raise SystemExit(f"Missing episode brief: {path}")
        briefs.append(path.read_text(encoding="utf-8").strip())

    title = "# 从成本下降到能力重构：AI基础设施、组织适应与制度创新正在重塑竞争力 (From Falling Costs to Capability Redesign: AI Infrastructure, Adaptation, and Institutional Innovation Are Reshaping Competitiveness)"
    first = """## 第一部分：摘要 (Summary)

本窗口的 17 集播客共同指向一个核心变化：**竞争优势正在从单点能力转向“能力 × 成本 × 组织适应 × 防御机制”的系统组合**。AI 相关节目一方面展示了模型、代理、实时世界生成和基因组模型的能力跃迁，另一方面也反复提醒，能力能否被低成本地部署、被组织吸收并被安全地约束，才决定技术是否真正形成生产力。

最直接的变化发生在 AI 基础设施层。Opus 5.5 与 GPT-6 Sol、Luna 的竞争说明，模型厂商已不再只争夺最高基准分，而是同时争夺单位任务成本、响应速度、默认推理效率和工具生态。更低的 API 价格会改变用户行为，允许更多迭代，并把原本只适合少数高价值任务的智能推向规模化工作流。Runway 的实时世界模型、AI 代理进入现实场景的讨论，以及 Sequence Holdings 对传统公司的重构，则进一步说明，模型能力只有嵌入具体流程、资产和责任边界后，才会产生持续的商业价值。

第二条主线是组织与人的适应。DECIEM 的早期文化、Bending Spoons 的收购与精益团队、Yakov Smirnoff 在旧定位失效后的重新定价，以及 Druski 对“一夜成名”叙事的拆解，都说明**增长不是单纯扩大投入，而是不断重做定位、协作方式和资源配置**。医疗、睡眠和债券市场节目也呈现同一逻辑：新技术或新资本只有在支付能力、监管约束、现金流与用户行为之间形成闭环时，才会从故事变成结果。

第三条主线是边界与防御。政治暴力、AI 暂停争论、基因组模型和宏观政策节目共同表明，系统越强，二阶风险越不能被当作附录处理。尤其在生成式生物学中，设计能力和防御能力使用相近模型，安全测试、监测和治理必须与能力建设同步推进。教育节目则把这一问题延伸到人才供给：AI 越能完成标准化任务，年轻人的价值越来自质疑假设、跨领域探索和把兴趣变成项目的能力。

因此，本期最具建设性的结论是：**下一阶段的赢家不会只是拥有最强模型或最多资本的组织，而是能把低成本智能、真实工作流、可迁移人才和前置防御整合成连续系统的组织。**"""
    third = """## 第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)

### 1. AI 竞争从“更强模型”转向“更便宜的有效工作流”

Opus 5.5 与 GPT-6 Sol、Luna 的发布把行业竞争的评价函数改写为：**完成一个真实任务需要多少成本、多久、多少次返工，以及能否持续迭代**。Runway 的实时世界模型和代理进入现实场景的讨论说明，模型能力的价值取决于它是否能够连接数据、工具、环境与用户反馈。换言之，模型本身正在从产品终点变成工作流中的可替换组件。

### 2. 组织适应能力成为技术扩散的瓶颈

DECIEM、Bending Spoons、Sequence Holdings 与 Yakov Smirnoff 的案例虽然来自不同领域，却呈现同一个机制：**旧的规模、品牌或定位失效时，组织必须重做资源配置，而不是只增加原有投入**。多品牌策略需要内部协作系统，收购策略需要快速识别产品市场契合，传统企业重构需要重新定义决策速度；个人职业转型则需要把旧能力翻译成新市场可以识别的价值。

### 3. “增长”与“安全”不再是两个阶段

基因组模型节目最明确地展示了双重用途：同一类模型既能提升科学发现，也可能扩大生物风险。政治暴力和 AI 暂停讨论则说明，社会系统的反馈速度往往慢于技术扩散速度。**防御、测试、监测和制度约束必须在能力扩张时同步建设**，否则增长越快，累积的尾部风险越大。

### 4. 人才与教育的稀缺价值转向探索和判断

教育节目提出的“side quest”、无成绩和无考试，并不是取消训练，而是把训练目标从标准化服从转向问题选择、跨学科迁移和项目交付。它与创业文化、创作者职业和 AI 代理的讨论相互呼应：**当标准化执行越来越便宜，提出新问题并在不确定性中完成闭环，才是更稀缺的能力**。"""
    fourth = """## 第四部分：第二层思维 (Second-Order Thinking)

### 1. 成本下降不会只带来节省，而会改变需求曲线

当模型价格下降 40% 或 50%，用户不会简单地把同一任务做得更便宜，而会增加尝试次数、并行方案和自动化范围。由此产生的二阶效应是：**模型厂商争夺的不是一次调用，而是用户未来会把哪些工作交给模型**。这也意味着企业采购不能只做静态价格比较，必须测量工具带来的流程重构。

### 2. 能力越接近现实，验证成本越重要

实时世界、代理和基因组模型都把输出从文本推向环境、代码或生物系统。输出一旦能够影响现实，错误的代价就不再是重新生成一段文字，而可能是资产损失、系统失控或安全事件。因此，**评估、沙盒、权限边界和可追溯性会成为能力扩散的前提，而不是上线后的补丁**。

### 3. 组织的真正护城河是吸收速度

资本可以购买模型、设备和人才，但不能自动购买协作习惯、决策权限和跨团队信任。DECIEM 的共同创造、Bending Spoons 的精益团队和教育节目强调的自主探索，指向同一个判断：**技术扩散的上限往往由组织吸收新能力的速度决定**。过度层级化的组织即使拥有先进工具，也可能把工具降级成低价值的局部自动化。

### 4. 未来的“安全”将成为生产力的一部分

在基因组和政治风险议题中，安全不只是限制创新，而是让创新能够被部署、融资和长期使用的条件。能够提前证明风险边界、快速发现异常并持续修正的组织，会获得更大的试验空间。**防御能力越成熟，能力建设越可持续**。"""
    fifth = """## 第五部分：结论与战略意义 (Conclusion and Strategic Implications)

本期的统一判断是：**下一轮竞争不是谁拥有最多的“智能”，而是谁能把智能转化为低成本、可验证、可扩展且能持续适应的系统。**

对企业而言，应把模型评估从基准榜单推进到任务级经营指标：单位任务成本、完成时间、返工率、人工介入点、数据权限和安全事件都要纳入同一张账。对投资和战略判断而言，应重点观察那些能把模型、工作流、组织重构和分发渠道连成闭环的公司，而不是只看一次发布会的性能排名。对人才和教育而言，应增加项目、实验、跨领域迁移和独立判断的权重，减少把标准化履历当作能力本身。

最后，任何高能力技术都必须配套前置防御。生物安全节目给出的启示尤其明确：当设计能力和攻击能力同时增强时，防御侧不能等到风险显现后才开始建设。**把能力、成本、组织和防御放在同一系统里管理，才是把技术进步转化为长期竞争力的建设性路径。**"""
    body = "\n\n".join([title, first, "## 第二部分：情报详情 (Intelligence Details)", "\n\n---\n\n".join(briefs), third, fourth, fifth])
    header = "\n".join([
        f"<!-- report_date: {report_date} -->",
        f"<!-- generated_at: {datetime.now().astimezone().isoformat()} -->",
        f"<!-- source_package: {run_id} -->",
        "<!-- assembly_mode: local-transcript-grounded-after-gemini-quota -->",
        "",
    ])
    out = root / "reports" / "markdown" / f"{run_id}-gemini-report.md"
    out.write_text(header + body + "\n", encoding="utf-8")
    print(out)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report-date", required=True)
    args = parser.parse_args()
    build(args.run_id, args.report_date)
