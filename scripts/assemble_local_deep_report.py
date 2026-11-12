#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


PROFILES = {
    "20261111-183805-700184": {
        "title": "把丰裕能力变成可持续复利：以验证、健康与资本纪律穿越高波动 (Turning Abundant Capability into Sustainable Compounding: Verification, Health, and Capital Discipline Through Volatility)",
        "summary": [
            "本期 18 集材料共同揭示一个建设性转折：**能力、资本和信息都在变得更丰裕，但真正稀缺的是把它们转化为长期复利的验证系统。** AI 可以写代码、剪视频、辅助医疗沟通、分析生物数据，也能让企业以 token 而非席位采购能力；与此同时，资本市场正在重新定价数据中心、AI 公司、并购标的和热门赛道。新的优势不再来自“率先拥有”，而来自能否持续验证效果、控制风险，并在波动中保留行动空间。",
            "第一条主线是 AI 从功能演示进入生产责任。斯坦福课程把作业改成真实开源贡献，前沿模型 PM 用评测连接研究与产品，代理视频把剪辑拆成可复用工作流，企业 AI 支出则快速转向按使用量计费。**当生成成本下降，任务定义、评测、代码扫描、权限和反馈闭环会成为主要成本。** 只增加调用量而不建立质量基线，会把效率红利变成返工、预算失控和安全债务。",
            "第二条主线是资本重新学习纪律。A 股“低估加风口”框架同时衡量价格成本与时间成本；数据中心和 AI 股票调整显示，供电、建设、需求兑现与政治约束可以让高增长叙事迅速重估；Anthropic、Salesforce 并购与风险投资节目则提示，技术可复制之后，分发、人才、客户关系和资本结构更重要。**估值不是未来的替代品，催化剂也不是安全边际的替代品。**",
            "第三条主线是健康与韧性必须被当成系统能力，而不是个人意志。Katt Williams 与 Bugzy Malone 说明创伤可以转化为动力，但维护成功需要边界、稳定关系和长期练习；医疗、长寿、居住空气和公共健康节目则把健康拆成信息整理、临床沟通、力量训练、睡眠、环境暴露和制度激励。真正可持续的高绩效，不是把人推到极限，而是让问题更早被看见、让干预可验证、让系统能恢复。",
        ],
        "part3": [
            ("1. 能力商品化后，评测与任务设计成为新的稀缺层", "斯坦福 AI 工程课程、前沿模型 PM 和代理视频节目形成同一条因果链：模型把执行成本压低后，组织必须重新定义什么算完成、什么错误不可接受、谁负责复核。课程转向真实仓库和维护者反馈，PM 用 eval 把模糊体验变成可比较信号，视频代理则把素材、剪辑、动画和分发串成流程。**模型能力越普及，真实任务、可靠评测和可回滚交付越难复制。**"),
            ("2. 资本决策必须同时管理价格成本、时间成本与兑现成本", "“低估加风口”不是简单追逐热门，而是把买贵的风险与等待过久的风险放在一起；数据中心、AI 企业支出、Anthropic 估值和风险投资则增加了第三个维度：兑现成本。供电、建设、组织吸收和后续融资都可能让看似正确的方向无法产生回报。**好的方向只有在进入价格合理、催化可识别、执行资源足够时，才会成为好的投资。**"),
            ("3. 从自建到并购，护城河正在从代码转向组织组合", "当代码越来越便宜，企业会更频繁地比较自建、采购和并购。Salesforce 的经验表明，并购价值不仅是功能，还包括人才、分发和缩短路线图；斯坦福与 AI 工程节目则显示，自建能力需要维护者、评测和安全流程。决策不应问“能不能自己写”，而应比较总拥有成本、时间窗口、整合风险与长期控制权。"),
            ("4. 健康系统的价值来自提前暴露问题，而非增加信息焦虑", "医疗 AI、长寿、空气质量与公共健康节目都把注意力从极端干预拉回基础闭环：记录、提问、检测、睡眠、运动、饮食和环境。AI 最有价值的角色是帮助患者准备更聚焦的问题、整理纵向信息并减轻行政负担，而不是替代临床判断。**健康工具的成功指标应是更早发现、更少遗漏和更强依从性，而不是生成更多建议。**"),
        ],
        "part4": [
            ("1. AI 支出增长可能先制造预算错配，再制造生产率", "从席位转向 token 后，使用量可以在没有明确采购节点的情况下快速增长。二阶风险是团队把“更多调用”误认为“更多价值”，而返工、复核和集成成本被分散到各部门。企业需要把 token 成本与任务成功率、人工节省和错误损失绑定，否则五倍支出可能只是五倍试验。"),
            ("2. 基础设施放缓既可能压制增长，也可能提高存量资产收益", "数据中心建设受政策、电力和施工约束时，新增供给放缓会打击设备与开发预期，却可能抬高现有算力租金、改善超大规模厂商现金流，并给管理层下调资本开支提供外部理由。因此“建设放缓”不能被单向解释为 AI 需求消失，必须区分需求、供给、融资和估值四个变量。"),
            ("3. 创伤驱动能产生突破，也可能形成维护阶段的隐性负债", "Katt Williams 与 Bugzy Malone 都把早期困境转化为极强的自我训练和竞争动力，但节目也反复出现关系回避、过度警觉与稳定性问题。组织若只奖励这种极限投入，会在扩张阶段积累健康和协作成本。**从“做成”到“维持”，评价体系必须从英雄式输出转向可重复节奏与心理安全。**"),
            ("4. 生物与医疗 AI 的进步会先扩大可解释性责任", "虚拟细胞和多模态生物模型可以加快假设生成，但模型输出越接近研究或临床决策，越需要记录数据来源、适用边界和失败模式。更强预测不会自动减少争议，反而会提高对可复现性、隐私与责任分配的要求。"),
        ],
        "part5": [
            ("第一阶段：建立任务与资本基线（0-30 天）", "选择 3 个高频 AI 工作流，记录当前耗时、错误率、人工复核点和单次成本；对投资与并购机会同时记录估值安全垫、催化时间、执行资源和退出条件。没有基线的项目不得以“战略性”绕过回报检查。"),
            ("第二阶段：用小范围闭环验证（30-90 天）", "为每个工作流设定 eval、权限边界和回滚机制；医疗与健康场景增加专业复核和数据最小化；资本项目设置需求、供给、价格与兑现四组领先指标。目标不是扩大使用，而是证明质量改善与风险可控。"),
            ("第三阶段：把验证结果沉淀为组织资产（90-180 天）", "将通过验证的提示、数据、评测、决策记录和异常处理固化为共享协议；明确何时自建、采购或并购；把员工健康、维护负担和客户信任纳入扩张预算。衡量指标包括任务成功率、返工率、单位有效产出成本、故障恢复时间和关键人才留存。"),
            ("核心结论", "**丰裕不会自动产生复利。只有把模型能力、资本纪律、健康韧性和验证责任放进同一个经营系统，组织才能在高波动环境中持续积累优势。**"),
        ],
    },
    "20261111-183921-490386": {
        "break_before_part4": True,
        "title": "从规模扩张转向可信系统：用留存、权限与组织设计把 AI 机会变成长期优势 (From Scaling Fast to Building Trusted Systems: Turning AI Opportunity into Durable Advantage with Retention, Permissions, and Organization Design)",
        "summary": [
            "本期 12 集节目表面横跨体育投资、俄乌战争、警务科技、前沿模型、开发者基础设施、金融科技、创业加速器、数据供应链与政府组织，但它们共同回答同一个问题：**当技术和资本都能迅速放大行动时，什么机制能让规模不以失控为代价？** 答案不是继续追求更多功能，而是建立留存、权限、反馈、责任和组织设计组成的可信系统。",
            "体育资产和 Revolut 展示了规模的经济性：媒体权利、订阅关系、全球牌照与严格留存曲线可以让平台持续复利。HF0 与 HubSpot 则说明，早期公司需要通过聚焦和完整解决客户问题避开前沿实验室的正面路径。**规模之前要先证明需求，扩张之前要先证明重复性。**",
            "战争、Axon 警务系统和 Nvidia 治理争议把权限问题推到前台。无人机、传感器、机器人和 AI 可以提高响应速度，却也扩大误判、监控与地缘政治风险。Fable 5.2 的模型比较同样提示，基准领先不等于迁移价值；真实采用取决于工作流兼容、可靠性和切换成本。",
            "最后，Resend、Handshake AI 与 a16z 组织史显示，AI 时代的分发入口正在改变。代理会替用户选择服务，前沿实验室购买的不只是原始数据，而是可评测的专家任务与反馈环境；大型组织改革则需要重新设计人才、激励与决策权。**长期优势来自让正确选择更容易、让错误更早暴露，并让责任随着权限一起扩张。**",
        ],
        "part3": [
            ("1. 留存曲线比增长故事更接近真实产品价值", "Revolut 对新产品设置严格留存门槛，HF0 的封闭式加速强调单一目标，HubSpot 则建议从窄市场切入并解决完整客户问题。三者共同说明：增长可以由补贴、渠道或氛围短期放大，留存才证明产品已经进入用户流程。**在扩大团队、地区或产品线前，应先验证核心行为是否重复发生。**"),
            ("2. 代理时代的分发从搜索排名转向机器可选择性", "Resend 被编码代理自动选中，意味着产品不仅要说服人，还要被工具发现、理解、调用和验证。文档结构、API 可靠性、默认配置、错误信息和生态口碑会共同形成新的分发面。AEO 不是新的关键词游戏，而是让产品对代理具有清晰能力边界和可验证结果。"),
            ("3. 高风险系统必须让权限、证据与责任同步扩张", "俄乌无人机战争、Axon 的传感器与机器人、Nvidia 的治理争议都说明，技术放大速度时也会放大误判和滥用。系统设计必须同时回答谁可以启动、依据什么、如何审计、何时撤销，以及事故由谁承担。缺少这些机制的自动化，只是把风险藏进响应速度。"),
            ("4. 数据价值从规模转向可训练、可评测的反馈环境", "Handshake AI 的快速增长说明前沿实验室愿意为专家任务、强化学习反馈和可验证结果付费。原始数据越来越丰富后，稀缺的是能代表真实工作、带有质量标准并允许反复评测的数据环境。企业应把专家判断结构化，而不是只把文档堆进向量库。"),
        ],
        "part4": [
            ("1. 基准领先会增加试用，却未必降低迁移成本", "Fable 5.2 的表现说明新模型可以在评测和复杂演示上领先，但用户是否切换仍取决于稳定性、工具生态、记忆迁移和既有工作流。**模型厂商的竞争将更多发生在兼容性、迁移体验与真实任务总成本，而非单次能力峰值。**"),
            ("2. 安全技术扩张可能同时提高自由与监控风险", "更好的警务记录、无人机和非致命武器可以减少部分暴力和证据缺口，却也降低持续监控的边际成本。**自动化越便宜，目的限制、数据保留边界和人工撤销权就越重要。**"),
            ("3. 极端聚焦能加速早期突破，也会放大单点判断错误", "HF0 的修道院式环境减少干扰并强化信念，但封闭网络也可能让错误假设得到更快强化。**高强度执行必须配套外部客户验证、反证审查和健康恢复窗口，才能避免把速度当成方向正确。**"),
            ("4. 稀缺资产的金融化会吸引资本，也会提高周期敏感性", "体育媒体权利和球队估值受益于稀缺性与全球观众，但机构资本进入后，回报更依赖转播增长、联赛治理和退出流动性。**价格上涨本身不能证明现金流可持续；投资者必须拆分文化稀缺、合同现金流与估值扩张。**"),
        ],
        "part5": [
            ("产品与增长", "对每项新产品设置 4、8、12 周留存曲线和明确停止线；同步测试人类用户与代理调用的发现率、成功率和错误恢复。只有留存和单位经济性同时通过，才增加市场与团队投入。"),
            ("高风险自动化", "建立分级权限、双人批准、完整审计、目的限制和紧急撤销；对警务、金融、国防和身份场景增加独立伦理与安全评审。核心指标包括误报率、人工接管率、权限异常和申诉解决时间。"),
            ("数据与组织", "把专家工作拆成任务、评分标准、反例和反馈，不只积累文本；为大型组织明确岗位能力、激励、决策时限和淘汰机制。每季度检查数据是否提高模型在真实任务上的成功率，以及组织调整是否缩短交付周期。"),
            ("核心结论", "**下一阶段的规模优势，不是让系统做得更多，而是让它在更大范围内仍然可验证、可撤销、可负责。留存证明需求，权限约束风险，组织设计把两者变成长期复利。**"),
        ],
    },
}


INSIGHTS = {
    "20261111-183805-700184": {
        1: ("Katt Williams 以离家、销售和喜剧训练经历说明，卓越并非等待环境改善，而是在人们看不见时把练习当成正式工作。他也把职业早期的合同诱惑与长期自主权联系起来：短期机会若拿走未来控制权，成功会变成新的脆弱性。", "对创始人和创作者而言，本集最重要的不是苦难叙事，而是把逆境转化为可持续训练、边界判断和合同纪律。"),
        2: ("Bugzy Malone 区分了“做成”与“维持”：创伤和黑暗面可以提供极强动力，却不能代替心理稳定、阅读、自我教育和诚实关系。维护阶段需要把警觉转成结构化习惯，而不是持续依赖危机感。", "这为高绩效团队提供了反直觉提醒：突破期的驱动力不一定适合规模期，组织必须为恢复、稳定和长期身份建设留出空间。"),
        3: ("本集用“低估加风口”同时管理价格成本和时间成本。低估值提供安全垫，但没有业绩、政策或资金催化时会长期占用资本；热门方向若估值与拥挤度透支未来增长，同样难以产生回报。", "该框架适合把选股从单一估值比较升级为安全边际、催化路径、拥挤度和资金效率的联合判断。"),
        4: ("斯坦福 CS146S 在编码代理能够完成旧作业后，把课程转向真实开源仓库、维护者反馈和生产级贡献。学生需要理解陌生系统、提出变更、处理测试与安全，而不是只交付能运行的代码。", "教育和招聘都应从“能否生成代码”转向“能否理解系统、验证变更并对维护结果负责”。"),
        5: ("Ashley Alexander 展示 AI 在癌症照护中的现实价值：整理纵向记录、准备更聚焦的问题、追踪治疗信息并减轻照护者认知负担。它帮助患者更好地进入临床对话，但 HIPAA、专业判断与个体差异仍是不可跳过的边界。", "医疗 AI 的有效指标应是减少遗漏、提高就诊准备质量和释放医护时间，而不是让模型替代诊断。"),
        6: ("前沿模型 PM 的角色是把研究能力、用户场景和评测连接起来。60-20-20 组合允许团队同时投资当前可用能力、接近可用的能力和高不确定探索；eval 则把“感觉更好”转成可比较的产品信号。", "模型竞争越激烈，优秀 PM 越需要管理不确定性、设计评测并决定何时让尚不稳定的能力进入产品。"),
        7: ("代理视频把脚本、素材理解、粗剪、动画、翻译和渠道切片串成可对话的工作流。真正的变化不是生成一段视频，而是让会议摘要、产品演示和客户教育内容能够持续更新。", "企业应从低风险存量素材编辑开始，再扩展到周期性内容；品牌审核、事实校验和版权边界必须与自动化同步。"),
        8: ("Justin Mares 将健康干预按基础收益重新排序：食物、运动、睡眠和减少有害暴露优先于极端补剂与生物黑客。检测只有在能改变行动时才有价值，否则会增加成本与焦虑。", "健康产品应证明它能改善可执行行为和长期指标，而不是依赖更多检测与复杂协议制造高端感。"),
        9: ("节目把美国中期选举、AI 股票抛售和数据中心暂停放在同一资本周期中讨论。政治反弹可能限制建设，却也可能给超大规模厂商下调资本开支、改善现金流和消化供给瓶颈提供外部理由。", "判断 AI 周期时应区分终端需求、基础设施供给、融资条件和估值；单日市值变化不能替代这四层分析。"),
        10: ("Mark Hyman 把长寿目标落到力量、蛋白质、睡眠、压力与代谢健康等日常投入，强调随年龄增长保护肌肉的重要性。极端干预的边际收益通常低于持续执行基础习惯。", "企业健康和个人计划都应优先选择可长期坚持、可测量且能降低功能衰退的干预。"),
        11: ("Michael Feldstein 将室内空气与睡眠、认知和慢性暴露联系起来，并指出“闻起来干净”可能只是挥发性化学物。改善路径从通风、源头控制和正确过滤开始，而不是盲目购买设备。", "空气健康产品必须用颗粒物、换气和实际空间表现证明价值，同时警惕节目中的商业利益冲突。"),
        12: ("Anthropic S-1 讨论把高速收入增长、算力成本、客户集中、模型竞争和上市叙事放到同一张表上。前沿模型公司的价值不能只按软件毛利想象，也不能只按基础设施重资产折价。", "投资判断应拆分训练与推理成本、收入质量、续费、资本需求和平台议价权，避免让神话替代单位经济性。"),
        13: ("企业 AI 支出快速增长，代理把采购从固定席位推向持续 token 消耗。Anthropic 与 OpenAI 的份额变化说明能力、工具链和企业接受度正在共同决定预算。", "企业需要建立 AI FinOps：按任务追踪调用、成功率、复核成本和业务结果，防止预算在部门试验中失去可见性。"),
        14: ("中期选举可能强化市场轮动：传统防御板块估值已高，医疗兼具防御与盈利加速潜力；数据中心相关股票下跌则重新提供估值缓冲。", "配置应关注政策变化如何作用于盈利和估值，而不是机械地把选举结果映射成行业涨跌。"),
        15: ("Calley Means 从食品、代谢和医疗激励讨论公共健康问题，核心主张是现有支付体系更擅长处理疾病而非维护健康。节目包含强烈政策立场与商业关联，需要将机制线索与未经独立核验的因果主张分开。", "可用价值在于审视激励与预防投入；涉及公共政策和医学结论时必须回到临床证据与利益披露。"),
        16: ("Fabian Theis 讨论虚拟细胞、多模态单细胞数据和机器学习如何连接分子、细胞与组织尺度。目标不是生成漂亮预测，而是形成可实验验证的干预假设。", "生物 AI 的护城河来自高质量数据、实验闭环和跨尺度验证；模型分数不能替代可复现的生物机制。"),
        17: ("Salesforce 的并购经验说明，在代码更容易构建的时代，收购价值更多来自人才、分发、客户信任和路线图加速。Slack、MuleSoft 等交易也提醒，整合能力决定协同是否兑现。", "并购评估应比较自建时间、人才稀缺、渠道增益和整合成本，而非只看功能重合或收入倍数。"),
        18: ("Ramtin Naimi 将当前风险投资市场与 2019、2021 两种状态比较：热门轮次出现更高价第二批额度，同时撤回或重谈 term sheet 的情况增加，显示热度与脆弱性并存。", "投资者和创始人都应把后续融资概率、价格保护和现金跑道纳入当前估值，避免用一轮高价锁死未来选择。"),
    },
    "20261111-183921-490386": {
        1: ("体育媒体权利和球队估值持续上升，机构资本通过联盟、场馆、内容和周边生态寻找规模机会。稀缺资产、全球观众和长期合同提供吸引力，但价格上涨也提高了对现金流与退出渠道的要求。", "体育投资应分别评估媒体合同、赛事治理、粉丝增长和估值扩张，不把文化影响力直接等同于可分配回报。"),
        2: ("两位军事分析者从兵力、工业能力、无人机、战术适应和政治目标解释俄乌战争。低成本无人系统提高透明度和杀伤效率，却没有消除后勤、训练、电子战与战略意志的重要性。", "企业与政策研究可借鉴其适应循环：观察技术如何被对手快速复制、干扰和重新组合，而非把单一武器当成决定性变量。"),
        3: ("Axon 从 TASER 扩展到摄像、证据软件、无人机与机器人，形成警务操作系统。提高记录和非致命能力的同时，传感器网络与自动化也带来持续监控、用途漂移和升级风险。", "高风险公共技术必须把权限、数据保留、审计、申诉和人工接管写进产品，而不是把治理留给采购之后。"),
        4: ("Fable 5.2 在基准和复杂演示中表现突出，但日常工作是否迁移取决于可靠性、工具生态、既有记忆和切换成本。最佳模型与最适合当前流程的模型可能不是同一个。", "采购应使用自己的任务集和失败成本做评测，比较迁移收益而非追逐发布日排行榜。"),
        5: ("编码代理开始替用户选择邮件基础设施，Resend 因文档、API、生态口碑和可调用性进入代理决策。产品分发由“被人搜索”扩展为“被机器发现并安全执行”。", "面向代理的产品需要机器可读文档、稳定默认值、清晰错误和可验证结果，AEO 不能退化为新的关键词投机。"),
        6: ("Gary Sinise 把演艺事业、家庭经历和退伍军人公益连接为长期服务承诺。其基金会的价值不只是捐赠规模，而是持续建立信任、陪伴和可见的社区支持。", "品牌与公益项目应把一次性传播转成长期交付机制，并用受益者结果而非曝光衡量影响。"),
        7: ("Dharmesh Shah 认为前沿实验室向应用层扩张并未消灭创业空间，但创业者应避开实验室必然前进的“黄砖路”。从窄市场开始、快速学习并解决完整客户问题，可以建立工作流和分发优势。", "创业选题应评估模型厂商的自然边界、客户切换成本和专有反馈，而不是只做一个容易被下一次模型发布吸收的功能。"),
        8: ("Revolut 以严格留存曲线筛选新产品，通过订阅而非主要依赖放贷建立盈利，并用 AI 缩短合规审批周期。全球扩张的核心不是功能数量，而是牌照、风险和运营系统能否复用。", "金融产品在扩大市场前应先证明留存、单位经济性和合规吞吐；AI 应缩短流程但不能降低责任标准。"),
        9: ("HF0 用 12 周封闭驻地、生活服务和高密度同伴环境减少一切非核心干扰。案例显示极端聚焦可以快速提升收入和产品速度，但信念氛围也需要外部客户事实校正。", "加速器和团队冲刺应同时设置单一目标、固定复盘、反证检查和恢复窗口，避免把强度误当成方向正确。"),
        10: ("关于 Nvidia CEO 的报道把私人行为、反情报风险、公司调查与芯片出口政策连接起来。节目中的指控需要独立核验，但它提出了关键治理问题：关键人物关系可能如何影响国家安全、声誉和监管。", "企业应建立适用于高管的利益冲突、敏感接触和事件披露机制，避免把系统性风险压缩成个人公关。"),
        11: ("Handshake AI 的高速增长显示，前沿实验室购买的是专家任务、强化学习反馈和可评测环境，而不仅是更多网页文本。数据供应从收集转向设计真实工作与质量标准。", "企业应把专家判断沉淀为任务、评分、反例和反馈循环；高质量数据资产的价值在于能持续改善真实任务表现。"),
        12: ("Scott Kupor 将 a16z 从小团队扩张的经验带到约两百万人的联邦 workforce，强调人才系统、激励、服务模型和组织结构。大型组织改革不能只靠裁员或新工具，需要改变决策权与绩效反馈。", "组织转型应明确客户是谁、岗位需要什么能力、决策需要多久，并用服务质量和交付周期检验结构调整。"),
    },
}


BANNED = re.compile(
    r"(?i)subscribe|sponsor|promo code|discount|thank you|thanks for|welcome back|"
    r"follow us|advertis|privacy policy|download the app|brought to you|see you next"
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def timestamp(segment: dict[str, Any], segment_index: int) -> str:
    value = segment.get("timestamp")
    if value:
        return str(value)
    start = segment.get("start")
    try:
        seconds = int(float(start))
        return f"{seconds // 60}:{seconds % 60:02d}"
    except (TypeError, ValueError):
        return f"原文段落 {segment_index + 1}"


def is_chinese_source(segments: list[dict[str, Any]]) -> bool:
    sample = "".join(clean_text(item.get("text")) for item in segments[:80])
    chars = [char for char in sample if not char.isspace()]
    return bool(chars) and sum("\u4e00" <= char <= "\u9fff" for char in chars) / len(chars) > 0.35


def has_chinese_translation(segment: dict[str, Any]) -> bool:
    translation = clean_text(segment.get("translation"))
    return len(re.findall(r"[\u4e00-\u9fff]", translation)) >= 4


def select_evidence(
    segments: list[dict[str, Any]],
    zh_segments: list[dict[str, Any]],
    source_is_zh: bool,
    count: int = 6,
) -> list[int]:
    candidates: list[tuple[float, int]] = []
    total = max(1, len(segments))
    for index, segment in enumerate(segments):
        text = clean_text(segment.get("text"))
        if not 70 <= len(text) <= 420 or BANNED.search(text):
            continue
        if not source_is_zh and (index >= len(zh_segments) or not has_chinese_translation(zh_segments[index])):
            continue
        if text.count("?") > 1 or text.casefold().startswith(("yeah", "right", "okay", "well, yeah")):
            continue
        score = min(len(text), 240)
        if re.search(r"\d|%|million|billion|because|therefore|means|risk|cost|build|decision|important|problem", text, re.I):
            score += 70
        if any(mark in text for mark in (".", "。", "!", "！")):
            score += 25
        score += 15 * (index / total)
        candidates.append((score, index))
    selected: list[int] = []
    separation = max(6, total // 35)
    for _, index in sorted(candidates, reverse=True):
        if all(abs(index - existing) >= separation for existing in selected):
            selected.append(index)
        if len(selected) == count:
            break
    return sorted(selected)


def source_label(source: str) -> str:
    labels = {
        "spotify_api_cdp": "Spotify 原生 transcript（STD 核验归档）",
        "spotify_api": "Spotify 原生 transcript",
        "official_rss_vtt": "节目官方 WebVTT transcript",
        "official_rss_txt": "节目官方 transcript",
    }
    return labels.get(source, source.replace("_", " "))


def episode_section(run_id: str, episode: dict[str, Any], audit_episode: dict[str, Any]) -> str:
    index = int(episode["index"])
    transcript_meta = episode["transcript"]
    original = load(Path(transcript_meta["path"]))
    chinese = load(Path(audit_episode["chinese_match"]["path"]))
    segments = list(original.get("segments") or [])
    zh_segments = list(chinese.get("segments") or [])
    source_is_zh = is_chinese_source(segments)
    selected = select_evidence(segments, zh_segments, source_is_zh)
    if len(selected) < 4:
        raise RuntimeError(f"episode {index} has only {len(selected)} meaningful evidence candidates")
    quote_indices = [selected[1], selected[-2]] if len(selected) >= 4 else selected[:2]
    anchor_indices = selected[:4]
    analysis, value = INSIGHTS[run_id][index]
    url = (
        transcript_meta.get("episode_url")
        or episode.get("rss_episode_url")
        or episode.get("audio_url")
        or "unknown"
    )
    lines = [
        f"#### 情报 {index}：{episode['episode_title']}",
        "",
        f"- 原始标题：{episode['episode_title']}",
        f"- 来源与发布者：Spotify | {episode['podcast_title']}",
        f"- 发布时间：{str(episode.get('published_at') or '')[:10]}",
        f"- 原始链接：{url}",
        f"- Transcript 来源：{source_label(str(transcript_meta.get('source') or ''))}",
        "",
        "**核心内容摘要：**",
        analysis,
        "",
        "**情报价值点：**",
        value,
        "",
        "**关键金句 / 结论：**",
    ]
    for segment_index in quote_indices:
        text = clean_text(segments[segment_index].get("text"))
        lines.append(f'- "{text}"')
        if not source_is_zh:
            translation = clean_text(zh_segments[segment_index].get("translation"))
            lines.append(f"  *{translation}*")
    lines.extend(["", "- 证据锚点："])
    for segment_index in anchor_indices:
        text = clean_text(segments[segment_index].get("text"))
        lines.append(f"  - [{timestamp(segments[segment_index], segment_index)}] {text}")
        if not source_is_zh:
            translation = clean_text(zh_segments[segment_index].get("translation"))
            lines.append(f"    *{translation}*")
    return "\n".join(lines)


def render_section(title: str, items: list[tuple[str, str]]) -> str:
    lines = [title]
    for heading, body in items:
        lines.extend(["", f"### {heading}", "", body])
    return "\n".join(lines)


def build(run_id: str, report_date: str) -> Path:
    profile = PROFILES[run_id]
    pack_path = ROOT / "data" / "runs" / f"{run_id}-evidence-pack.json"
    audit_path = ROOT / "data" / "runs" / f"{run_id}-transcript-language-audit.json"
    pack = load(pack_path)
    audit = load(audit_path)
    audit_by_index = {int(item["index"]): item for item in audit["episodes"]}
    details = [episode_section(run_id, ep, audit_by_index[int(ep["index"])]) for ep in pack["episodes"]]
    document = [
        f"<!-- report_date: {report_date} -->",
        f"<!-- generated_at: {datetime.now().astimezone().isoformat()} -->",
        f"<!-- source_package: {run_id} -->",
        "<!-- assembly_mode: local-transcript-grounded-platform-disclosure-blocked -->",
        "",
        f"# {profile['title']}",
        "",
        "## 第一部分：摘要 (Summary)",
        "",
        "\n\n".join(profile["summary"]),
        "",
        "## 第二部分：情报详情 (Intelligence Details)",
        "",
        "\n\n---\n\n".join(details),
        "",
        render_section("## 第三部分：跨节目专题分析 (Cross-Episode Thematic Analysis)", profile["part3"]),
        "",
        (
            "<!-- pagebreak -->\n\n"
            if profile.get("break_before_part4")
            else ""
        ) + render_section("## 第四部分：第二层思维 (Second-Order Thinking)", profile["part4"]),
        "",
        render_section("## 第五部分：结论与战略意义 (Conclusion and Strategic Implications)", profile["part5"]),
        "",
    ]
    output = ROOT / "reports" / "markdown" / f"{run_id}-gemini-report.md"
    output.write_text("\n".join(document), encoding="utf-8")
    print(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, choices=sorted(PROFILES))
    parser.add_argument("--report-date", required=True)
    args = parser.parse_args()
    build(args.run_id, args.report_date)
