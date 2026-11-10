# 549a744d 实际 CI 失败后续核查

本记录只描述合成隔离验证，不代表生产状态。本批本机统一验证及整批回退已完成；提交、推送与精确新 SHA 的 CI 分别验收，未验收前不计交付。

## 最终本机验收（69 文件）

- 本次修改按 4 个 BUG 台账条目归类，不能把失败用例数或文件数算作 BUG 数。39 个完整测试模块一次联合运行：**762 passed、53 subtests passed、0 failed、0 skipped**，234.00 秒；测试清单保存在 `ci-final-unified-manifest.json`，日志为 `logs/ci-r8-current-restored.log`。
- 98 模块扩展诊断曾出现 BOM 的旧预览期望、领料测试提取旧函数签名、销售金额 VM 漏载真实 money.js、旧委外 WW 前缀缺失。全仓同类扫描同时修正另一处 one_action 函数提取；失败模块先 303 passed，再全部纳入上述统一回归。前两组曾为 376 passed/1 failed 和 642 passed，第三组为 458 passed/136 failed；这些历史诊断数字与最终联合回归重叠，不累计。
- 编号保留旧 WW 格式；分配不提前 flush 调用者尚未填完整的单据，历史扫描包含本事务未 flush 的号码。通过持久序列锁串行分配，不额外锁历史单据行，避免与编辑/删除形成相反的加锁顺序。合成 SQLite 的双连接及双进程并发均实际执行；其他数据库只验证了 SQL 生成，未声明实际数据库验收通过。
- 在新建私有 Git 仓库将全部 69 文件分成 3 个组件提交，逆序全部 revert，再逆序撤销这些 revert；基线及候选逐文件 SHA-256 完全一致。回退实现运行新回归锁为 **48 failed/19 passed**，其中 2 项是回退后新增接口不存在，其余为行为断言失败；恢复后为上述 762 passed。共享 `C:\wms` 没有执行回退、stash、reset 或清理。
- 回退证明为 `ci-followup-r8-number-uf6azjxk/r8-proof.json`。旧版和恢复版的内核回执均 closed，Job 清空、WFP 过滤回收、隔离身份回收、受保护摘要不变；没有真实网络或生产数据库操作。验证结果写回文档属于验证后的证据补记，业务和测试源码摘要未改变。
- 最终暂存规则 **0 违规**，全量棘轮/A11 通过（A8=61、A9=199、A10=94，均低于既有上限；未隐藏历史存量）；裸 fetch 的修改范围检查、严格 AI 台账、纯源码副本编码、Python 语法和 `git diff --check` 通过。使用临时索引预检，共享索引字节未变。
- Linux 特有的 Git/不可写源目录与预上线目录校验仍须通过新 SHA 的实际 CI；完整 Linux unit/verify/AI 没有被本机子集替代。此前 549a744d 的远端失败仍是事实，不能以本机通过或旧 Android 绿灯宣布新 SHA 全绿。

## 精确基线

- main / HEAD：`549a744de4597b4cfa80ade74083f489e021b588`。
- [WMS CI #2098](https://github.com/SIX2090/wms/actions/runs/42648422916)：failure。smoke、browser-material-entry 成功；lint-and-static、unit 三片、verify 四片失败。
- [WMS AI Verification #2393](https://github.com/SIX2090/wms/actions/runs/42648422907)：failure。用户提供完整脚本汇总为 59 / 58 passed / 1 failed，唯一失败脚本为启动自动更新验证；静态步骤另有失败。
- gate 正确传播上述失败，不能修改为忽略红色子任务。GitHub 日志下载 API 当前匿名请求返回 403 / Must have admin rights to Repository；检查注解 API 可读，已经保存各 verify 的失败文件名。

## 已复现并修复的项

| 项目 | 修改前证据 | 当前验证与边界 |
|---|---|---|
| 自动更新验证仍要求自动 stash | 实际脚本 exit 1，仅旧 stash 断言失败 | 新版 exit 0；实际 main AST 执行 4 种旧配置 × 4 种场景，脏工作区不备份、不 stash、不 pull，备份失败/期间出现改动不 pull，干净时只 ff-only |
| 单号静态门禁钉住 `last_no` 变量 | 静态诊断实际失败 BUG-NEW-015 | 改为执行真实数字后缀读取函数；9999/10000/乱序/无效后缀和 IN/BOM 长度，截断/取最小/恒零/断开调用变异均必须失败 |
| standalone 文件被误派给 pytest | 新分类回归旧版 7 failed / 3 passed；真实 CI 返回零收集 exit 5 | 检查模块级函数/类 AST；嵌套 unittest main、字符串和注释由 Python 执行；不删非空和失败码保护 |
| 部署暂停开关覆盖正常模拟路径 | 冻结收件人 3 failed，模拟 HTTP 从未被调用 | 合成容器使用正常业务开关，仍保留 OS 网络隔离；同三项 passed |
| 旧微信分享/清理 fixture | 分享 2 failed / 2 passed；清理 4 failed / 1 passed | queued_v2 新队列与 pending 人工核对分别验证；新建共享内存库的独立连接保留清理事务保护；新增 StaticPool 拒绝且图片保留 |
| 开仓负库存提示 fixture 漏 warehouse_aliases | 26 项中 18 failed | 提取真实别名解析到合成环境，26 passed；没有改变仓库归属或业务规则 |
| 前端临时 JS 写入只读源码目录 | 扩展主单测在写文件时 PermissionError，未执行断言 | 全仓找到 7 个同类 harness，统一使用独占 TemporaryDirectory；与启动/编号门禁相邻共 63 passed、4 subtests passed |
| 详情页 VM 缺少真实金额组件 | 扩展主单测复制行时报 window is not defined | 加载实际 money.js 并绑定 window；详情页列排序/隐藏/复制与委外、销售相邻共 80 passed |

13 文件组合运行：139 passed / 26 subtests passed / 0 failed，42.69 秒测试时间。其他独立重复运行不叠加计数。

手机识物另有真实兼容性修复（BUG-2026-11-10-002）：[SQLite 3.44.0 发布记录](https://www.sqlite.org/releaselog/3_44_0.html) 证实 CONCAT 在该版本新增。新测试在独有内存连接禁用该能力，旧版中文匹配/无结果两项失败；改用 SQLAlchemy 字符串拼接并拒绝空字段匹配后，新测试及原接口/路由/隔离相邻四文件 21 passed。证据为 `logs/ci-mobile-sqlite-before.log` 和 `logs/ci-mobile-sqlite-after-adjacent.log`，及对应回执。没有通过更新本机 SQLite 或放宽断言掩盖兼容性问题。

## 仍未通过 / 未验收

- 原生候选实验入口已修复：旧脚本重写已删除的内联锁，并含旧回执应重放/应拒绝等互相冲突的期待。现在直接运行真实实现的事务、租约、合并协议、AI 重放和双连接并发五个完整模块；56 passed、0 skipped。缺少完整清单或出现跳过不能成功。新增两项无请求号旧客户端兼容和三项未知旧回执保留原文/拒绝重放，用于锁定已批准 B2 约定。没有以旧候选替换产品实现。证据：`logs/ci-native-current-entry-56.*`。
- 原真实单号检查的同预览冲突、删号复用两项已实际修复，原 10 项现全部通过，失败断言保留。正式代码新增事务内持久序列并统一新增/编辑编号边界，11 模块 195 passed；另 8 项历史编号检查通过。新旧对照见下节。完整消费点扩大回归及本次新增改动的整批回退仍在进行，不能据此宣布全系统交付。
- 手机识物已完成不依赖本机 SQLite 版本的复现和修复；精确新 SHA Linux CI 仍未验收。
- 主单测按显式文件清单扩展诊断：前段 353 passed/15 failed；随后一段 638 passed/5 failed/10 errors；再下一段 64 passed/15 failed/1 skipped，均为遇错停止的诊断，不能累计为完整回归通过。其中 Windows Git 访问 NUL、缺少 PowerShell/命令解释器属于本机受限运行条件，不能据此推断 Linux 相同失败。源码目录临时写入及金额 VM 缺依赖已按上表修复。
- CI 源码镜像不携带宿主 .git：控制台编码测试改用自有新建 Git 仓库；制品检查使用控制器同一次 ls-tree 生成的不可写文件名清单，连被排除的数据路径名也保留，但不读取其内容。清单拒绝/保留检查 6 passed，源文件导出契约已纳入下述统一回归；Windows LPAC 的 Git NUL 限制使真实合成 Git 编码检查仍需 Linux CI 验收。
- 预上线脚本的合成备份标记改用本次新建临时目录，避免写只读源码；Windows LPAC 对 `Path.resolve(strict=True)` 返回拒绝访问，真实备份目录枚举不计通过。私有合成文件已复现该平台限制，没有通过放宽路径校验消除失败；Linux 旧 SHA 的该项已通过，不冒充新 SHA 通过。
- 下面的 25 模块联合回归及 40 文件逆序回退属于编号修复前阶段；已由上方 69 文件最终本机验收覆盖。commit/push 和新 SHA 完整 CI 仍分别登记。

## 编号修复前的续修验证与整批回退（40 文件阶段）

- 编号修复前的 25 个完整模块一次联合运行：**397 passed、53 subtests passed、0 failed、0 skipped**。包括调度/隔离/工作流/失败报告、7 个只读源码 JS harness、详情列与金额组件、手机识物、自动更新行为门禁、原生九入口/两种旧协议/租约/真实双连接并发，以及新增网页和原生 AI 重放权限回归。不能据此宣布全部 unit/verify/AI CI 全绿。
- AI 回执补修 BUG-2026-11-10-003：原生三个入口旧版 7 failed；网页普通/SSE 旧版 4 failed、2 个既有角色拦截对照 passed。复核当前开关和能力后仍保留原回执，恢复权限原样重放，不重复模型、草稿、库存或审计。原生并发 7 项现在使用隔离身份专属的新文件库实际执行，退出恢复内存引擎；两处 SQLite 外部连接显式关闭。
- 单测报告新增 XML/完整 Markdown 和公开错误注解，CI 每个 unit 分片保留失败报告制品。缺失/空/坏 XML、旧报告、pytest 非零码及“退出 0 但报告含失败”都不得算通过。原有测试选择、分片和断言保持。
- 在私有合成 Git 仓库把本次全部 **40 文件**分为 2 个组件提交，再按逆序全部 revert，并逐文件比较基线摘要；恢复后所有候选摘要再次相同。共享 `C:\wms` 未回退、未暂存、未改 HEAD。
- 回退后的独立隔离运行：**37 failed、34 passed、16 errors**；其中错误为旧 harness 向只读源码写临时 JS，不计作业务断言失败。恢复后运行上述完整 25 模块为 **397 passed / 53 subtests passed**。回退结果可证明这些回归锁有效，不能替代尚未通过的正式编号问题。
- 前一版 39 文件在全仓库对象和独立临时索引中实际执行 staged 静态规则，**0 违规**；共享索引字节校验保持。全量棘轮门禁、A11、Python 语法和 `git diff --check` 通过；全量历史存量告警未被清零或隐藏。第一次仅含改动文件的私有仓库缺少原测试，产生 A9 假失败，已用包含全部原测试的独立索引复核，未改规则或加豁免。
- 回退证明目录：`ci-followup-r8-final40-2b_goy4l`；原始日志为 `logs/ci-r8-final40-old.*`、`logs/ci-r8-final40-restored.*`。两次内核回执均 closed，Job 已清空、WFP 过滤与隔离身份回收，受保护摘要不变。

## 正式编号实际修复（BUG-2026-11-10-004）

- 既有批准方案保持：首次成功保存正式号、编辑按 ID 保留编号、同请求重放、删除不复用。不改变历史格式和前缀，不修改现存历史编号。
- 使用已有 system_setting 表的内部序列键，写锁、初始化、完整后缀最大值、序号更新及单据保存处于同一事务；无独立提交，没有生产迁移。页面 GET/HEAD 预览不占号，失败回滚不消耗正式号码；ORM 记录导入及变化的高水位，历史已丢失且无留存的号码不能追溯。
- 20 个现有前缀合成回归：旧版 25 failed/3 passed，新版初次 28 passed。原编号 10 项、历史编号 8 项全过；真实应用 11 模块联合 195 passed/0 failed，包含两个独立连接及两个自有子进程并发、跨月、响应重放、同请求更换内容拒绝、原单据/库存保持。
- 新建保存入口统一后，旧“客户端预览重复必须拒绝”测试按批准方案变为创建另一正式号，仍严格核验原单据、原明细、库存不变；故意注入后端生成器碰撞时仍必须拒绝，不允许覆盖。
- BOM 补齐后端及统一 JS 请求幂等入口。首批 33 个相邻模块 376 passed、1 个旧 BOM 预览期望失败，该期望已按上述业务约定修正，并在最终联合回归通过。这些阶段数字有重叠，不相加作为总 BUG 数。
- 62 文件阶段的静态证据已经由最终 69 文件检查覆盖；整批逆序回退已完成，见上方。提交、推送及新 SHA CI 仍分别登记。

## 本机原始证据

目录：`C:\Users\Administrator\AppData\Local\Temp\wms-unified-acceptance-puotc0hf`。

- `logs/ci-startup-before.log`、`logs/ci-confirm-verify_ci_startup_diagnostic.log`。
- `logs/ci-dispatch-before.log`、`logs/ci-dispatch-fixed.log`。
- `logs/ci-paused-frozen-before.log`、`logs/ci-paused-frozen-after.log`。
- `logs/ci-followup-combined.log` 及同名 `-receipt.json`。
- `logs/ci-readonly-js-harnesses.log`、`logs/ci-detail-money-context.log`、`logs/ci-purchase-legacy-highwater.log` 及同名隔离回执。
- `logs/ci-unit0-exact-manifest.log`、`logs/ci-unit0-next-failures.log`、`logs/ci-unit0-after-scope.log` 是部分失败诊断，非整片验收。
- `logs/ci-confirm-verify_ci_static_only_diagnostic.log` 是局部静态诊断：AI 子脚本明确标 DEFERRED / 失败，不是完整 gate 通过证据。
- `annotations-129268045*.json` 为实际 549a744d 的 GitHub 检查注解。

生效确认：待人工确认。没有生产数据库/备份操作，没有部署或服务重启。
