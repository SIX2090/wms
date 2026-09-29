# WMS 仓库管理系统

> 最近更新：2026-09-29 —— 全面校对并同步 9 月进展：CI 三工作流全绿门禁、防 BUG 规则扩至 A1–A14、打印模板设计中心/在线编辑器、手机端离线队列与语音能力、库存三账口径收敛。历史数字均已按当日仓库实测重新核对。
> 当前重点：基于 Flask 的单人 WMS，面向低压成套电气设备企业，重点是拍照识别 + AI 物料治理 + 出入库草稿生成 + 移动端扫码作业。

## 系统定位

单人使用的中文 WMS：物料登记、出入库、盘点、打印、报表，配合 AI 单据识别（照片/截图 → 草稿）与 Android 扫码 App。AI 只创建和检查草稿，完成、审核、作废、删除等高风险操作必须由人工执行（详见 [`AI_PERMISSION_MATRIX.md`](./AI_PERMISSION_MATRIX.md)）。

## ⚠️ Code Review SLA（开发者必读）

> **所有改动只能直推 main，且必须先过本地 L1 + L2 两道关，再等 CI 三工作流转绿。**

本仓库使用 GitHub 免费版 + 私有仓库，**main 分支无服务端强制保护**。同时按 [AGENTS.md](./AGENTS.md) 的硬规则，**禁止在 GitHub 上创建任何新分支**（包括 `feature/*` / `fix/*` / `chore/*`）。这意味着：

- 没有 PR review 流程，所有 review 都在 commit 之前人工完成
- 没有任何"合并前最后一道闸门"，错代码一旦 push 就是 main 历史
- 服务端保护层（L4）"摆设"——不能依赖 GitHub Web UI 勾选的强制规则

### 流程强制

1. **开工前置条件——CI 全绿门禁**：开始任何任务前，确认三个工作流在 `main` 上最近一次运行全部为绿色（`python3 scripts/check_ci_green.py`，全绿退出码 0）。任一非绿**不得开工**，必须先修红。
2. 改动前先读 [DEVELOPMENT_RULES.md](./DEVELOPMENT_RULES.md) 和本文件底部的"防 BUG 14 条规则"
3. 提交前必须跑 `make check`（lint + BUG 静态回归 + pytest），全部通过
4. 改完模板或路由后跑 `make smoke`（121 项冒烟），全部通过
5. commit message 关联 BUG ID（若有）：`fix: BUG-2026-09-29-NNN 简述`
6. push 之前再人工 review 一次自己的 diff（`git diff origin/main`）

### 三层防御

| 层级 | 触发时机 | 拦截什么 |
|---|---|---|
| L1 本地 pre-commit | `git commit` | 防 BUG 14 条规则（A1–A14）+ 裸 fetch 拦截 |
| L2 本地 pre-push | `git push` | 拒绝非 main 分支推送 + 禁删远程 main |
| L3 GitHub Actions CI | push / 每日 02:30 定时 | 三工作流：121 项冒烟 + BUG 静态回归 + pytest 全量 + A1–A14 全量门禁 + AI 子系统验证 + Android APK 构建 |

L1 + L2 是合入 main 之前的**唯一**拦截机会。`git commit --no-verify` 和 `git push --no-verify` 等于主动缴械，强烈不推荐。

### 启用本地钩子（每个 clone 必做一次）

```bash
bash .githooks/install-hooks.sh
```

### CI 全绿门禁（2026-09-18 起）

开工前必须确认下列三个工作流在 `main` 最近一次运行全为 `success`：

| 工作流 | 文件 | 跑什么 |
|---|---|---|
| `Android APK Build` | `.github/workflows/android-build.yml` | Release APK 构建（本仓库唯一真实 Android 编译证据）+ Lint + 单测 |
| `WMS AI Verification` | `.github/workflows/verify.yml` | 静态规程检查 + AI 子系统 core 验证 |
| `WMS CI` | `.github/workflows/ci.yml` | A1–A14 全量门禁 + gitleaks + pytest（4 并发分片）+ 74 项静态回归 + 121 项冒烟 |

```bash
# 一键检查：全绿退出码 0；任一非绿退出码 1 并列出失败项
python3 scripts/check_ci_green.py
```

三个工作流每日 02:30（北京时间）定时触发，用于发现依赖变更、上游镜像失效等时间性故障。CI 总耗时已从 20 分钟优化至约 4–6 分钟（CI-PERF-2026-09-17 / 2026-09-24 并行化拆分）。

## 主要功能

- 基础资料：物料、分类、单位、供应商、客户、仓库、库位、员工、部门、合同/工程档案。
- 库存管理：库存查询（仓库必填、仓库级口径）、库位库存、库存流水、两级库存预警（最低库存/安全库存）、期初库存（多明细行汇总，ARCH-OS-DOC-01）、库存台账。
- 入库管理：采购入库、产品入库、其他入库、销售退货入库和入库单打印。采购入库可手工录入，采购订单是可选来源。
- 出库管理：领料单、其他出库、销售出库、售后出库、采购退货出库和出库单打印。
- 盘点管理：库存盘点、扫码盘点、盘点差异处理。
- 库内业务：调拨单、调整单、库存扣减和库存增加流水。
- 采购业务：采购申请、采购订单、采购到货执行跟踪。
- 生产与外协：BOM、生产领料、外协发料、外协收货、外协进度。
- 单据效率：明细字段设置、复制行、合同/工程/仓库向下填充，合同编号和工程名称按明细行保存。
- 单据下推：采购入库和其他入库可按明细及数量下推领料单、其他出库单或售后出库草稿。
- 数据导入导出：Excel 批量导入、导出（openpyxl）和前端表格处理。
- 标签条码：物料标签模板、批量标签打印（`app/routes/label.py`、`label_barcode.py`）。
- 打印体系：全 Excel 模板化打印；统一打印模板设计中心 + 在线编辑器 v2（类 Excel，PRINT-TEMPLATE-F01~F06）；10 种单据内置模板注册表；打印队列与重试、多工作站多打印机定向路由（`/print_routing`）、内置/独立 Windows 打印代理无人值守出纸、打印失败/滞留/离线告警与微信推送（详见 `app/routes/print_queue.py`、`print_template_center.py`、`print_template_editor.py`、`app/local_print_agent.py`、`tools/print_agent/`）。
- 移动端 APP：Android 原生 APP（Kotlin + Jetpack Compose，`app/android-native-wms/`，包名 `com.factory.wms`）扫码入库/出库/盘点，提交即自动触发打印任务；未提交清单落盘 DataStore（杀进程不丢）；断网离线作业队列暂存、联网补传；崩溃自动上报；库存日报/出入库明细/库存台账只读报表；语音指令（可集成 sherpa-onnx 离线中文识别，见 [SHERPA_INTEGRATION.md](./SHERPA_INTEGRATION.md)）。APK 由 CI 构建发布，CI 出包是 Android 端唯一编译验收依据。
- 移动端接口：移动扫码、物料查询、扫码提交、拍照识别物料（`app/routes/mobile.py`、`native_api.py`）。
- 客供登记：其他入库明细可勾选客供并选择客户；不做库存所有权隔离，客供行禁止直接下推普通出库（后端 409 硬拦截）。
- AI 单据助手：上传照片或截图后识别明细、匹配已有物料、人工确认新物料编码，并生成入库或出库草稿（LLM vision 通道，OpenAI 兼容 endpoint，带熔断器；104 个脱敏 golden 样本见 `samples/ai_documents/`）。
- AI 物料治理：中文归一化、名称+规格加权、别名命中、低置信度二次确认（详见 `app/ai/documents/material_governance.py`）。
- AI 工作台：采购到货跟进、销售跟进、仓库巡查、补货建议、业务质量仪表盘（详见 `app/ai/agents/`、`app/ai/ops/`）。
- AI 灰度发布：四档灰度模式、白名单即时生效、降级保留证据（详见 `app/ai/ops/rollout_control.py`）。
- 安全：Flask-WTF CSRF 保护、生产 Cookie 硬门禁（`SESSION_COOKIE_SECURE` 强制）、客户端每 25 分钟自动刷新令牌、`/api/csrf_refresh` 端点、AI 路由权限交集 + 高风险硬拦截。
- 前端统一 HTTP 层：`app/static/js/api.js` 封装 `WMS.api.get/post/put/delete`，自动注入 CSRF、统一错误处理；业务 JS 禁止原生非 GET `fetch`（pre-commit 强制）。

AI 只能创建和检查草稿。完成、审核、作废、删除以及库存变动必须由操作人员在业务页面手工执行。

## 库存数据口径（三账恒等式）

库存三份数据的权威关系、派生方向与写入归属铁律见 [`INVENTORY_TRUTH.md`](./INVENTORY_TRUTH.md)，要点：

- **总账** `material.stock`（全局合计，仅展示/估值）、**库位账** `location_inventory`（仓库级真相）、**流水账** `stock_transaction`（append-only 事实来源），恒等式 **总账 = Σ库位账 = Σ流水账**。
- 业务校验必须用仓库级 `get_warehouse_stock_quantities()`，**禁止**裸用全局 `material.stock`（lint 规则 A11 + CI 全量硬门禁强制，防"A 仓掩护 B 仓"串仓）。
- 库存写入收敛到 `apply_stock_delta` / `apply_transfer_pair` / `apply_opening_balance` 三个入口。

## 技术栈

- Python 3.11（版本号随发布递增，当前 `2026.09.1`，见 `app/version.py`；启动自检横幅 `wms v版本 (git短SHA)`）
- Flask 3.1 + Flask-SQLAlchemy 3.0 + SQLAlchemy 2.0 + alembic/Flask-Migrate（迁移）
- Flask-WTF（CSRF 保护）、Flask-Login、pydantic v2（新增路由输入校验，A8 强制）
- APScheduler（定时任务）、waitress（生产 WSGI）
- SQLite（默认本地数据库，WAL + `synchronous=NORMAL` + `busy_timeout=30s`）
- openpyxl / pandas / reportlab / qrcode / python-barcode 等业务工具库
- 前端：Bootstrap 5.3 + 原生 JS（`app/static/js/`），无构建链
- Android：Kotlin + Jetpack Compose（JDK 17，独立 Gradle 工程自包含）

依赖清单（全钉版）位于：

```text
app/requirements.txt          # 运行依赖
app/requirements-test.txt    # 测试依赖（pytest / pytest-xdist / PyYAML / bs4，CI 同源）
```

## 快速启动

### Git 工作区恢复

不要使用 GitHub 的 `Download ZIP`，ZIP 不包含 `.git` 历史。临时电脑重启后可执行：

```powershell
powershell -ExecutionPolicy Bypass -File tools\clone_wms_main.ps1
```

脚本只使用 `main`，目标目录存在普通文件时会停止并提示人工备份，不会删除文件。

进入应用目录：

```bat
cd /d C:\wms\app
```

安装依赖：

```bat
python -m pip install -r requirements.txt
```

启动系统：

```bat
python run_server.py
```

> 首次启动会自动迁移表结构（`auto_migrate_database`），过程约 10-30 秒，请勿中断。启动第一行输出自检横幅（跑的是哪份代码、什么配置），见 `app/startup_check.py`。

访问地址：

```text
http://127.0.0.1:8080/login
```

默认管理员账号：

```text
用户名：admin
初始密码：优先使用 `WMS_BOOTSTRAP_PASSWORD`；未设置且首次创建管理员时为 `admin`
```

如果设置了 `WMS_BOOTSTRAP_PASSWORD`，系统首次创建管理员时会使用该环境变量。安装和启动不会重置已有管理员密码。系统不会自动生成随机密码（密码透明原则）。

## Windows 离线安装

### 用户电脑免 Python 便携版

最终用户电脑不需要安装 Python 3.11。开发/打包电脑执行：

```bat
build_portable_dist.bat
```

脚本会生成便携目录：

```text
dist\WMS\
```

> `dist/` 是构建产物，已被 `.gitignore` 排除，不提交到 Git。

该目录内包含 Python 解释器、依赖包、WMS 程序和启动入口。把整个 `dist\WMS\` 文件夹复制到用户电脑后，用户只需要双击 `启动WMS.bat` 或 `WMS.exe`，然后浏览器访问 `http://127.0.0.1:8080/login`。

便携包由 `tools\build_portable_dist.ps1` 生成。

### 源码离线安装

项目根目录提供离线安装入口：

```bat
install.bat
```

安装脚本会将系统安装到 `C:\wms`，并使用本地 `wheelhouse` 安装 Python 依赖。安装完成后可通过 `wms.bat` 或 `start_wms_offline.bat` 启动。

离线包必须与 `app/requirements.txt` 同步。发布前在联网构建机执行：

```powershell
py -m pip download --only-binary=:all: --dest wheelhouse -r app/requirements.txt pip==26.1.1 setuptools==82.0.1 wheel==0.47.0
py scripts/verify_offline_wheelhouse.py
```

### 其他安装变体

| 脚本 | 用途 |
|---|---|
| `install_e_wms.bat` | 企业内网定制版（含内网代理、域账号集成） |
| `install_portable_python.bat` | 便携 Python 解释器版（不依赖系统 Python） |
| `deploy_cloud.bat` | 腾讯云 Windows 服务器部署（nssm 注册 Windows 服务自启） |

## 重要数据

业务数据库和运行期文件不要提交到 Git，也不要在部署更新时覆盖：

```text
app/instance/inventory.db
app/backups/
app/logs/
app/static/uploads/
```

如果迁移服务器或重装系统，至少先备份：

```text
C:\wms\instance\inventory.db
C:\wms\backups
C:\wms\static\uploads
```

## 配置说明

常用环境变量：

```text
SECRET_KEY                  Flask 会话密钥
DEV_SECRET_KEY              开发环境密钥
WMS_BOOTSTRAP_PASSWORD      初始化管理员密码
WMS_DATABASE_URI / DATABASE_URL   数据库地址，默认 sqlite:///inventory.db
SQLALCHEMY_ECHO             是否打印 SQL，true/false
WECHAT_HELPER_TOKEN         微信助手访问令牌
WMS_WECHAT_HELPER_PORT      微信助手本地端口，默认 8765
WMS_BASE_URL                WMS 主服务地址
WMS_SKIP_AUTO_UPDATE        跳过 auto_update.py，默认 0
WMS_SKIP_DB_UPGRADE         跳过启动时自动迁移，默认 0
WMS_PORT                    HTTP 端口，默认 8080
WMS_THREADS                 Waitress 并发线程数，默认 16
WMS_LOCAL_PRINT_AGENT       是否随服务启动内置本机打印代理，默认 1
WMS_LOCAL_PRINT_BASE_URL    内置打印代理回连地址，默认 http://127.0.0.1
```

生产环境应显式设置 `SECRET_KEY` 和相关访问令牌，不要使用弱默认值。生产 Cookie 硬门禁：非本地部署未启用安全 Cookie 时服务拒绝启动（`WMS_ALLOW_INSECURE_COOKIE` 仅限本地调试，scripts/ 下引用 app 的脚本必须显式放行，A14 门禁）。

SQLite 连接已内置 PRAGMA：`journal_mode=WAL` + `synchronous=NORMAL` + `busy_timeout=30s`（PERF-2026-08-23-001）。`NORMAL` 是 WAL 官方推荐组合：commit 不逐次强制刷盘，慢盘写性能提升 5~50 倍；代价是掉电丢最后数百毫秒事务（有幂等键 + 单据重推兜底）。仍感到写操作卡顿时，优先检查杀毒软件实时扫描白名单与磁盘（建议 SSD）。

## 项目结构

```text
SIX2090/wms
├── app/                          应用主目录
│   ├── app.py                    Flask 主程序（3.4 万行，A10：禁止新增 @app.route）
│   ├── config.py                 配置
│   ├── run_server.py             生产启动入口（waitress）
│   ├── startup_check.py          启动自检横幅（版本 + git SHA + 配置 + 迁移核对）
│   ├── version.py                版本号（日期基 semver，当前 2026.09.1）
│   ├── requirements.txt          运行依赖（全钉版）
│   ├── requirements-test.txt     测试依赖（CI 同源钉版）
│   ├── models/                   SQLAlchemy 模型（core / inventory / master_data / ai / documents / print / wechat）
│   ├── routes/                   业务路由（46 个业务模块：物料/出入库/盘点/调拨/采购/销售/报表/打印×5/移动端×2/AI 反馈/审批/备份等）
│   ├── services/                 仓库级库存口径服务（warehouse_stock_service / warehouse_scope）
│   ├── ai/                       AI 子系统（71 个 .py：agents / analysis / documents / ops / tools、routes.py、v2_routes.py、orchestrator.py、providers）
│   ├── android-native-wms/       Android 客户端（Kotlin + Compose，102 个 .kt，独立 Gradle 工程）
│   ├── templates/                页面模板（135 个 .html）
│   ├── static/                   前端静态资源（js/ 6 个业务文件 + cdn/ 三方库）
│   ├── migrations/               alembic 迁移
│   ├── local_print_agent.py      内置打印代理
│   ├── wechat_helper.py          微信助手
│   ├── notifications.py          定时通知（APScheduler）
│   ├── instance/                 本地数据库目录，不提交
│   ├── logs/                     运行日志，不提交
│   └── backups/                  数据备份，不提交
├── scripts/                      检查、验证和质量工具（189 个 .py）
│   ├── lint_wms_rules.py         A1–A14 防 BUG 静态规则（+ --full / --full-a11 全量门禁模式）
│   ├── lint_no_raw_post_fetch.py 业务 JS 裸调非 GET fetch 拦截
│   ├── check_ci_green.py         CI 全绿门禁检查器（三工作流）
│   ├── verify_wms_bugs.py        BUG 静态回归（74 项检查）
│   ├── run_smoke_in_ci.py        CI 冒烟（自动启停服务）
│   ├── full_smoke_test.py        121 项冒烟（本地手工，需启动服务）
│   ├── verify_ai_all.py          AI 子系统全量验证（core/smoke/full 三档，进程池并发）
│   ├── monthly_bug_review.py     月度 BUG 复盘
│   └── check_hooks_installed.py  验证 git hooks 是否启用
├── tests/                        pytest 测试套件（394 个 test_*.py）
├── samples/ai_documents/         AI 文档识别 golden 样本（104 个脱敏样本）
├── tools/                        安装和维护工具（便携包构建 / clone 恢复 / 打印代理 / 管理员密码重置）
├── .githooks/                    git 钩子（pre-commit / pre-push / install-hooks.sh）
├── .github/workflows/            CI：ci.yml / verify.yml / android-build.yml / perf.yml
├── build_portable_dist.bat       生成 dist\WMS 便携包
├── install.bat                   离线安装入口
├── wms.bat                       快速启动入口
└── README.md                     项目说明
```

## 质量基线（截至 2026-09-29）

| 指标 | 数值 | 验证方式 |
|---|---|---|
| pytest 全量 | 2984 passed / 87 skipped / 0 failed | CI 同参数 `pytest tests/ -q -n 4 --dist loadfile`（254s） |
| 防 BUG lint（A1–A14） | 0 违规 | `python3 scripts/lint_wms_rules.py`（含 A11/A8/A9/A10/A13/A14 CI 全量模式） |
| BUG 静态回归 | 74 项全 PASS | `python3 scripts/verify_wms_bugs.py` |
| 业务冒烟 | 121 项 | `python3 scripts/full_smoke_test.py`（需启动服务） |
| CI 工作流 | 三工作流全绿 | `python3 scripts/check_ci_green.py` |
| BUG 台账 | 462 条已核验条目 | [WMS_BUG_BASELINE.md](./WMS_BUG_BASELINE.md) |
| AI 开发台账 | 约 170 条任务，主线 AI-R01~R17 全部完成 | [WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) |

> 数字随开发滚动，以各台账与 CI 实际运行结果为准；本表仅作健康度快照。

## 部署说明

腾讯云 Windows 服务器部署说明见 `上线部署说明.md`；发布验收模板见 [PRODUCTION_DEPLOYMENT_CHECKLIST.md](./PRODUCTION_DEPLOYMENT_CHECKLIST.md)（每次生产发布前重新填写）。

公网部署时通常由 Nginx 将域名转发到本机 WMS 服务（参考配置 `app/nginx_wms_server_block.conf`）：

```text
http://127.0.0.1:8080
```

## 项目文档

| 文档 | 用途 |
|---|---|
| `AGENTS.md` | AI 和开发代理必须遵守的最高优先级项目规则（业务铁律、atomic action、CI 全绿门禁、A1–A14、R1–R8） |
| `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` | 唯一 AI 开发台账：已有能力基线、任务、依赖、验收和完成记录 |
| `AI_PERMISSION_MATRIX.md` | AI 能力角色、风险等级和人工确认边界 |
| `AI_ONBOARDING_PROMPT.md` | AI 新会话上手提示词 |
| `WMS_BUSINESS_SCOPE.md` | 当前单人 WMS 业务口径和客供料处理边界 |
| `INVENTORY_TRUTH.md` | 库存三份数据的权威关系、派生方向与写入归属铁律 |
| `PRODUCTION_DEPLOYMENT_CHECKLIST.md` | 每次生产发布前重新填写的验收模板 |
| `WMS_BUG_BASELINE.md` | 已核验 BUG、风险、误报和暂缓项基线 |
| `WMS_QUALITY_REPORT.md` | BUG 质量月报（类型分布、模块分布、Top 根因） |
| `WMS_STABILITY_BASELINE.md` | 发布门禁覆盖的 10 条关键链路 |
| `DEVELOPMENT_RULES.md` | 开发规范：加功能 checklist、修复 BUG 流程、CI/pre-commit 门禁、防 BUG 规则详解 |
| `SHERPA_INTEGRATION.md` | Android 端 sherpa-onnx 离线中文语音识别集成说明 |
| `docs/archive/` | 已结束的 BUG、巡检、专项审计报告与已完成计划快照（含 SYSTEM_TEST_*、SALES_MANAGEMENT_*、AI-MOB-OFFLINE-01），仅供追溯 |
| `上线部署说明.md` | 腾讯云 Windows 部署和数据保护说明 |

> 为避免计划冲突，仓库只保留 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 作为 AI 开发主计划，禁止另建并行 AI 计划。

## 开发校验

### 基础校验

```bash
# 编译检查
python3 -m compileall -q app scripts

# BUG 基线静态回归
python3 scripts/verify_wms_bugs.py
python3 scripts/scan_wms_risks.py

# CI 全绿门禁（开工前必查）
python3 scripts/check_ci_green.py
```

### 防 BUG 静态规则 + 钩子验证

```bash
# A1–A14 全部规则（默认模式）
python3 scripts/lint_wms_rules.py

# CI 全量模式（A11 全量 + A8/A9/A10/A13/A14 棘轮）
python3 scripts/lint_wms_rules.py --rule a11 --full-a11
python3 scripts/lint_wms_rules.py --full

# 验证 git hooks 是否启用
python3 scripts/check_hooks_installed.py
```

### 测试套件

```bash
# 提交前一键：lint + BUG 回归 + pytest
make check

# 本地全量回归请复刻 CI 参数（串行跑法存在跨文件环境污染，不可作判据）
pytest tests/ -q -n 4 --dist loadfile

# AI 子系统全量验证（smoke / core / full 三档）
python3 scripts/verify_ai_all.py --level core
python3 scripts/verify_ai_all.py --level full

# 业务冒烟（本地手工启动服务）
python3 scripts/full_smoke_test.py

# 业务冒烟（CI 友好版：自动启停服务）
python3 scripts/run_smoke_in_ci.py
```

### 月度质量复盘

```bash
python3 scripts/monthly_bug_review.py    # 写入 WMS_QUALITY_REPORT.md
```

## Git 忽略规则

仓库已通过 `.gitignore` 排除数据库、日志、备份、上传文件、虚拟环境和密钥文件。新增功能时不要把以下内容提交到 Git：

```text
*.db
*.db-wal
*.db-shm
app/instance/
app/logs/
app/backups/
app/static/uploads/
dist/
.env
secret_key
wechat_helper_token
```

## 本地开发钩子（防 CSRF 回归 + A1–A14 + 分支强制）

仓库自带一组 git 钩子，位于 `.githooks/`：

| 钩子 | 触发时机 | 作用 |
|---|---|---|
| `pre-commit` | `git commit` | 跑 A1–A14 防 BUG 规则 + 裸调非 GET fetch 检查，违规直接拒绝 |
| `pre-push` | `git push` | 强制 push 只能发生在 `main`（禁止任何新分支；禁止删除远程 main，允许清理残留的 traes/* 等非 main 分支） |

### 首次克隆后必须启用钩子

```bash
bash .githooks/install-hooks.sh
```

脚本等价于 `git config core.hooksPath .githooks`。验证启用是否成功：

```bash
python3 scripts/check_hooks_installed.py
```

### 启用后的运行流程

1. `git commit` → pre-commit 跑 A1–A14 + 裸调 fetch，违规直接拒绝
2. `git push` → pre-push 检查分支策略，禁止非 main 分支
3. 推送触发 GitHub Actions 三工作流，转绿才算这个 atomic action 完成
4. 下一轮开工前再次确认三工作流全绿（CI 全绿门禁）

**跳过钩子（紧急情况，不推荐）：** `git commit --no-verify` —— 会绕过所有检查，务必只在已知冲突、明确原因时使用。

## 开发规范

加新功能或修复 BUG 前，请务必阅读：

- 📘 [DEVELOPMENT_RULES.md](./DEVELOPMENT_RULES.md) — 完整开发规范
- 🤖 [AGENTS.md](./AGENTS.md) — AI Agent 工作准则（含任务粒度、提交流程、反复 BUG 防护 R1–R8）
- 🐛 [WMS_BUG_BASELINE.md](./WMS_BUG_BASELINE.md) — 已知 BUG 登记

### 防 BUG 14 条规则（pre-commit 强制）

| 编号 | 规则 |
|---|---|
| A1 | `<form method="post">` 必须有 csrf_token |
| A2 | Python POST 路由必须 @login_required 或 @csrf.exempt |
| A3 | 业务 JS 不能 console.log |
| A4 | 业务 JS 不能 debugger / alert |
| A5 | 业务 JS 不能 eval / new Function |
| A6 | 业务 Python 不能 print |
| A7 | SQL 必须参数化，禁止字符串拼接 |
| A8 | 新增 POST/PUT/DELETE 路由必须用 pydantic BaseModel 输入校验 |
| A9 | 新增业务函数必须在 tests/ 至少 1 个对应 pytest 测试 |
| A10 | app/app.py 禁止新增 @app.route，强制走 app/routes/ 模块 |
| A11 | 禁止裸用 material.stock（总账）做库存校验，必须用仓库级 get_warehouse_stock_quantities()（CI 全量硬门禁） |
| A12 | 测试文件模块顶层禁止裸 app context .push()/.pop() |
| A13 | WMS_BUG_BASELINE.md 新增 BUG 条目必须含「生效确认」字段 |
| A14 | scripts/ 下新增 app 引用脚本必须显式放行生产硬门禁 |

> A8/A9/A10/A13/A14 仅对 git staged 新增行强制；A11 双模式：pre-commit 查新增行 + CI `--full-a11` 全量。业务 JS 的非 GET 请求必须走 `WMS.api.post/put/delete`（`app/static/js/api.js`），白名单外裸调 `fetch` 会被 pre-commit 拦截。

启用钩子：`bash .githooks/install-hooks.sh`

### 修复 BUG 流程

1. 在 [WMS_BUG_BASELINE.md](./WMS_BUG_BASELINE.md) 登记（`BUG-YYYY-MM-DD-NNN: <标题>`，含「生效确认」字段）
2. 登记前先 grep 台账查同根因历史（R6），同模式复发必须一并修复所有同类消费点
3. commit message 关联 BUG ID：`fix: BUG-2026-09-29-NNN xxx`
4. 加回归测试，且回退修复后新测试必须失败（回归锁自证，R8）
5. 全量 + 相邻模块回归通过、lint 0 违规、CI 三工作流转绿后，改状态为"已修复"
