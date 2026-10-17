# WMS 全面审计报告

**审计日期**：2026-10-18 　**审计基线**：main @ 0f8442b3（2026-10-17）　**版本**：2026.09.1
**当前状态（2026-10-18）**：第一批 A10–A18 中 8 项 + CP936 门禁共 9 项已闭环（`046ca9f2`，四条工作流全绿）；第二批按用户要求修复 §4–§9 的 P1/P2 共 14 项（§16.2，排除 app.py 拆分）；第三批继续深化 P1/P2 共 7 项（§16.3）。审计结论本身（§3–§9）保持**审计时点**事实，不回写。
**审计方式**：静态代码审计 + 生产 SQLite 只读核对 + Git/GitHub 元数据核对。审计阶段未运行 pytest/服务/脚本（原因见 §1.3）；**整改阶段**在放宽权限后实际运行了 pytest、lint、pre-commit 钩子与 PowerShell 健康检查（见 §16、§16.1）。
**报告构成**：本文件为总报告；分册（含逐条证据）见 docs/audit/2026-10-18/：backend-flow.md、inventory.md、security.md、ai-quality.md；原定的 frontend.md 因执行中断未产出，前端部分由本报告 §8 补审。

---

## 0. 一页结论

### 0.1 总评

> **系统在"账"上是干净的，在"门禁"上是虚的。**
>
> 生产库 97 张表、1301 个物料、3760 条流水、605+593 张单据，**总账=流水 0 差异、0 负库存、0 悬挂流水、0 空仓流水**；认证/CSRF/SQL 注入/路径穿越这些"主干安全"也做得扎实（360 条写路由无一裸奔、449 处 SQL 无用户输入拼接）。
>
> 真正的问题不在"已发生的账错"，而在**规则只落在单张路径、批量/旁路/新入口大面积漂移**，以及**安全与确认机制"写了但没接线"**：
> - 单张入库完成会回写采购订单状态，**批量完成/反提交不会**（P1）；
> - 单张出库会校验仓库停用，**批量完成不会，且 0 成功仍返回成功**（P1）；
> - AI 建单不填仓库、AI 盘点用全仓总账当账面数（P1/P1）；
> - 低置信度人工确认门禁**三重失效**（风险字段无写入点、记录永不 pending、异常 fail-open）（P1）；
> - 14 条 lint 规则全部"真实现"，但 A2/A6/A7/A8/A9 整体豁免 app/ai，A3–A5 不扫 136 个模板，A8 有 279 处书面豁免（P2）。
>
> 一句话：**"CI 全绿"证明的是"没有新增违规"，不是"高风险面被覆盖"。**

### 0.2 发现统计

| 域 | P0 | P1 | P2 | P3 | 合计 | 分册 |
|---|---:|---:|---:|---:|---:|---|
| 单据生命周期与路由 | 0 | 4 | 8 | 5 | 17 | backend-flow.md |
| 库存口径与多仓 | 0 | 3 | 8 | 6 | 17 | inventory.md |
| 安全（认证/CSRF/注入/XSS/密钥） | 0 | 1 | 6 | 7 | 14 | security.md |
| 前端/模板/Android | 0 | 0 | 3 | 2 | 5 | 本文件 §8（原分册中断） |
| AI / 测试 / 质量门禁 | 0 | 4 | 8 | 6 | 18 | ai-quality.md |
| 运维 / 架构 / 数据（Lead 复核） | 0 | 5 | 9 | 5 | 19 | 本文件 |

> 按域登记 90 条（含跨域重复）；去重后**P0 = 0**、P1 约 13 条（AI 草稿与 AI 盘点为同一根因，跨域合并）、P2 约 30 条、P3 约 24 条。跨域根因见 §11。

### 0.3 必须先做的 8 件事（按 ROI 排序）

1. **修标签模板存储型 XSS**（label_template_detail.html:520 的 |safe 改 |tojson）——唯一可利用的提权链（warehouse 写、admin 打开即执行）。
2. **AI 建单补仓库层**：5 类 AI 草稿 + 盘点统一走 resolve/validate_inventory_warehouse，盘点改 get_warehouse_stock_quantities()。
3. **接线 AI-R08 人工确认门禁**：风险字段回写、门禁 fail-closed、确认页渲染证据并阻断低置信提交。
4. **补批量入口的三处门禁**（PO 状态回写、下游下推守卫、仓库停用校验 + 0 成功返回失败）。
5. **AI 大模型端点从 HTTP 改 HTTPS**（Key 已加密落库，但公网明文传输仍在）。
6. **一物多码 4 组人工合并**，让 uq_material_dedupe_key 真正建起来（当前 DB 级唯一保证缺失）。
7. **清理 4 个旧审计项**（健康检查日志路径、app/wms.bat 死入口、clone 脚本退出码、config 解析）——都是 1 小时内的活。
8. **把"运行现场"从生产日志里分离**，并把启动备份改成防抖/节流，避免再次出现 37 秒 10 次全库备份。

> **整改状态（2026-10-18）**：1 XSS、2 AI 建单仓库层、3 AI 确认门禁、4 批量门禁、7 旧审计项、8 运行现场 **已修**（§16/§16.2）；I2 多行快照已修（§16.3-F01）；5 AI HTTPS 已加运行时 CRITICAL 告警（生产配置未改）；只剩 **6 一物多码合并** 需人工确认数据。A10 随 F08 闭环。

---

## 1. 审计范围、方法与证据边界

### 1.1 基线

| 项 | 值 |
|---|---|
| 工作区 | C:/wms（Windows 实机生产部署） |
| 审计基线 HEAD | 0f8442b3（"docs(audit): close verified A09 service configuration and maintenance"） |
| 审计时上游 | 350cfd40（2026-10-17 15:43Z）；审计时本地落后 4 个提交（8bde424c / 294fbf07 / 2cbedd45 / 350cfd40，均为 hooks/scripts/台账修补） |
| **整改后 HEAD** | **046ca9f2**（2026-10-18）；本地 = origin/main，工作树干净，9 项修复已推送（§16） |
| 审计时工作树 | **不干净**：16 个文件已 staged（A10/F08），另有 1 个 JSON 未暂存。首版曾用 blob-vs-index 误判为干净，`git status` 复核后更正（§15 勘误） |
| 已跟踪文件 | 1730（解析 .git/index） |
| CI | 4 条工作流最近一次 main 运行全部 success（350cfd40）：WMS CI 39046389505、AI Verification 39046389518、Perf 39046389579、Android 39046389585（Android 实际编译的是 217ac3bd@10-16，因 paths 过滤） |

> **审计完整性说明**：本地落后 4 个提交，这 4 个提交只改 .githooks/pre-push、scripts/check_ci_green.py 与台账，不影响本报告任何结论；但其存在本身说明"本地基线 ≠ 上游基线"，建议收尾时 git pull --ff-only 后再复核一次。

### 1.2 覆盖面

| 对象 | 覆盖方式 |
|---|---|
| app/ 167 个 py | 全量正则扫描（路由/鉴权/SQL/密钥/库存写入点）；核心 40+ 文件逐行 |
| app/app.py 35,995 行 | 架构面全量统计 + 约 2,500 行定点精读（启动/迁移/安全/库存原语/AI 建单/确认门禁） |
| app/routes/ 49 模块 611 路由 | 全量路由地图 + 705 条 (url,method) 去重 + 16 个核心模块的 complete/revert/delete/batch 逐函数 |
| app/ai/ 74 文件 22,449 行 | 核心 15 文件精读 + 全量 grep（调用点/权限/门禁） |
| app/templates/ 136 HTML | 全量正则（form/csrf/innerHTML/内联脚本）+ 6 个高危模板精读 + 6 个死模板 |
| app/static/js/ 10 JS | 全量（37 处 innerHTML 逐点判定） |
| app/android-native-wms/ 111 Kotlin | 接口契约 + 错误处理 + 明文 HTTP 抽查（未逐行） |
| tests/ 688 py | 机器分类 675 个 CI 执行文件 + 抽样 30 个人工复核 |
| scripts/ 189 | lint/hooks/verify 调度/更新/恢复/安装/打包/健康检查 |
| .github/workflows/ 4 + .githooks/ 2 | 全文 |
| 生产库 | node:sqlite **只读**（readOnly:true）打开 app/instance/inventory.db，跑 40+ 条一致性查询；未写一个字节 |
| 运行日志/备份 | app/logs/app.log（39,498 行）、app/backups、C:/wms_backups、auto_update_tencent_wms.log 只读分析 |

### 1.3 不能做的事（必须写明的边界）

1. **无法执行外部进程**：本会话 pwsh 返回 0xC0000142（DLL init failed），python/git 经 child_process 返回 EPERM。因此**没有重跑 pytest、没有跑 lint、没有启动服务、没有执行任何 .bat/.ps1**。测试数量/门禁结论均为**读源码**得出；凡"运行时才能确认"的条目均标注 [需运行验证] 或"高度可疑"。
2. **未做渗透测试**：XSS/SQLi/越权为静态判定 + 逐点核对，未实际发 payload。
3. **未审计全部 Android 代码**（111 文件 3 万行，仅契约与配置层）。
4. **未通读 271KB 的 AI 台账**（只做 grep 168 条"已完成" + 抽样核对）。
5. **未验证上游 4 个提交**。

### 1.4 与上一轮审计的关系

仓库在 2026-10-16 做过一次"全仓审计"（docs/audit/WMS_FULL_AUDIT_20261016.md，登记 18 项 A01–A18）。本轮：
- **复核了这 18 项的闭环状态**（§13）：7 项已闭环、1 项代码完成待闭环、10 项仍待修；
- **不重复报告**上一轮已确认且仍有效的 P1（避免"旧闻当新闻"）；
- 本轮新发现集中在：**批量入口门禁漂移、AI 链路、安全输出编码、测试有效性、运行现场**。

---

## 2. 系统画像

### 2.1 规模

| 区域 | 文件 | 行数 | 备注 |
|---|---:|---:|---|
| app/app.py | 1 | **35,995** | 903 顶层函数 / 92 个 @app.route / 1,311 行的 auto_migrate_database() |
| app/routes/ | 49 | 36,863 | 611 路由（316 写） |
| app/ai/ | 74 | 22,449 | 另有 app.py 内 337 个 _ai_* 函数、31 个 /ai/* 路由 |
| app/templates/ | 136 | 63,133 | base.html 3,974 行；121 个内联 script |
| app/static/js/ | 10 | 6,182 | app.js 4,150 行 |
| Android | 111 | 29,819 | Kotlin |
| tests/ | 688 | — | 4,529 test 函数 / 13,865 assert |
| scripts/ | 189 | — | 大量一次性 verify/deep_audit |
| **合计（app 内）** | **429** | **205,303** | |

### 2.2 业务与数据规模（生产库实测）

| 项 | 值 |
|---|---|
| 表 | 97 |
| 物料 | 1,301（其中 1,184 个库存为 0；1 个停用） |
| 库存流水 | 3,760（入库 1,875 / 出库 1,826 / 期初 30 / 反提交 29） |
| 入库单 | 605（全部 completed，全部"采购入库"） |
| 出库单 | 593（全部 completed，全部"领料单"） |
| 盘点/调整/调拨 | **0 / 0 / 0**（模块已建但生产从未使用） |
| 仓库 | 4（实际使用 3；客供仓 0 单） |
| 用户 | 2（admin + 1 个普通用户） |
| 单据时间跨度 | 2026-08-01 ～ 2026-10-16 |
| 数据库 | 4.7MB + WAL 4.1MB，quick_check=ok |

### 2.3 核心矛盾

数据规模是"小型单机应用"（1,301 物料 / 2 用户 / 4 仓库），代码规模是"中大型团队工程"（20 万行 / 97 表 / 688 测试文件 / 4 条 CI / 610 路由）。**单人使用的系统承载了按多人协作设计的治理设施**（台账、灰度、验收、发布门禁、AI 运营），维护成本与业务收益严重失衡——这是本报告所有"复杂性缺陷"的总根因，也是给决策者的第一条建议（见 §8.1）。

---

## 3. 生产现场（运行证据）

> 这一节全部来自**真实文件**：日志、备份、SQLite 数据。它回答"系统现在到底怎么样"。

### 3.1 账是干净的（核心正向结论）

| 检查 | 结果 |
|---|---|
| 物料总账 vs 流水净额（容差 0.01） | **0 条不一致** |
| 负库存（总账 / 仓级） | 0 / 0 |
| 流水 warehouse_id 为空/0 | 0 |
| 流水指向不存在物料/单据 | 0 / 0 |
| 入库/出库表头金额 vs 明细合计 | 0 / 0（但金额全为 0，见 3.6） |
| 单据号重复 | 0 |
| 单据仓库为空 | 0 |
| PRAGMA quick_check | ok |

**结论：截至 2026-10-17，没有发现任何已发生的账实分裂。** 这很重要——它意味着本轮所有 P1 都是"下一次操作会错"，不是"已经错了"。

### 3.2 R1 [P1] 37 秒内 10 次全库启动备份（重启风暴）

- 证据：app/backups/auto_startup_20261017_233138.db ～ ..._233215.db，10 个文件，间隔约 4 秒，每个 4.7MB。
- 影响：说明 10-17 23:31–23:32 应用处于"启动即退出"循环；每次启动同步复制全库。库增长后会拖垮启动并写满磁盘；保留策略只留 10 份，**把此前正常启动的快照全挤掉了**。
- 建议：启动备份加"距上次成功 N 小时才做"+ 同分钟去抖；启动失败写独立 crash 日志；启动备份异步化。

### 3.3 R2 [P2] 生产日志被测试污染，真实故障被淹没

- 证据：app/logs/app.log 39,498 行 → 2,693 行 ERROR/CRITICAL；其中含测试注入标记（isolated cost failure、boom-from-report-api，来自 tests/）；757 次 [SECURITY] SESSION_COOKIE_SECURE=False（app 模块每进程打一次 → 说明大量独立进程共用同一 LOG_FILE）；193 次 ensure_material_dedupe_unique_index 失败: no such column: brand（来自测试自建的极简 material 表，如 tests/test_material_merge.py:373）。
- 影响：排障时无法区分真故障/测试噪声；10MB×5 轮转很容易被噪声写满。
- 建议：LOG_FILE 按用途分流（app / test / audit）；conftest 强制指向 tmp；日志加 run_id。

### 3.4 R3 [P2] 运行目录被当草稿纸

- app/logs/ **438 个文件**：331 .log、68 .txt、26 .json、4 .py、2 .png、1 .patch（含 f07a_attempt_*.txt、flow_*_backup_*.txt 等 AI 过程产物）。
- app/backups/ 30 个 auto_startup_* 文件，其中 **20 个是 .db-wal/.db-shm 侧车**（清理只删 .db）。
- 建议：审计产物统一放 docs/audit/ 或临时目录；备份清理同时删 sidecar。

### 3.5 R4 [P3] WAL 长期未截断

inventory.db-wal = 4.1MB（主库 4.7MB），最后写入 10-16 18:15。长读事务阻止 checkpoint，会让 WAL 无界增长。
建议：确认连接池/线程；维护窗口 PRAGMA wal_checkpoint(TRUNCATE)；监控 WAL 大小。

### 3.6 R5 [P2] 金额/成本维度 100% 为空

- 证据：1301/1301 物料 price=0；1852/1852 入库明细 amount=0；605/605 单据 total_amount=0。
- 影响：采购金额、库存资金占用、BOM 成本、毛利、价格分析全部恒为 0；"表头=明细"校验因全零失去意义。
- 建议：明确是否使用价格维度——不用则隐藏，用则设默认价/必填策略。

### 3.7 R6 [P1] 一物多码 4 组，DB 级唯一索引未生效

- 证据：启动日志 274 次 [DB] 存量仍有 4 组一物多码；数据库无 uq_material_dedupe_key 索引。4 组：301065/40021、40022/40027、108032/108034、115021/115022。
- 影响：一物一码只剩应用层判重，可被绕过；再产生重复后合并成本极高。
- 建议：用 BUG-2026-10-17-004 的"人工选择+确认"页面逐组合并，重启自动补建索引。

### 3.8 R7 [P2] 后台任务写库违反外键（ai_cleanup_log.executed_by=0）

- 证据：PRAGMA foreign_key_check 19 行违规；ai_cleanup_log 57 行中 executed_by=0；2026-08-30 日志 FOREIGN KEY constraint failed。
- 影响：SQLite 默认 foreign_keys=OFF 时静默落脏行；一旦强制外键，清理任务直接失败且被吞。
- 建议：允许 NULL 或建"系统"用户；补 FK 回归测试。

### 3.9 R8 [P2] 库位管理开关的"地雷"

- 证据：location_inventory 2 行残留——material 615（仓 1 库位账 5 / 流水 0）、material 727（仓 2 库位账 1 / 流水 0.4）。
- 影响：库位管理 0→1 时前置校验会正好卡这 2 条；若被强制开启，两个物料的库存显示/出库校验会错。
- 建议：开启前按 services/warehouse_stock_service.py:93 跑校验并人工核销。

### 3.10 R9 [P3] 一次真实的失败更新（历史）

auto_update_tencent_wms.log（2026-07-26）：Please move or remove them before you merge. Aborting → Pull failed; starting existing WMS。旧更新器先停服再拉取。**当前已改为 scripts/update_from_github.py（停服前预检、固定 SHA、失败回退）**，属已整改项，仅作历史证据保留。

---

## 4. 库存口径与多仓（inventory 分册）

> 完整 evidence 见 [inventory.md](docs/audit/2026-10-18/inventory.md)。该分册对 app/ 下 163 个 py、105,911 行做了全量正则扫描（.stock 186 行、get_warehouse_stock_quantities 70 处、三账入口 36 处），并精读 INVENTORY_TRUTH.md 全文 522 行。

### 4.1 主体质量（正向）

- **三账已收口**：出入库、调拨、盘点、调整、期初均走 apply_stock_delta / apply_transfer_pair / apply_opening_balance 三个入口（36 处调用，11 个文件），路由层不再裸调 add_stock 双写。
- **反提交/删除基本对称**：19 处流水清理点逐一核对，净额为 0；生产库实测 0 差异印证。
- **锁覆盖较完整**：_acquire_order_write_lock + 条件 UPDATE（Material.stock >= qty）+ 仓库级子查询护栏（_wh_stock_guards）三层。

### 4.2 I1 [P1] AI 5 类草稿绕过仓库必填，盘点草稿"永久不可完成"

> 与 ai-quality P1-1/P1-2 同一根因，两个域独立确认。

- 位置：app/app.py:11391（领料）、11462（入库）、11570（调拨）、11654（盘点）、11747（调整）。
- 现象：5 类草稿一律不写 warehouse；调拨把仓库名写进 from_location/to_location，调整单把 material.spec 写进 location；盘点 system_stock = material.stock（全仓总账）。
- **闭环证据（本条定为 P1 的关键）**：
  - 完成端硬门禁：check.py:532 if not check.warehouse: return api_error('盘点单未指定仓库，无法完成')；
  - 编辑端也补不了：check.py:329-331（有明细且仓库不一致 → 拒绝）、check.py:690-692（历史盘点单已冻结明细缺仓库 → 拒绝）；
  - 全仓仅 check.py:335 / 712 两处会写 check.warehouse，都被上述门禁挡住 → **AI 盘点草稿 100% 不可完成，只能删单重建**。
- 影响：4 仓环境下 AI 生成单据大面积不可用；盘点账面取总账 → 多仓盘盈亏错误。
- 建议：抽 _ai_draft_warehouse()（解析→validate_inventory_warehouse→默认仓→拒绝），5 处统一补；盘点改 get_warehouse_stock_quantities(wh)；补 A9 回归（当前无任何测试引用 _ai_create_check_draft）。

### 4.3 I2 [P1][需运行验证] 多行同物料反提交用"单次快照逐行比较"，仓库级护栏不下推时可扣成负账

- 位置：in_order.py:2450-2517（反提交）、2953-3015（批量反提交）、after_sale_out.py:423-460、app.py:7656-7732（旧委外发料）。
- 现象：同一物料同单多行时，每行都用**同一份扣减前快照**判断"够不够"，没有按物料合计需求；而 _wh_stock_guards（app.py:35898-35923）在"存在空 location+带来源单据的历史流水""单仓""开启库位"等条件下**主动返回 []**（不下推仓库级护栏），此时扣减只剩全局 Material.stock >= qty。
- 影响：仓库被扣成负数；①=Σ③ 仍成立，但仓库分布错，该仓后续出库/反提交全部被拒。
- 示范（静态推演）：A 仓 10、B 仓 100；A 仓入库单两行 8+8 反提交，逐行都"10≥8"通过；若该物料存在不可归属历史流水 → 护栏不下推 → A 仓 -6。
- 为何只标"高度可疑"：是否触发取决于生产库是否存在令 _wh_stock_guards 返回 [] 的历史流水（本审计未能运行验证）。当前库实测 warehouse_id 无 NULL，风险较低，但**一旦开启库位管理或出现旧流水即成立**。
- 对照：transfer.py:516-526 的调拨校验**做了**按物料累加，是正确写法，可直接照抄。
- 建议：4 处统一"先按 material_id 聚合 required，再比较"；长期把仓库级校验收口进入口层，禁止路由自预校验。

### 4.4 I3 [P1] 业务数据初始化：先归零①再删③，删表失败被吞且接口报成功

- 位置：app.py:8121-8152（_zero_all_material_stock）、8154-8162（_bulk_delete_model 吞异常）、8193-8211（编排）；system_settings.py:260-308（路由只捕获整体异常）。
- 现象：顺序为"completed→pending → Material.query.update({stock:0}) 全表归零 → commit → 逐表删业务/库存表"；每张表删除失败都被捕获、rollback、返回 0，循环继续，最后接口返回 success。
- 影响：若 stock_transaction/location_inventory 删除失败，则 ① 已归零而 ③ 仍在 → 三账永久分裂，用户看到"初始化成功"。这是**唯一一条能直接造成账实分裂的已确认代码路径**（触发需 DB 异常/锁冲突）。
- 建议：先删 ③ 并校验影响行数，再归零 ①；任何一张表删除失败立即整体失败并回滚；接口返回明细；初始化前强制一致性备份。

### 4.5 其余库存问题（P2/P3）

| 编号 | 级别 | 问题 | 位置 |
|---|---|---|---|
| I4 | P2 | 领料单 Excel 导入无仓库列、不解析仓库 → 完成时静默落默认仓，扣错仓 | batch_import.py:199-208、export.py:434 |
| I5 | P2 | 期初库存改库位只改 ①③，不迁移 ② 库位账 | app.py:8300-8383 |
| I6 | P2 | 期初导入逐行异常不回滚、无 savepoint，部分成功 | batch_import.py:899-941 |
| I7 | P2 | /report/inout/print 含 pending 草稿、丢弃列表筛选、仓库判据未走唯一实现 | report.py:334-426、app.js:1903-1927 |
| I8 | P2 | /alert 仓库视图 scoped 判据缺 NULL+location 兜底 → 漏报 | inventory_alert.py:85-117 |
| I9 | P2 | stock_query 传入无效仓库时显示全部物料且库存全 0（误导） | stock_query.py:94-100 |
| I10 | P2 | 新增物料"初始库存"无默认仓 → 产生无归属流水（三账口径隐患） | material.py:336-353 |
| I11 | P2 | AI 出库异常分析仍读全局 material.stock | app.py:10564-10592 |
| I12 | P3 | utils.check_stock_sufficient 仍是全局校验（遗留） | utils.py |
| I13 | P3 | 报表内联重复实现预警判定；workbench metric_scope 文案漂移 | report.py |
| I14 | P3 | 旧 /api/subcontract/quick_issue、quick_receive 死代码却可写库存且无锁 | app.py:7627-7815 |

**结论**：库存域的"主干"是本次审计中工程质量最高的部分；风险全部在**主链路之外的旁路**（AI 草稿、旧 API、Excel 导入、初始化工具、报表口径）。这与 §11 的跨域根因一致。

---

## 5. 单据生命周期与路由（backend-flow 分册）

> 完整 evidence 见 [backend-flow.md](docs/audit/2026-10-18/backend-flow.md)。该分册建立全量路由地图：routes/ 611 路由（316 写）+ app.py 94 路由（43 写）；705 条 (url,method) 去重 **0 冲突**。

### 5.1 B1 [P1] 批量完成/反提交入库单不回写采购订单状态

- 位置：in_order.py:2714-2902（batch_complete）、2908-3027（batch_revert）；对照单张 in_order.py:1955-1956、2529-2530。
- 现象：单张路径改完 status 后调用 update_purchase_order_status(purchase_order)；两个批量入口**全程 0 次**（全文件 21 处调用点，2690 之后到文件尾无一处）。
- 派生关系：采购订单状态由 InOrder.status 聚合 received_qty 后回写（app.py:6238-6260）。
- 影响：凡是"批量审核/批量反审"操作过的入库单，其来源 PO 长期停在旧状态 → 采购执行报表、待办汇总、重复催货/漏采购。
- 建议：照 batch_delete_in_order:2685-2695 的收尾写法，收集 affected ids 后逐单 update_purchase_order_status；补 PO 状态断言测试。

### 5.2 B2 [P1] 批量反提交入库单缺"下游有效下推"守卫 → 单据可永久卡死

- 位置：in_order.py:2908-3027；对照单张 2419、批量删除 2647 均有 _source_has_active_push。
- 机理：对 auto_push_requisition=True 的入库单，完成时会自动生成并完成一张领料单（in_order.py:1958-2011）。批量反提交把它拉回 pending，而下游领料单仍 completed、库存已扣；再次完成时被 request_id='auto-requisition-{id}' 幂等校验拦住（1962-1968）→ **永久卡死，只能改库**。
- 建议：循环内加锁前补 if _source_has_active_push(order_id): skipped.append(...); continue；补测试。

### 5.3 B3 [P1] 批量完成出库单不校验仓库停用，且 0 成功仍返回 success

- 位置：out_order.py:1396-1523；对照单张 1151-1156。
- 现象：单张对非"销售出库"调 assert_warehouse_active；批量只对"销售出库"调 validate_sales_outbound_warehouse，领料/其他出库/采购退货三类**完全不校验**；结尾无条件 status=success（1520-1523）。
- 影响：(1) 停用仓被继续记账（停用仓不进"新单据"口径，账面出现看不到的库存）；(2) 全部跳过仍绿色成功弹窗 —— in_order 已修的同款缺陷（BUG-2026-09-23-004）在 out_order 复发。
- 建议：批量循环补仓库停用校验 + skip/rollback；结尾补 completed==0 → 400。

### 5.4 B4 [P1] 委外快速发料两套实现并存，旧 API 无锁/无幂等/库位键退化

- 位置：app.py:7627-7754（旧 POST /api/subcontract/quick_issue）vs subcontract.py:308-402（新 /subcontract/<id>/issue）。
- 现象：旧实现无写锁、无幂等、无 assert_warehouse_active、无库位入参；非法行静默 continue；issue.location 从未赋值，库位键退化为仓库名。
- 消费面：模板/JS/Android **零引用**，仅测试引用 → 已是"无消费方的可写库存遗留接口"。
- 影响：若被脚本/旧 APK 调用可重复发料（每次新建 completed 发料单并再扣库存）；开启库位管理后会把仓库名当库位写 ②，破坏恒等式。
- 建议：删除旧端点（连同测试改打新端点），或改为薄委托。

### 5.5 其余单据/路由问题（P2/P3）

| 编号 | 级别 | 问题 | 位置 |
|---|---|---|---|
| B5 | P2 | 委外批量状态接口可任意直改状态（含 cancelled），无校验/无审计/无锁 | subcontract.py:755-788 |
| B6 | P2 | 16 处中文用户可见文案乱码（? 替代汉字） | subcontract.py:1260/1340、app.py:16177-17679 |
| B7 | P2 | 精度设置是死代码，库存硬编码 2 位；已完成单改量不归一 → 明细数量≠库存变动 | app.py:4336-4340、utils.py:47/53、in_order.py:2182/2251 |
| B8 | P2 | 40 处把异常原文（英文 SQL/约束名）回传客户端 | batch_import/material/in_order/transfer 等 |
| B9 | P2 | /print_queue/jobs 豁免 CSRF 却接受 Web 会话鉴权 | print_queue.py:549-564 |
| B10 | P2 | recalculate_order_total 不量化，表头金额带浮点尾差 | utils.py:250-255 |
| B11 | P2 | serialize_material 把全局 material.stock 交给前端当"可用库存" | utils.py:184 |
| B12 | P2 | select_all 绕过 100 条上限 | in_order.py:2730/2921 |
| B13 | P3 | AGENTS.md 单据状态权威表与代码漂移 | AGENTS.md:44-56 |
| B14 | P3 | app.py 仍 94 条 @app.route（含 2 组死路由）；10 个 .bak 混在 app/ | app.py |
| B15 | P3 | log_operation/log_audit 内部 commit 隐患；审批双实现无锁 | app.py:7103/5118、approval.py:76 |

### 5.6 模块使用现状（重要背景）

生产库中 **盘点/调整/调拨 = 0 单**。这意味着 B1–B4、I2、I3 中涉及这些模块的缺陷目前都是"未引爆状态"——一旦用户开始使用这些模块（尤其批量操作），风险立即兑现。审计建议在启用这些模块前先完成对应修复。

---

## 6. 安全（security 分册 + Lead 复核）

> 完整 evidence 见 [security.md](docs/audit/2026-10-18/security.md)。该分册建立量化矩阵：709 路由 / 360 写路由 / 43 处 csrf.exempt / A1 表单 0 缺 token / 449 处 SQL 无用户输入拼接。

### 6.1 主干安全（正向，逐条已复核）

| 项 | 结论 |
|---|---|
| 认证 | 360 条写路由逐条核对，**仅 /login 无鉴权装饰器**（A2 官方豁免 + 全局 CSRF + 表单带 token） |
| SQL 注入 | 449 处 execute 中仅 20 处含插值，**全部是启动期迁移 DDL**（表名/列名硬编码 + 值走 ? 参数）；app/ai 人工补扫无命中 |
| SSTI | 用户可编辑打印模板走 SandboxedEnvironment + 白名单，render_template_string 仅服务端自建 |
| 路径穿越 | 备份下载/删除校验 source 白名单、拒绝 ..、校验 resolved.parent == root；上传有扩展名+magic bytes+随机名 |
| 密钥 | 无硬编码 SECRET_KEY；未配置时随机生成到 instance/ 且生产拒绝启动；WMS_DISABLE_CSRF 生产直接拒绝；AI Key 用 Fernet 加密落库（实测前缀 enc:gAAA，长度 104） |
| 登录 | 会话固定防护、账号/IP 双维度锁定、IP 滑动窗口限流、开放重定向白名单、改密强度校验 |
| .git/index | 无 instance/、.env、*.db、secret_key、uploads/ 命中 |

### 6.2 S1 [P1] 标签模板存储型 XSS（warehouse 写 → admin 打开即执行）

- 位置：label_template_detail.html:520 let layoutData = {{ template.layout | default('{}') | safe }};
- 写入点：label_barcode.py:70（新增模板，layout 原样落库、不校验）、:138-145（保存布局，只校验 dict/list，json.dumps 不转义 </script>）。
- 载荷：{"c":"</script><script>new Image().src='/leak?c='+document.cookie</script>"}。
- 影响：**warehouse 角色可持久化脚本，admin 打开模板设计页即以 admin 身份执行任意请求** = 越权/会话劫持。单人环境下需要"同一账号先写后看"（风险下降），但角色边界存在时是实打实提权链；若按多用户口径应升 P0。
- 建议：|safe → |tojson；写入侧 json.loads 校验并规范化；回归测试断言响应中不出现裸 </script>。

### 6.3 S2 [P2] 报表 AI 洞察未转义直接拼 innerHTML

report_dashboard.html:334-341 把 LLM 返回文本逐行拼进 html 后 innerHTML，无 escapeHtml；数据源 report.py:167-210 原样返回 LLM 文本。若模型被污染/复述业务数据中的 <img onerror>，可在任意登录用户浏览器执行。
建议：escapeHtml(line) 或统一走 renderMarkdown（其先 escape）。

### 6.4 S3 [P2] CSRF 豁免与 Web 会话鉴权叠加（11 端点 + 前缀批量豁免）

print_queue.py:549、app.py:32124、app.py:3433、mobile.py 8 条，另有 app.py:3463-3467 按 URL 前缀批量豁免 13 条 /mobile/api/*。SameSite=Lax 缓解但不能替代 token。
建议：豁免端点强制 Bearer-only（无会话回退），Web 会话分支必须带 CSRF。

### 6.5 S4 [P2] /api/login 缺 IP 级限流

原生 API 登录（native_api.py:899）没有 Web 侧同款 IP 滑动窗口；login_log 中 518 次失败（含 SQL 注入载荷用户名）全部来自 127.0.0.1，说明系统被当作靶子扫过。参数化挡住了注入，但**慢速爆破仍可行**。
建议：与 Web 登录共用 rate_limit；nginx 层 fail2ban。

### 6.6 S5 [P1] AI 大模型端点走明文 HTTP（公网）

- 证据：system_setting.ai_llm_base_url = http://81.71.29.219:7863/v1；生产启用（ai_llm_enabled=1、vision=1）；API Key 虽加密落库，但**请求时以 Bearer 明文发出**（app.py:12808-12814）。
- 影响：网络中间节点可截获 API Key、库存/单据数据、上传的送货单图片；Key 会随备份扩散。
- 建议：强制 https 或本机回环代理；启动期对"http + 非回环 endpoint"告警/拒绝。

### 6.7 S6 [P2] 会话 Cookie 未启用 Secure

生产 SESSION_COOKIE_SECURE=False + 显式 WMS_ALLOW_INSECURE_COOKIE=1（日志 757 次 CRITICAL 告警）。nginx 模板是 443 TLS + HSTS，但 HSTS 只对访问过 https 的浏览器生效；HTTP 首跳仍可能带 Cookie。
建议：确认 100% 走 443 后开启 Secure；本地调试用独立 dev 配置。

### 6.8 其余安全项（P2/P3）

| 编号 | 级别 | 问题 |
|---|---|---|
| S7 | P2 | ai/security.py 的注入检测/PII 脱敏/sanitize_markdown 全仓零调用（详见 §7） |
| S8 | P2 | lint A2/A7/A8 只认 @app.route 且排除 app/ai → 42+10 条路由脱管 |
| S9 | P3 | excel-table.js:274 self-XSS；账号枚举；密码仅 6 位；options_api 500 回显；2 个死模板使用 safe 过滤器；print_fill 缺包含校验；3 处体内手工鉴权 |

---

## 7. AI 能力、测试与质量门禁（ai-quality 分册）

> 完整 evidence 见 [ai-quality.md](docs/audit/2026-10-18/ai-quality.md)。

### 7.1 AI 底线（正向）

- **AI 不直接写业务数据**：全 app/ai 无 .status='completed' / revert / complete 调用；5 类建单全部产出 status='pending'。
- **AI 路由鉴权完整**：17 个端点全 @login_required，写 LLM 的再加 @require_ai_role。
- **工具注册表设计良好**：JSON Schema（additionalProperties:false + 上下限）+ 角色白名单 + 风险级 + confirmation_required，且 confirmation 在 orchestrator 真正强制。
- **模型不持有工具执行权**：LLM 不做 function-calling 自主执行，工具由服务端按意图白名单分发，从结构上掐断"模型越权调工具"。
- **幂等与审计表齐全**：AIDraftIdempotency（唯一键 + IntegrityError 兜底）、AIRun/AIToolCall/AIDocumentAttempt 审计链完整。

### 7.2 Q1 [P1] AI-R08 "低置信度/风险人工确认"门禁三重失效

- 位置：app.py:14909-14991（门禁）、14742-14907（确认记录写入）、32456-32541（证据聚合）、models/ai.py:504-508（风险列）。
- 三重失效：
  1. 门禁依赖的 5 个 job 风险字段（duplicate_risk / low_confidence_fields / material_ambiguity / specification_conflict / high_risk_material）**全仓只有读、没有任何写入点** → 恒为默认值；
  2. 确认记录一律写成 confirmed_original/corrected，**从不产生 pending**；
  3. 门禁任何异常 return True, []（fail-open）；
  4. 证据聚合 ai_document_confirmation 在 templates/static/Android 中**零消费方**（grep 0）。
- 影响：R5"低置信度必须回退人工、禁止 AI 结果不经确认写入业务数据"**名义已实现、实际不设防**；低置信 OCR 可一键"确认原值"生成草稿；DB/JSON 异常时 100% 放行。
- 建议：OCR 落库时回写 5 个风险列 → 门禁 fail-closed → 确认页渲染证据并阻断未确认低置信字段；回归锁：confidence=0.1 的 job 不确认即不能建单。

### 7.3 Q2 [P1] 幂等 processing 槽位无 TTL，崩溃即永久锁死业务键

draft_idempotency.py:117-148：先落 processing 并 commit，崩溃/被 kill 后永久停留；同业务键后续请求一律"请勿重复提交"，无超时接管、无管理端重置。
建议：加 locked_at + lease 超时接管；提供 admin 重置。

### 7.4 Q3 [P2] 规则 A1–A14 覆盖缺口（本次最有价值的定量结论）

**14/14 条规则都有真实 scan 实现（非空壳）**，但覆盖面有 6 处系统性缺口：

| 规则 | 缺口 |
|---|---|
| A2 / A6 / A7 / A8 / A9 | **整体豁免 app/ai**（74 py / 2.2 万行）——增长最快、调 LLM、会被注入的模块恰恰豁免最多 |
| A3 / A4 / A5 | 只扫 app/static/js 10 个文件；136 个模板内联脚本零覆盖（实测模板内 199 处 alert、4 处 console.log） |
| A2 / A8 | 只认 @app.route，不认 @bp.post / @xx_bp.route（17+7 条路由盲区） |
| A13 | 只认 ^###，台账 12/74 条用 ## 绕过 |
| 全量棘轮 | 基线允许 a8=66 / a9=217 / a10=102 / a14=32，**共 417 处存量违规**；季度 -10% 需约 2.5 年清零 |
| A8 实际覆盖 | 334 写路由，仅 46 个 BaseModel、27 处 model_validate、**279 处 # pydantic:reason= 书面豁免** |

### 7.5 Q4 [P2] 测试有效性：约 1/4 是源码字符串断言

- 4,529 个 test 函数、13,865 个 assert；但 675 个 CI 执行文件中 **167 个（24.7%，队友口径 25.9%）不 import app、不发 HTTP**，只 read_text() 后 assert 字符串。
- 引用 ai.* 的测试仅 16–19 个（AI 74 文件 / 2.2 万行）。
- 典型：test_bug_2026_09_13_011 全文 10 行，断言 "material.stock" not in block —— 正是 A11 lint 的 Python 复写，无法发现"传错仓库/消费点漏检"（本轮 AI 盘点 P1 即漏网）。
- 正面样本：test_bug_2026_09_27_001 用 node 真实执行模板抽出的 JS 片段。
- 建议：静态断言测试打标单列；库存/草稿/确认链路补 client 级行为测试。

### 7.6 Q5 [P2] 9 个 verify_ai_* 脚本在 CI 中从不执行

scripts/verify_ai_*.py 共 66 个，verify_ai_all.py --level core 只跑 58 个；--level full 无任何 workflow 调用 → 9 个永不执行，其中包含 **verify_ai_cross_user_isolation**（跨用户越权）与 **verify_ai_photo_document_flow**（拍照单据链路）——正是本报告 P1 相关的两条校验。verify_stability_gate.py 本身也不在 CI。

### 7.7 其余 AI/质量项（编号 Q6–Q14 为本节序号，不是仓库规则 A6–A14）

| 编号 | 级别 | 问题 |
|---|---|---|
| Q6 | P2 | 置信度阈值三处漂移（0.80 / 0.85 / 0.85），且缺省 confidence=0 → 指标恒告警 |
| Q7 | P2 | ai/security.py 注入防护与 PII 脱敏零调用（死代码） |
| Q8 | P2 | chat/warehouse_assistant 无速率/配额，成本控制只在 Agent 预算内 |
| Q9 | P2 | 台账 AI-C05/AI-R08 标记"已完成"但实现未接线（虚高） |
| Q10 | P3 | 蓝图路由不被 A2/A8 识别（当前均已鉴权） |
| Q11 | P3 | 确认令牌 expires_minutes 未 clamp；ai_run_id 未校验归属 |
| Q12 | P3 | AI v2 只读工具端点仅 login_required，未按角色收窄 |
| Q13 | P3 | 死调用 _ai_dispatch_registered_tool('stock_query')（注册表无此工具） |
| Q14 | P3 | CI 注释内测试数量过时（362/178/58 vs 实际 484/191/66） |

---

## 8. 前端 / 模板 / Android（Lead 补审）

> **说明**：原定 frontend 分册的队友在"证据已收集、开始写报告"阶段中断，未落盘。本节由 Lead 用同一套扫描与抽样补做，覆盖度低于其它域（模板 136 个做全量正则 + 8 个抽样精读；Android 仅配置/存储/分页层），结论以标注为限。

### 8.1 正向（先说不好的对立面）

| 项 | 证据 |
|---|---|
| §二 仓库必填**已落实**在出入库主表单 | in_order_add.html:567 select required + 1464-1481 JS 校验 + 默认仓；out_order_add.html:557 + 1290 |
| 模板 CSRF | 30 个 post 表单**逐表单核对 0 缺** csrf_token |
| 全局 CSRF 注入 | base.html:47-79 包装 window.fetch 自动加 X-CSRFToken；2298-2345 每 25 分钟刷新 |
| Android 明文管控 | network_security_config.xml：release base-config cleartext=false，仅放行 127.0.0.1/localhost/10.0.2.2；debug-overrides 才全放开 |
| Android Token 存储 | EncryptedSharedPreferences + MasterKey AES256_GCM，损坏时降级为"待登录"并删损坏文件（WmsRepository.kt:84-131） |
| Android 分页意识 | WmsRepository.kt:453-525 显式 pageSize/total_pages（R1 注释在代码里） |
| Android 异常处理 | 121 处 runCatching/try；DataStore 超时降级（BUG-2026-10-002） |

### 8.2 F1 [P2] 45 个模板、130 处原生写 fetch，违反 AGENTS §四

- 实测：130 处 fetch(..., {method:POST/PUT/DELETE})，分布 45 个模板（check.html 6、mobile_scan.html 6、adjustment.html 5、after_sale_out.html 5、base.html 5…）。
- 背景：F3.7（2026-10-12）把模板内联 fetch 设为 **warn 模式**，实测 166 处，"观察 3 周后定棘轮基线"——3 周后不降反升。
- 影响：绕过 WMS.api.* 的统一错误处理/重试/token 刷新；CSRF 由 base.html 拦截器兜底，**不是安全漏洞**，但治理承诺失效，后续任何 API 契约变更都要改 45 个文件。
- 建议：按文件分批迁移到 WMS.api.post；把"模板内写 fetch 计数"纳入 lint 棘轮（只许减）。

### 8.3 F2 [P2] 121 块内联脚本、199 处 alert：规则扫不到、测试只能正则

- 132 个模板中 121 个含内联 script（base.html 5 块）；模板内实测 199 处 alert(、4 处 console.log。
- A3/A4/A5 只扫 app/static/js 10 个文件 → 这些全部漏检（见 §7.4）。
- 建议：抽公共 JS 到 static；模板内联纳入 A3/A4（warn → strict）。

### 8.4 F3 [P2] 21 个模板用 innerHTML 拼接数据

- 21 个模板同时出现 .innerHTML = 与模板字符串插值（adjustment_add、after_sale_out_add、ai_* 工作台、in_order_detail、opening_stock、report_view…）。
- 已确认可达的 2 处：label_template_detail（P1 XSS，§6.2）、report_dashboard（P2，§6.3）；其余需逐点看数据来源，本轮未逐一判定（**风险提示**）。
- 建议：统一 escapeHtml/textContent；对 AI 输出强制走 renderMarkdown（其先 escape）；加 CSP 作为兜底。

### 8.5 F4 [P3] mobile_scan.html 是唯一没有 page_size 的列表页

其余列表页共用 _list_macros.html 的 pager（per_page_options 20/50/100/200，R1 合规）。mobile_scan 的列表数据量小，属轻微。

### 8.6 F5 [P3] 6 个死模板，其中 2 个带 |safe

print_in_with_html.html / print_out_with_html.html 用 |safe 内联整段 HTML（当前 0 引用）；若将来被启用，就是一个新的 XSS 面。连同 bom_detail/check_detail/requisition_detail/transfer_detail 一并删除或标注 DEPRECATED。

### 8.7 Android 残余风险（风险提示）

- debug-overrides 允许任意明文 HTTP：构建纪律要求 release 包不得带 debuggable（当前 CI 只 assembleRelease，未见显式校验 debuggable=false，建议加一条 aapt dump badging 断言）。
- baseUrl 由用户输入（RetrofitClient.setBaseUrl）：release 下非白名单 http 会被系统拒绝，但错误信息需保持可读。
- 未审：3 万行 Kotlin 的 UI 状态机、并发、离线草稿一致性。

---

## 9. 架构与可维护性

### 9.1 A1 [P1] app.py 仍是 35,995 行单体，A10 只对新代码生效

- 证据：903 顶层函数 / 92 个 @app.route / 31,579 行（87.7%）在函数体内 / auto_migrate_database() 单函数 1,311 行；模块级还内嵌 SYSTEM_SETTING_GROUPS 等数千行配置字面量。
- 对照：routes/ 已迁出 610 路由，形成**双轨**；A10 只拦"新增 @app.route"，存量 92 个不受约束（lint 基线 a10=102）。
- 影响：跨模块改动导航成本高、评审困难、合并冲突概率高；迁移逻辑无法单测（只能整库跑）。
- 建议：按域继续迁移（迁完即删 app.py 对应段）；A10 升级为"app.py 行数棘轮"（只许减）；auto_migrate_database 拆成编号步骤函数。

### 9.2 A2 [P2] A8 名义存在、实际覆盖率 <10%

334 写路由 / 46 个 BaseModel / 27 处 model_validate / **279 处 pydantic:reason= 书面豁免**（subcontract 45、in_order 23、out_order 15、transfer 14…）。
建议：按"金额/数量/状态迁移"优先级分批迁移，并把免责注释纳入计数棘轮。

### 9.3 A3 [P2] 死模板 6 个

见 §8.6。维护者误以为有独立详情页。

### 9.4 A4 [P3] 冗余索引

stock_transaction 上 idx_stock_txn_material 与 idx_stock_transaction_material_id 完全重复；idx_stock_txn_ref 与 idx_stock_transaction_ref 重复。每次写流水多维护 2 个索引，无查询收益。

### 9.5 A5 [P3] 同功能多实现

- 委外发料：app.py:7627 vs subcontract.py:308（§5.4）
- 审批：approval.py:76 vs purchase_request.py:622
- 打印：print_queue / print_routing / print_template_center 三套入口
- 库存预校验：各路由自写 vs 入口层

### 9.6 A6 [P2] 代码量/业务量失衡

1,301 物料 / 2 用户 / 4 仓库 / 0 盘点 / 0 调拨 / 0 调整，对应 20.5 万行、97 表、688 测试、189 脚本、4 条 CI。
**建议**：做一次"功能-使用率"盘点，冻结/下线从未使用的模块（调拨、盘点、调整、委外、合同、BOM 中至少一半生产零使用），把维护面压到实际使用的 20%。

---

## 10. 运维 / 部署（上轮遗留项复核 + 本轮新增）

### 10.1 O1 [P2] 健康检查日志路径错误（上轮 A11；2026-10-18 已修，§16）

scripts/health_check.ps1:114 读 InstallDir 下的 logs/app.log，应用实际写 InstallDir/app/logs/app.log（config.py:29）。健康检查会误报"日志不存在"。

### 10.2 O2 [P3] app/wms.bat、app/wms.cmd 指向不存在的 app/install.bat（上轮 A12；2026-10-18 已修，§16）

两文件第 2 行 call "%~dp0install.bat"，app/install.bat 不存在（根目录才有）。

### 10.3 O3 [P2] 配置非法值在 import 期炸（上轮 A16；2026-10-18 已修，§16）

config.py:57 int(os.environ.get('BACKUP_RETENTION_DAYS','30'))；空串/非数字 → ValueError，调度器的"回退 30 天"永远执行不到（REMEMBER_COOKIE_DURATION 同型）。

### 10.4 O4 [P3] clone 脚本不查退出码（上轮 A13；2026-10-18 已修，§16）

tools/clone_wms_main.ps1 全程 **0 处 LASTEXITCODE** 检查，末尾仍打印"已准备 main 工作区"。

### 10.5 O5 [P2] 自动更新不要求备份成功（上轮 A15；2026-10-18 已修，§16）

auto_update.py:176-216 的 backup_database() 失败只 log("[警告]…")；main() 在 430 行无条件调用后直接 pull。当前由 WMS_SKIP_AUTO_UPDATE=1 规避，但一旦启用就是"备份失败也更新"。

### 10.6 O6 [P2] README 库存口径未限定库位开关（上轮 A17；2026-10-18 已修，§16）

README.md:93 写"总账 = Σ库位账 = Σ流水"，而权威文档明确"关闭库位时只验证 ①=Σ③"。照 README 排查会把 2 行历史残留误判为坏账。

### 10.7 O7 [P3] 旧环境审计脚本（上轮 A18；2026-10-18 已修，§16）

scripts/deep_audit_lib.py:16 硬编码 /Coze/Drive/扣子/wms 并 os.chdir，本机不存在。

### 10.8 O8 [正向] 更新/恢复/安装链路已显著加固

- update_from_github.py：停服前完成 fetch/固定 SHA/依赖 dry-run/一致性备份；失败 git reset --keep 回退；启动健康检查核对 PID 身份。
- restore_backup.py：SQLite 一致性快照 + 核心表校验 + 运行锁（8d74f67c）。
- install.bat / install_e_wms.bat：覆盖安装失败不删已有目录（ab283c6f）。
- 这三条是上一轮 18 项里最重的 P1，已闭环——是本轮能给"无 P0"的重要前提。

### 10.9 O9 [P2] 生产/开发现场混用（新增）

见 §3.2–3.5：启动备份风暴、日志污染、438 个运行目录文件、WAL 4.1MB。

---

## 11. 跨域根因（比单条缺陷更重要）

把 6 个域、约 90 条 findings 按"根因"归并，只剩 5 个：

### T1 "单张修了、批量/旁路没修"（R6 名存实亡）

B1/B2/B3（批量三缺）、I2（多行快照）、B9（print_queue CSRF）、I4/I7/I8（旁路口径）。
仓库规则 R6 明确要求"同根因必须排查所有消费点"，但实际修复史显示：每次 BUG 只修报告点。**后果：修复数量越多，单张/批量/旁路之间的行为差越大，用户越难预测系统行为。**

### T2 "写了但没接线"（安全与治理的 fail-open）

- AI 低置信门禁：风险字段无写入点、证据无消费方、异常放行（§7.2）；
- ai/security.py 注入检测/PII 全仓零调用（§7.7）；
- 9 个 verify_ai 脚本不进 CI，verify_stability_gate.py 也不在 CI（§7.6）；
- lint A8 的 279 处书面豁免（§9.2）。
**后果：台账/文档宣称的能力与真实防护之间存在系统性落差；CI 绿色不构成"这些能力有效"的证据。**

### T3 口径分叉（全局 vs 仓库级；名称 vs ID）

AI 盘点取总账（§4.2）、serialize_material 给前端全局库存（B11）、报表/预警/库存查询的仓库判据各写一套（I7/I8/I9）、单据仓库以**名称字符串**存储（仓库改名即历史失联）、库位管理残留 2 行（§3.9）。
**后果：多仓是"声明支持"而非"处处支持"，一旦真开多仓运营就会集中爆。**

### T4 治理设施 > 业务规模（复杂度税）

20.5 万行 / 97 表 / 688 测试 / 189 脚本 / 4 CI / 271KB 台账 / 234KB BUG 基线，服务 1,301 物料 2 用户。
约 25% 的测试是源码字符串断言（§7.5）；A9 有 217 个业务函数无测试；A10/A8/A14 基线共 417 处存量。
**后果：维护者（含 AI）把大部分时间花在"证明"而不是"构建"；真实缺陷反而藏在证明的缝隙里（本轮 AI 盘点 P1 就是被"源码断言测试"放过的）。**

### T5 生产现场与开发现场混在一起

同一 LOG_FILE、同一 app/logs、同一备份目录承接了测试、AI 过程产物、审计脚本与生产运行（§3.2–3.4）。
**后果：排障时信噪比极低；一次重启循环就把 10 份正常启动快照挤掉。**

---

## 12. 整改路线图

> 原则：先"止血"（可利用/会直接出错），再"接线"（宣称的能力真正生效），最后"减负"（复杂度治理）。
> 每个动作都给出**验收标准**；由于本环境不能执行进程，验收命令供有 Python 的机器执行。

### Phase 0（本周，预计 0.5–1 人日）

| # | 动作 | 验收 |
|---|---|---|
| 0.1 | 标签模板 XSS：safe 过滤器 → tojson；写入侧 json.loads 校验 | POST 含 </script> 的 layout 后，响应 HTML 不含裸 </script><script>；页面正常渲染 |
| 0.2 | AI endpoint 改 https（或本机回环代理） | ai_llm_base_url 以 https:// 或 http://127.0.0.1 开头；启动日志无告警 |
| 0.3 | 一物多码 4 组合并 | 重启后日志出现"已建唯一索引"，sqlite_master 存在 uq_material_dedupe_key |
| 0.4 | 4 个旧审计项（O1/O2/O3/O4） | health_check 能找到日志；app/wms.bat 可用或删除；BACKUP_RETENTION_DAYS=bad 不再抛栈；clone 脚本失败即非零 |
| 0.5 | 生产日志分流 + 启动备份防抖 | 测试运行不再写 app/logs/app.log；连续重启 10 次只产生 1 份启动备份 |

### Phase 1（2 周，预计 3–5 人日）

| # | 动作 | 验收 |
|---|---|---|
| 1.1 | 批量完成/反提交补 PO 状态回写 + 下推守卫 + 仓库停用校验 + 0 成功返回 400 | 新增 3 条回归测试；回退修复后测试必红（R8） |
| 1.2 | AI 建单统一补仓库 + 盘点改仓库级账面 | AI 盘点草稿可直接完成；grep 无 material.stock 用于 system_stock |
| 1.3 | AI-R08 门禁接线（回写风险列 → fail-closed → 确认页阻断） | confidence=0.1 的 job 未确认时不能建单（回退修复后该断言失败） |
| 1.4 | 幂等 processing 加 lease 超时 | 模拟进程中断后，同业务键 N 分钟后可重试 |
| 1.5 | 业务数据初始化顺序改为"先删③再归零① + 失败即整体失败" | 注入删表异常时 ① 不变，接口返回失败 |
| 1.6 | I2 四处"按物料合计"校验 | 两行 8+8 对 A 仓 10 的反提交被拒 |

### Phase 2（1 个月，预计 6–10 人日）

| # | 动作 | 验收 |
|---|---|---|
| 2.1 | A8 迁移 Top 20 高风险写接口（金额/数量/状态），把 279 处豁免降到 <100 | lint 计数棘轮下降；新增接口 100% BaseModel |
| 2.2 | lint 覆盖面补齐：模板内联 JS 纳入 A3/A4、A2/A8 支持 blueprint、A13 放宽标题 | --full 报出当前漏掉的 console.log/alert；新规则有 golden 测试 |
| 2.3 | verify_ai_all --level full 进 CI（至少 cross_user_isolation + photo_document_flow） | CI 出现 66/66 脚本执行记录 |
| 2.4 | 测试分级：静态断言测试打 @pytest.mark.static_check 单列；核心链路补 client 级测试 | 覆盖率报告不再把静态断言计入 |
| 2.5 | 模板 130 处原生写 fetch 分批迁移到 WMS.api | 计数棘轮只降不升 |
| 2.6 | 单据仓库从"名称"改"ID + 名称快照"（或至少改名时级联） | 仓库改名后历史单据仍可筛可完成 |

### Phase 3（季度，架构治理）

| # | 动作 |
|---|---|
| 3.1 | app.py 拆分：按域迁移至 routes/，A10 升级为行数棘轮（只许减） |
| 3.2 | auto_migrate_database 拆为 migrations/ 编号步骤 + 单测 |
| 3.3 | 功能-使用率盘点，下线零使用模块（盘点/调拨/调整/委外/合同/BOM 至少一半），目标把 20.5 万行压到 8 万行以内 |
| 3.4 | 价格/成本维度决策：要么全链路接入（默认价/采购价/加权平均），要么从 UI 下线所有资金类报表 |
| 3.5 | SQLite → 服务型数据库的可行性评估；否则明确"单机上限"并写入 README |
| 3.6 | 台账瘦身：271KB 计划 + 234KB BUG 基线拆分为索引 + 分片 |

---

## 13. 上一轮审计（AUDIT-FULL-20261016）18 项复核

| 项 | 内容 | 本轮结论 | 证据 |
|---|---|---|---|
| A01/A02 | 恢复工具停机证明/结构校验 | **已闭环** | 8d74f67c；restore_backup.py 一致性快照+核心表校验+运行锁 |
| A03/A08 | 启停进程身份 | **已闭环** | 369eeea8；stop_wms_offline.bat 已改走 service_control.py |
| A04/A05 | 更新失败回退 | **已闭环** | b33ceebf；update_from_github.py 预检/回退 |
| A06 | 安装回滚保留数据 | **已闭环** | ab283c6f |
| A07 | 打包输出目录防护 | **已闭环** | 71ff441a |
| A09 | 服务配置/托管实例维护 | **已闭环** | ac18ca29 + 47d4c3f0 |
| A14 | 只读/内存库边界 | **已闭环** | 3c64f4c3 |
| A10 | 备份页看不到自动日备份 | **已修（2026-10-18）**：f7a0d257（BUG-2026-10-17-008），45+59 passed，CI 全绿 | §16 |
| A11 | 健康检查日志路径 | **已修（2026-10-18）**：75956e3a；并补 UTF-8 BOM 使 PS 5.1 可解析 | §16 / §10.1 |
| A12 | app/wms.bat 死入口 | **已修（2026-10-18）**：068b93bd | §16 / §10.2 |
| A13 | clone 脚本未查退出码 | **已修（2026-10-18）**：af599d5b | §16 / §10.4 |
| A15 | 自动更新不要求备份成功 | **已修（2026-10-18）**：836018d5，备份失败跳过 pull | §16 / §10.5 |
| A16 | 配置解析 | **已修（2026-10-18）**：21b288ad，非法值回退默认 | §16 / §10.3 |
| A17 | README 库存口径 | **已修（2026-10-18）**：5853b3f3，按库位开关分档 | §16 / §10.6 |
| A18 | 旧环境审计脚本 | **已修（2026-10-18）**：1d5f0989，12 个脚本改相对根 | §16 / §10.7 |

**结论（审计时点）：7 项闭环、1 项代码完成待闭环、10 项待修**。上一轮的 P1 已全部关闭，剩余为 P2/P3 运维与文档卫生项——这是本轮"无 P0"判断的重要前提。

> 复核补记（2026-10-18 收尾）：A10 已随 f7a0d257 提交；A11/A12/A13/A15/A16/A17/A18 全部修复并各带回归测试（§16）；**最终 18/18 项闭环**。另有整改中新发现的 CP936 门禁崩溃（BUG-2026-10-17-010）同批修复。当前 HEAD 046ca9f2，四条工作流全绿。

---

## 14. 附录

### A. 关键数字速查

| 指标 | 值 |
|---|---|
| 本地/上游 HEAD | 审计时 0f8442b3（落后 350cfd40 四个提交）；**整改后 046ca9f2** |
| 已跟踪文件 | 1,730 |
| app/ 代码量 | 429 文件 / 205,303 行 |
| app.py | 35,995 行 / 903 函数 / 92 路由 / auto_migrate 1,311 行 |
| 路由 | 709；写路由 360 |
| 测试 | 688 文件 / 4,529 test 函数 / 13,865 assert；静态断言约 167（24.7%） |
| lint | 14/14 实现；存量基线 417；A8 豁免 279 |
| 生产库 | 97 表 / 1,301 物料 / 3,760 流水 / 605+593 单据 / 4 仓 / 2 用户 / 4.7MB+4.1MB WAL |
| 账务一致性 | 总账 vs 流水 0 差异；0 负库存；0 悬挂流水；19 行 FK 违规（ai_cleanup_log） |
| CI | 审计时：4 条工作流最近 main 全绿（350cfd40）；**整改后：全绿（046ca9f2）** |
| 运行现场 | app/logs 438 文件；app/backups 30 个（20 个 sidecar）；37 秒 10 次启动备份 |

### B. 证据与分册

- 本报告：docs/audit/WMS_FULL_AUDIT_2026-10-18.md
- 分册：docs/audit/2026-10-18/backend-flow.md（17 条）、inventory.md（17 条）、security.md（14 条）、ai-quality.md（18 条）
- 上一轮：docs/audit/WMS_FULL_AUDIT_20261016.md、docs/audit/WMS_FULL_AUDIT_FIXES_20261016.md

### C. 未覆盖 / 存疑（诚实边界）

1. **审计阶段**未运行测试/服务/脚本（环境禁止）——所有"运行时"结论均标 [需运行验证]；**整改阶段**已运行 pytest/lint/pre-commit/PowerShell 健康检查（§16、§16.1）。
2. 未做渗透测试；XSS/越权为静态可达性判定。
3. Android 3 万行 Kotlin 只审了配置/存储/分页/异常层。
4. 271KB AI 台账未通读（grep 168 条"已完成" + 抽样 2 条确认虚高）。
5. 上游 4 个提交未审。
6. 字段级 IDOR 未逐条验证（security 分册已声明）。
7. native_api.py（4,115 行、41 路由）只做装饰器/CSRF 清单级扫描，未逐函数审计移动端入库/出库/盘点的幂等与库存写入。

### D. 复现方法（在有 Python 的机器上）

    # 1) 静态规则（仓库自带）
    python scripts/lint_wms_rules.py --full --full-gate
    # 2) 三账恒等式（只读）
    python scripts/verify_inventory_identity.py --db app/instance/inventory.db
    # 3) 全量测试（约 20 分钟）
    python -m pytest tests/ -q
    # 4) CI 门禁
    python scripts/check_ci_green.py

---

## 15. 勘误（2026-10-18 复核）

1. **§1.1 工作树状态错误**：首版据 .git/index 与工作区 blob 哈希一致判断"干净"，但**索引本身包含已 staged 的改动**，该比对无法发现 staged 未提交内容。git status --porcelain -b 实测：16 个文件已 staged（A10/F08 备份目录改造），1 个 JSON 未暂存改动；main...origin/main 同步标记基于本地远端引用，实际 fetch 后确认落后上游 4 个提交（350cfd40）。结论不受影响（这 4 个提交只改 hooks/check_ci_green/台账），但"基线 = 已提交代码"的说法对 A10 不成立——A10 的实现在工作区与索引里，不在 HEAD 里。
2. **§13 A10 状态**：由"代码完成待确认"更正为"实现已成型但未提交（16 文件 staged，台账仍写未修复）"。该 BUG 原编号 006 与上游冲突，整改时改为 **BUG-2026-10-17-008**（见 §16）。

## 16. 整改记录（2026-10-18，A10–A18 与门禁修复）

> 本节记录报告交付后立即执行的整改。审计正文（§4–§13）保留审计时点的事实，不回写。

| 审计项 | 提交 | 主要变更 | 验证 | 状态 |
|---|---|---|---|---|
| A10 备份页看不到自动日备份 | f7a0d257（BUG-2026-10-17-008） | 固定三来源（每日/手动/更新）注册，只读完整性校验，路径穿越与受保护库校验，模板+JS | test_audit_backup_catalog 45 passed；backup_scheduler+catalog 59 passed；lint 0 | 已修（生产需重启） |
| A11 健康检查日志路径 | 75956e3a（F09-F01） | 同时探测 app/logs 与扁平 logs；补 UTF-8 BOM 修 PowerShell 5.1 中文解析 | 新增 4 用例；PS 5.1 实测运行，日志项 PASS | 已修 |
| A12 app/wms.bat 死入口 | 068b93bd（F09-F02） | 指向根 install.bat 并校验存在，保留 CRLF/退出码 | 新增 3 用例 | 已修 |
| A13 clone 脚本未查退出码 | af599d5b（F09-F03） | Invoke-Git 包装 + 末尾本地/远端 SHA 核对 | 新增 4 用例（含 Windows 行为） | 已修 |
| A15 自动更新不要求备份成功 | 836018d5（F09-F05） | backup_database 返回 bool，失败跳过 pull | 新增 4 用例（真实/损坏/缺失库） | 已修 |
| A16 配置解析 | 21b288ad（F09-F06） | _env_int 安全解析，非法/越界回退 | 新增 11 用例（子进程隔离） | 已修 |
| A17 README 库存口径 | 5853b3f3（F09-F07） | 三账恒等式按库位开关分档并回指权威文档 | 新增 2 用例 | 已修 |
| A18 旧环境审计脚本 | 1d5f0989（F09-F08） | 12 个脚本改 Path(__file__) 相对根 | 新增 3 用例；12 文件 py_compile 通过 | 已修 |

| pre-commit 编码 | ad1e1789（BUG-2026-10-17-010） | lint_wms_rules / lint_no_raw_post_fetch 增加 _configure_stdio + _glyph，GBK 下不再因 ⚠/✓/✗ 崩溃；3 处 git 子进程补 encoding=utf-8 | test_console_encoding_gbk 5 passed；真实钩子 HOOK_EXIT=0（默认 cp936）；CI 39057235881 全绿 | 已修 |
| CI 门禁 | e935ce17 | gitleaks-action@v2 黑盒失败（本地同版本对同一区间 0 命中），改为固定版本 8.30.1 二进制 + 显式 before..after 区间（schedule/manual 退回全历史） | WMS CI 39055291813 全绿（10/10 job） | 已修 |

说明：
- 每个修复都是独立 atomic commit，可单独 revert；均新增“回退后必红”的回归测试。
- 过程中 a76e30a5 与 a8894fad 两次 WMS CI 红，均定位在 gitleaks 步骤（不是代码回归）：本地用同版本 8.30.1 对同一提交区间与全目录扫描均 0 命中。修复见上表最后一行。
- 整改过程中新发现并同批修复第 9 项：cp936 控制台下 pre-commit 因打印 ⚠ 崩溃、把脚本异常误判为“发现违规”而拒绝所有提交（BUG-2026-10-17-010）。它与 BUG-2026-10-17-006/007 同根因，现已让两个 lint 脚本按输出流编码降级。
- 由于红门禁会阻断“修复 CI 本身”的推送，两次推送使用了仓库文档化的逃生舱 WMS_SKIP_CI_GATE=1，并在推送后立即以 e935ce17 的四条工作流全绿补证；这不是常态做法。
- A14 已在 2026-10-16 由 3c64f4c3 闭环，本批不重复。
- 生产生效边界：备份页（模板）需要重启 WMS 生效（R3）；其余脚本为“下次调用读新文件”。

### 16.1 收尾状态（2026-10-18）

| 项 | 值 |
|---|---|
| 最终 HEAD | `046ca9f2`（本地 = origin/main，工作树干净） |
| 已推送提交 | 14 个：10 个代码/CI 修复（A10、A11–A18、CP936、gitleaks 门禁）+ 4 个台账/报告 |
| CI | WMS CI 39057678030（9/9 job success）、AI Verification 39057677940、Perf 39057677981 均 @046ca9f2；Android 217ac3bd（paths 过滤的最近一次，符合既定语义） |
| 台账 | BUG-2026-10-17-008（A10）、-009（A11–A18）、-010（CP936）均"已修复"；008 生效确认=生产待重启，009/010=CI 已确认 |
| 本地验证 | 全量 pytest 3837 passed / 347 skipped / 3 环境性失败（node 不在 PATH、gbk 解码 node 输出；Linux CI 不复现）；lint 0 违规；--full-gate 0 新增（A8/A9/A10 存量各降 5/4/8） |

**仍未闭环（本轮范围外，按优先级）**：

1. 标签模板存储型 XSS（§6.2）——唯一可利用提权链；
2. AI 建单 5 类草稿仓库层 + 盘点账本口径（§4.2）；
3. AI-R08 人工确认门禁接线（§7.2）；
4. 批量入口三处门禁：PO 状态回写、下游下推守卫、仓库停用 + 0 成功返回失败（§5.1–5.3）；
5. AI 大模型端点 HTTPS（§6.6）；
6. 一物多码 4 组合并、建立 DB 级唯一索引（§3.7）；
7. 运行现场分区与启动备份防抖（§3.3–3.5）；
8. §12 的 Phase 2/3：规则覆盖补齐、app.py 拆分、零使用模块下线、价格维度决策。

### 16.2 第二轮整改（审计 §4–§9，2026-10-18）

> 用户要求「全面修复报告上的问题，不修 app.py 拆分 / A10 行数棘轮」。本轮按域推进，每项独立提交。

| 编号 | 问题 | 提交 | 验证 |
|---|---|---|---|
| 011-F01 | 标签模板存储型 XSS（safe 过滤器内联 layout + 写入不校验） | 2b06a115 | 真实渲染 + node 执行 8 用例（含脚本结束标签载荷）；写入侧 5 用例 |
| 011-F02 | 报表 AI 洞察未转义拼 innerHTML | b238a6ad | 2 用例（洞察行/错误文案） |
| 011-F03 | AI 5 类草稿无仓库、盘点取全局总账 | 1b870eda | 5 用例（解析顺序/停用仓/默认仓/仓库级账面） |
| 011-F04 | 幂等 processing 无租约，崩溃即锁死 | 64dc6bb4 | 3 用例（超时接管/新鲜冲突/环境变量） |
| 011-F05 | 低置信度确认门禁三重失效 | 9f33205d | 4 用例（写风险标记/未确认拒绝/确认后放行/缺失任务拒绝） |
| 011-F06 | 置信度阈值 0.80/0.85 漂移 | 86e2345b | 3 用例（单一定义/再导出/禁止 confidence<0.85） |
| 011-F07 | lint A2 只认 @app.route 且豁免 app/ai；A13 只认 ### | 2c4c22d6 | 4 用例（bp.post/route 命中、鉴权放行、AI 不豁免） |
| 011-F08 | 跨用户隔离脚本从不进 CI | 3e44010b | verify_ai_all core 59 个脚本全过 |
| 011-F09 | chat/warehouse_assistant 无限流 | 09572ed4 | 3 用例（阈值/隔离/窗口过期） |
| 012-F01 | 批量完成/反提交不回写采购订单状态 | 034ceaae | 行为用例：批量完成后 PO=completed |
| 012-F02 | 批量反提交缺下推守卫 | 034ceaae | 行为用例：有 active 下推时 reverted=0、单据仍 completed |
| 012-F03 | 批量出库不校验停用仓、0 成功仍 success | 034ceaae | 2 用例（停用仓拒绝；0 成功 400） |
| 012-F04 | 初始化先归零①再删③、失败被吞 | 1a133f3d | 2 用例（正常顺序；删流水失败时总账不变） |
| 012-F05 | 启动备份风暴、sidecar 残留、测试污染生产日志 | 311ff643 / 14a55e64 | 2 用例（防抖；保留数与 sidecar）；conftest 日志隔离 |
| — | 死模板清理 | b8d616aa / 2d84f579 | 先删除、因空状态测试依赖随即恢复；当前保留 |

> CI 证据（2026-10-18）：WMS CI 39069539558（9/9 job）、AI Verification 39069539557、Perf 39069539570 均 success @bdda0826；Android APK Build 为 1eef6223 的重跑 success（首次 unit-test 失败为 flake，重跑通过）。

**本轮明确未做（如实记录）**：

1. **app.py 按域拆分 / A10 行数棘轮**：用户明确排除（风险高）。
2. **模板内联原生写 fetch 130 处 / A8 pydantic 279 处书面豁免**：大规模机械改造，需逐页回归与独立排期；本轮未动（列入 Phase 2）。
3. **一物多码 4 组合并、库位账 2 行残留**：涉及生产数据，按 AGENTS §一保留人工确认，本轮只登记不执行。
4. **AI 大模型端点 HTTPS（§6.6）**：需改生产 system_setting/网关，属部署配置变更，未擅自修改。
5. **verify_ai_all --level full 剩余 2 个失败脚本**（photo_document_flow、stage3_agents 补货 Agent）：本轮只把通过的 cross_user_isolation 并入 core，其余待单独定位。

### 16.3 第三批深化（2026-10-18）

| 编号 | 问题 | 提交 | 验证 |
|---|---|---|---|
| 013-F01 | 多行同物料反提交/售后/批量反审按单行快照校验，合计可扣成负账（I2） | de097844 | 2 用例：8+8 对单仓 10，单张反提交拒绝、批量跳过，单据与总账不变 |
| 013-F02 | 旧 /api/subcontract/quick_issue 无锁/无幂等（P1 §5.4） | b16c08e3 | 加写锁 + 10 秒相同明细重放；回归 1 用例（重复提交只扣一次） |
| 013-F03 | AI 端点明文 HTTP（§6.6） | b16c08e3 | 首次调用 CRITICAL 告警 + 2 用例覆盖判定；生产配置未改 |
| 013-F04 | 一物多码/库位残留/FK 缺少安全修复工具 | f5aefcdb | scripts/data_repairs.py 默认只读；2 用例（dry-run 不写库、--apply-fk 需 --yes） |
| 013-F05 | 模板原生写 fetch / pydantic 豁免无防增长约束 | 287f1f36 | 棘轮 ≤157 / ≤279，只许减；2 用例 |
| 013-F06 | 16 处用户可见 4 连问号乱码（§5.5） | b16c08e3 | 全部修复 + 1 条全仓扫描守卫 |
| 013-F07 | /print_queue/jobs 的 CSRF 豁免对 Web 会话也生效（S3） | a827fa2f | Web 会话无 token 400、Bearer 走令牌；2 用例 |

**第三批后仍未做**：一物多码 4 组合并（需人工确认生产数据；工具已就绪：先 `python scripts/data_repairs.py --db <生产库>` 只读复核，再走页面合并）；模板 fetch 130+/pydantic 279 的机械迁移（已设棘轮，留 Phase 2）。

**报告完。**
