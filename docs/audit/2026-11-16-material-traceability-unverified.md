# 一物多码独立追溯校验：消除占位假成功（2026-11-16）

任务AI-MG-TRACEABILITY-FIX-20261116-001，父能力AI-R07-F01，BUG-2026-11-16-012。用户同意只纠正假成功；空态新手引导、诊断覆盖扩展、并行视觉候选继续暂缓。本记录不宣称按物料枚举全部别名的追溯能力已实现。

## 根因、最小修复与范围

原validate_one_material_multiple_codes_traceable忽略material_id/query_aliases，恒返回True和空列表。QueryAliasRecordsFn的合同为按alias_key查记录，不能把material_id转成字符串冒充别名键，也不能拿单个别名命中证明全物料映射完整。

保留原关键字参数、三元组类型及空记录返回；现在明确False与“未验证：尚未接入按物料查询全部别名”。False表示尚未验证，不是已经判定物料不可追溯。不扩大查询接口，不新增审批、权限、路由、模型、配置或迁移。

原20项黄金测试只对本函数做返回形状检查，增强verify的原8项不调用它。本批保留原断言，新增三种回调情形的实际行为锁及真实CLI检查；verify新增第9项，明确通过的是“未验证保护”，不是追溯能力。父计划的历史完成行同步注明此独立helper未接入边界，原物料别名能力不重复开发。

## R6调用链与同类检查

按函数名、模块路径、回调名与相关verify/test消费者查全仓。实际app.py仍使用基础material_governance.match_material_governance、_ai_mg_query_aliases和AI物料别名ORM列表/维护；此增强helper未发现业务调用。消费者为黄金测试、增强verify及verify_ai_all的CORE_SCRIPTS；本批把verify缺失的真实调用一起补齐。

AST候选扫描后的19个同形校验器已独立逐体复核：budget_control三项、document_confirmation_status一项、material_governance_enhanced另外四项、sales_draft_validation一项、knowledge_lifecycle一项、acceptance_evidence两项、data_retention两项、launch_acceptance一项、rollout_control四项。其均检查实际输入并有失败分支，未发现第二个忽略输入的占位恒真；不把合法成功分支、模拟数据或防御fallback算成新BUG。

## 已执行基线与回归

纯模块副本不包含app/app.py和任何业务数据目录；实际导入整个纯逻辑模块，未用恒真替身或源码字符串检查替代行为。显式--noconftest仅用于这些不依赖Flask/ORM的纯模块测试，绝不用于绕过完整应用隔离门禁。宿主未import WMS应用、连接数据库、访问生产HTTP或运行部署入口。

- 有效基线：黄金20 passed；基础verify 8/8、增强verify 8/8。第一轮Windows GBK打印checkmark失败保留，随后解释器显式-X utf8建立有效基线；编码夹具失败不计旧版业务反证。
- 保留新增4锁的旧实现：4 failed/20对照passed，均为真实成功状态/诊断披露断言，无导入/夹具错误。
- 修复候选：24 passed/0失败；基础verify 8/8、增强verify 9/9。旧20项及原脚本8项业务断言保留，没有删减或改宽容差。

## 冻结、整批回退和提交验收

初始产品基线86fadbfbe729de37f8b1064b70647cfd8c416ceb；并行main随后推进至5510ebf732564d9259c404aacf1b0b76b2864760，仅影响本任务发行号和公共台账基线，两个产品/验证模块原始字节无变。BUG编号避开其011，使用012；Windows发行号使用80。测试、脚本、版本、父计划边界、BUG/AI记录、生成索引及本专项合为自洽批次。

纯源码副本中保留新增回归锁，逆序回退本批其余文件、核对5510基线；同锁应恢复旧4失败/20对照，再正序恢复候选并重验24通过。全部路径/摘要、实际JUnit、脚本日志与回退结果以外置回执为准，本段定义验收方法，不预填尚未执行的成功。

索引用query_ledger重建，仅新增本任务与BUG012；生成器把已提交的11条Nov16 BUG按生成顺序归位，内容不改。工作区原有Nov15排序漂移、17行BUG状态改动、父计划另一行视觉标记及其它视觉文件均保留，不纳入本任务暂存。

外置证据根：C:/Users/Administrator/.codex/visualizations/2026/11/15/01a1de80-0f3b-75d1-bcbd-a7f2c7e704aa/traceability-fail-closed-20261116。主要回执为baseline-input.json、baseline-utf8-summary.json、old-regression.xml、candidate.xml、owned-projected-texts.json、index-generation-proof.json，整批/CI结果执行后补证。新增BUG还消费历史状态统计回归锁：5510父提交的011与本批012均须显式登记到POST_SPLIT_BUGS，保留原315/141/19/1历史断言及原全部检查，不通过改变基线或跳过用例取绿。模块全量/相邻、规则、文档/编码/严格AI台账和精确目标三工作流分别验收；全站测试交目标CI，不在宿主重复全应用。

生效确认：本轮不部署或重启，现役封存服务保持原状；生产数据库、备份、认证信息、HTTP及真实单据/设备均未操作。Git提交/推送/CI不等于生产生效。按物料查询全部别名的接口仍未接入，用户若以后需要完整追溯，应作为独立明确范围实施。
