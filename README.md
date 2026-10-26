# WMS 仓库管理系统

> 最近校订：2026-10-23。补充生产领料库位、继续新增及系统设置初始化的使用说明；具体版本、测试与生产生效记录以当前代码和对应证据为准。
> 当前重点：基于 Flask 的单人 WMS，登记物料出入库，优先改善界面和录单效率；支持拍照识别、草稿生成及移动扫码。

## 系统定位

单人使用的中文 WMS：物料登记、出入库、盘点、打印、报表，配合 AI 单据识别（照片/截图 → 草稿）与 Android 扫码 App。AI 默认只创建和检查草稿，完成、审核、作废、删除等高风险操作须由人工执行或获得用户对具体操作的明确授权（详见 [`AI_PERMISSION_MATRIX.md`](./AI_PERMISSION_MATRIX.md)）。

Git 部署的一键代码更新使用根目录 `update_from_github.bat`；预检失败不停止服务，启动失败返回非零并报告旧代码/服务恢复结果。依赖升级需要独立维护，详见[一键更新操作说明](docs/UPDATE_FROM_GITHUB.md)。

覆盖安装失败会保留已有业务目录和快捷方式，已有数据库只读校验后跳过初始化；处理方式见[安装失败数据保留说明](docs/INSTALLATION_FAILURE_RECOVERY.md)。

普通领料、其他出库草稿详情支持整批粘贴物料，全部校验通过后一次保存；格式、权限和来源限制见[出库草稿批量粘贴说明](docs/OUTBOUND_BATCH_PASTE.md)。

普通领料新增/草稿编辑页的「保存完成并新增领料单」在本单保存并完成成功后，直接进入新单号、当天日期和空白明细的领料单。完成失败或需要确认时进入已保存单据详情核对，由人工决定后续操作。

生产领料启用库位管理后，新增、编辑须填写库位；切换仓库时清空原库位，避免串用。表单和列表的“完成并新增”均携带仓库、库位等表头信息，新单仍须人工核对。关闭库位管理时不显示该输入框，编辑保留历史库位；系统不自动生成默认库位，也不因此开启库位管理。

入库列表的「批量导出」下载所选单据的 Excel；「打印已选（单张）」当前限选一张，多张合并打印暂未支持，见[入库列表导出与打印说明](docs/INBOUND_LIST_EXPORT_PRINT.md)。

管理员在「系统设置」初始化业务数据前，应先创建并核对备份。向导须成功加载预览，再输入当前管理员密码、准确确认短语并作最后确认；取消勾选「同时清空主数据」后，预览将主数据标为保留，并从将清理合计中排除。初始化保留用户账号与密码，系统参数会重置为默认值；若请求中断或执行结果不确定，先核对实际结果，再决定是否重新确认。

## 开发与发布规则

以 [AGENTS.md](AGENTS.md) 和 [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md) 为准，以下仅作入口说明：

CI 对经过验证基线上的白名单文档改动执行轻量检查；代码、规则及未知范围仍跑全量。推送核验远端基线，发布核验目标 SHA，具体边界和命令见[CI 分级验证操作说明](docs/CI_VALIDATION_POLICY.md)。

1. 所有修改直接在 main 工作，按 atomic action 独立提交和推送；禁止新建工作分支。
2. 开工前确认 main 上 `Android APK Build`、`WMS AI Verification`、`WMS CI` 的最近一次运行全部成功。运行中、失败或尚未核实均不放行；异常时按 AGENTS 的查询失败处理规则取得实际证据。
3. 代码修改先查既有能力、BUG台账和相关测试；遵守A1–A14及R1–R8，按受影响范围执行模块、相邻及全量回归。模板/路由变更须用隔离库做HTTP冒烟。
4. 每个atomic action推送后核对实际远端SHA并验收CI。代码已推送、测试通过、生产已部署是三种不同状态，不得混报。
5. 纯文档修订核对事实、命令、链接及对应契约测试；修改AGENTS本身单独commit/push，并注明规则修订日期。

每次克隆后启用钩子：

```bash
bash .githooks/install-hooks.sh
python scripts/check_hooks_installed.py
```

Windows未配置bash命令时可调用Git for Windows的bash，或使用等效配置 `git config core.hooksPath .githooks` 后验证。安装脚本还会检查钩子可执行权限。

| 层级 | 实际作用 |
|---|---|
| pre-commit | 涉及app/scripts代码时检查A1–A14及非GET原生fetch；按规则区分新增行、白名单和豁免 |
| pre-push | 检查main分支策略和CI全绿门禁；API工具写入不会经过本地钩子，仍须满足相同规则 |
| GitHub Actions | 普通lint、A11全量、A8/A9/A10/A13/A14存量棘轮、安全扫描、隔离测试、业务冒烟及AI/Android验证 |

CI入口：

```powershell
python scripts/check_ci_green.py
```

匿名API可能限流；HTTP403不等于工作流失败，也不能当作已通过。可用连接器/Actions页面核实最新运行。三个必需工作流有每日定时触发，Android还受push路径过滤；并非每次文档提交都新建Android构建。具体触发、并行分片和结果以 `.github/workflows/` 为准。GitHub分支保护与规则集以现场核验为准，不根据旧的免费/私有仓库结论推断当前保护。

## 主要功能

- 基础资料：物料、分类、单位、供应商、客户、仓库、库位、员工、部门、合同/工程档案。
- 库存管理：库存查询（仓库必填、仓库级口径）、库位库存、库存流水、两级库存预警（最低库存/安全库存）、期初库存（多明细行汇总，ARCH-OS-DOC-01）、库存台账。
- 库存报表：多仓环境仅列出所选仓库有库存记录的物料；本仓已归零的物料默认保留，勾选“库存等于0不显示”可隐藏。查询、汇总、导出和打印使用同一仓库范围。
- 出入库汇总默认[按物料查看收发存](http://127.0.0.1:8080/report/view/summary)：期初、本期入库、本期出库和期末结存，按单位分别合计，可点击物料联查台账。页面可切换原按日期汇总。[统计口径与接口](docs/REPORT_MATERIAL_MOVEMENT.md)。
- 入库管理：采购入库、产品入库、其他入库、销售退货入库和入库单打印。采购入库可手工录入，采购订单是可选来源。
- 出库管理：领料单、其他出库、销售出库、售后出库、采购退货出库和出库单打印。
- 盘点管理：库存盘点、扫码盘点、盘点差异处理。
- 库内业务：调拨单、调整单、库存扣减和库存增加流水。
- 采购业务：采购申请、采购订单、采购到货执行跟踪。
- 生产与外协：BOM、生产领料、外协发料、外协收货、外协进度。
- 单据效率：明细字段设置、复制行、合同/工程/仓库向下填充，合同编号和工程名称按明细行保存；采购入库、领料支持人工点击“保存并完成”。
- 单据下推：采购入库和其他入库可按明细及数量下推领料单、其他出库单或售后出库草稿。同一页面内，相同内容失败后手动重试复用请求编号；刷新或关闭页面后不保留。若结果不确定，先核对目标草稿再决定是否重试。
- 数据导入导出：Excel 批量导入、导出（openpyxl）和前端表格处理。
- 期初库存导入统一进入[批量导入页](http://127.0.0.1:8080/batch_import?type=opening_stock)：先预检，再人工确认整份文件；换文件或取消后须重新预检。预览最多展示前 500 行，确认数量以整份文件的可导入总数为准。导入中禁止重复点击；若网络中断导致结果不确定，先核对期初单据再决定是否重试，重复导入会累加数量。
- 标签条码：物料标签模板、批量标签打印（`app/routes/label.py`、`label_barcode.py`）。
- 批量标签须等当前模板预览就绪再打印；切换模板时以最后选择为准，加载失败可重试或明确选择默认90×50模板。入库明细标签的Excel下载按预览中的实际物料生成；不沿用入库明细ID作为物料ID。免登录代理打印沿用90×50文字标签，自定义模板及Excel下载须先登录。
- 物料页标签设计器须等所选模板加载完成再保存；保存、设默认和删除进行中会暂停其它设计操作。保存更新当前模板的版式及尺寸，修改名称请用「另存为」；更新后继续编辑原模板，新建后选中刚创建的模板。
- 微信报表分享：手动执行前确认发送；“重新生成并再次发送”会再次投递已分享的报表。结果以分享日志的实际发送状态为准，执行完成不代表全部发送成功。
- 打印体系：全 Excel 模板化打印；统一打印模板设计中心 + 在线编辑器 v2（类 Excel，PRINT-TEMPLATE-F01~F06）；单据内置模板注册表；打印队列与重试、多工作站多打印机定向路由（`/print_routing`）、内置/独立 Windows 打印代理无人值守出纸、打印失败/滞留/离线告警与微信推送（详见 `app/routes/print_queue.py`、`print_template_center.py`、`print_template_editor.py`、`app/local_print_agent.py`、`tools/print_agent/`）。
- 移动端 APP：Android 原生 APP（Kotlin + Jetpack Compose，`app/android-native-wms/`，包名 `com.factory.wms`）扫码入库/出库/盘点，提交即自动触发打印任务；未提交清单落盘 DataStore（杀进程不丢）；断网离线作业队列暂存、联网补传；崩溃自动上报；库存日报/出入库明细/库存台账只读报表；语音指令（可集成 sherpa-onnx 离线中文识别，见 [SHERPA_INTEGRATION.md](./SHERPA_INTEGRATION.md)）。APK 由 CI 构建发布，CI 出包是 Android 端唯一编译验收依据。
- 移动端接口：移动扫码、物料查询、扫码提交、拍照识别物料（`app/routes/mobile.py`、`native_api.py`）。
- 客供登记：其他入库明细可勾选客供并选择客户；不做库存所有权隔离，客供行禁止直接下推普通出库（后端 409 硬拦截）。
- AI 单据助手：上传照片或截图后识别明细、匹配已有物料、人工确认新物料编码，并生成入库或出库草稿（LLM vision 通道，OpenAI 兼容 endpoint，带熔断器；脱敏 golden 样本见 `samples/ai_documents/`）。
- AI 物料治理：中文归一化、名称+规格加权、别名命中、低置信度二次确认（详见 `app/ai/documents/material_governance.py`）。
- AI 工作台：采购到货跟进、销售跟进、仓库巡查、补货建议、业务质量仪表盘（详见 `app/ai/agents/`、`app/ai/ops/`）。
- AI 灰度发布：灰度模式、白名单即时生效、降级保留证据（详见 `app/ai/ops/rollout_control.py`）。
- 安全：Flask-WTF CSRF 保护、生产 Cookie 硬门禁（安全Cookie或受信HTTP场景显式放行）、客户端每 25 分钟自动刷新令牌、`/api/csrf_refresh` 端点、AI 路由权限交集 + 高风险硬拦截。
- 前端统一 HTTP 层：`app/static/js/api.js` 封装 `WMS.api.get/post/put/delete`，自动注入 CSRF、统一错误处理；业务 JS 禁止原生非 GET `fetch`（pre-commit 强制）。

AI默认只创建和检查草稿；完成、审核、作废、删除及库存变动须人工操作或获得用户对具体操作的明确授权，详见AGENTS与权限矩阵。

## 库存数据口径（三账恒等式）

库存三份数据的权威关系、派生方向与写入归属铁律见 [`INVENTORY_TRUTH.md`](./INVENTORY_TRUTH.md)，要点：

- **总账** `material.stock`（全局合计，仅展示/估值）、**库位账** `location_inventory`（仓库级真相）、**流水账** `stock_transaction`（append-only 事实来源）。
  恒等式**按库位开关分两档**（[INVENTORY_TRUTH.md](./INVENTORY_TRUTH.md) §1 为准）：**开启库位管理时** 总账 = Σ库位账 = Σ流水账；**关闭库位管理时**（当前默认）库位账不落账、可能留有历史残留，只要求 **总账 = Σ流水账**，不得把残留的库位账差异当成坏账。
- 业务校验必须用仓库级 `get_warehouse_stock_quantities()`，**禁止**裸用全局 `material.stock`（lint 规则 A11 + CI 全量硬门禁强制，防"A 仓掩护 B 仓"串仓）。
- 库存写入优先通过 `apply_stock_delta` / `apply_transfer_pair` / `apply_opening_balance`；历史未收敛点及例外见INVENTORY_TRUTH，不把“收敛目标”写成所有旧调用已迁移。

## 技术栈

- Python 3.11；应用版本独立记录于 `app/version.py`，启动日志包含 `wms v版本 (git短SHA)`，不是Python版本号
- Flask 3.1 + Flask-SQLAlchemy 3.0 + SQLAlchemy 2.0（F3.1 起迁移机制唯一：启动期 auto_migrate_database() 幂等补列；Alembic/Flask-Migrate 已废弃）
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

## 启动与更新

### 已有Windows生产部署

先核对8080监听、实际解释器和托管方式；服务已运行时不要重复启动。标准手工入口：

```bat
C:\wms\start_wms_offline.bat
```

2026-10-21核验的当前常驻实例由 `WMS-Warehouse` 计划任务通过本地 `run_wms_task.bat` 以SYSTEM运行；重启沿用实际托管方式，不能把手工窗口实例当作常驻实例。自动启动/服务模式见 [服务部署说明](docs/SERVICE_DEPLOYMENT.md)。

标准离线脚本设置生产环境及 `WMS_NO_DB_TOUCH=1`，禁止启动升级/初始化；这不是数据库只读模式。首次安装需按下方安装流程准备数据库，不能承诺每次启动都会自动迁移。现有库更新、依赖安装和生产重启均须独立维护并核验，不能直接对运行中的生产解释器执行全量pip升级。

访问：`http://127.0.0.1:8080/login`。有Nginx时还须核对实际公网入口；本地HTTP200不能代替公网验证。

退出当前账号：电脑端点击左侧菜单末尾的「退出登录」（管理员位于「系统管理」下方）；手机浏览器先点左上角菜单，再点「退出登录」。退出会返回登录页，并清除本浏览器的登录会话及「记住我」。退出前请先保存正在编辑的单据。

录单快捷键：Ctrl+S（Mac 为 Cmd+S）仅触发当前页面可用的普通「保存」或「保存草稿」，不会触发「保存并新建」或「保存并完成」。只有完成按钮的页面会提示使用页面按钮；弹窗打开时不触发页面保存。 Ctrl+N／Esc 仅点击当前页面可见、可用且已声明的「新增单据」／「返回列表（取消）」入口；没有对应入口时不跳转。输入框、中文输入法组合输入、弹窗、抽屉或菜单打开时不触发页面导航；Esc 关闭组件后不会同时返回列表。

单据「保存并完成」分为两个步骤。若草稿已保存，但完成请求被拒绝或结果尚未确认，录单页会保留单号、具体原因和「查看已保存单据」入口；请进入已保存单据核对状态或修改后再完成，避免重复录入。领料单只有保存与完成均成功后才自动打开下一张。

初次创建管理员时用户名为admin，密码优先取 `WMS_BOOTSTRAP_PASSWORD`，未设置时使用admin并警告；已有账号不会因安装/启动而重置密码，系统不随机生成密码。代理修改密码须事先获得用户对具体操作的授权。

### Git工作区恢复

```powershell
powershell -ExecutionPolicy Bypass -File tools\clone_wms_main.ps1
```

脚本仅使用main，目标目录已有普通文件时停止；GitHub Download ZIP不含Git历史，不能当作已同步工作区。更新代码使用根目录 `update_from_github.bat`，详见 [更新操作说明](docs/UPDATE_FROM_GITHUB.md)。

### 开发与测试依赖

在独立开发环境安装，勿套用到正在运行的生产解释器：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r app/requirements-test.txt
```

该清单引用生产钉版依赖，CI同源使用。后续开发/测试命令中的python使用该虚拟环境解释器；不要另行裸装最新版pytest或全量升级生产依赖。

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

便携包由 `tools\build_portable_dist.ps1` 生成。 打包电脑还需安装 Git；程序文件取自已提交的 HEAD，app/tools 已跟踪文件有未提交改动时拒绝构建。本地未跟踪文件、业务库、上传、备份、日志、环境及密钥文件不导出。输出只能是仓库 dist 下的全新直接子目录，已有目录一律拒绝覆盖，不自动删除。重复构建可指定 `build_portable_dist.bat -DistDir C:\wms\dist\WMS_20261017`；失败保留输出现场，另选新目录重试。这里只生成程序运行包，业务数据迁移与源码覆盖安装须另按对应流程。

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
| `install_e_wms.bat` | 另一套源码安装入口；执行前核对目标目录、权限及随包运行时，不据脚本名推断域账号集成 |
| `install_portable_python.bat` | 便携 Python 解释器版（不依赖系统 Python） |
| `deploy_cloud.bat` | 腾讯云 Windows 服务器部署（nssm 注册 Windows 服务自启） |

## 重要数据与备份

源码部署在C:\wms时，至少保护以下实际路径：

```text
C:\wms\app\instance\inventory.db
C:\wms\app\instance\secret_key
C:\wms\app\instance\wechat_helper_token
C:\wms\app\static\uploads\
C:\wms\app\backups\
C:\wms\backups\
C:\wms_backups\
```

数据库实际位置受 `DATABASE_URL` 影响，上传目录受 `UPLOAD_FOLDER` 影响；扁平安装包布局也可能不同。迁移前按运行配置核验，不能套用旧的 `C:\wms\instance` 或 `C:\wms\static` 路径遗漏生产数据。环境配置和本机凭证需单独保护，不上传Git。

手动/历史备份、每日自动备份、更新前备份位置及保留策略不同；每日自动备份默认在 `C:\wms_backups`，由 `WMS_BACKUP_DIR` 覆盖。详见 [备份管理说明](docs/BACKUP_MANAGEMENT.md)。活库使用SQLite backup API取得一致快照，不能只复制.db忽略WAL；完整性通过也不能代替恢复演练。生产恢复必须明确授权，测试恢复显式指定隔离目标，禁止使用默认生产路径做演练。

## 配置说明

变量名以 `app/config.py`、`app/run_server.py` 及对应模块实际读取为准：

| 环境变量 | 用途 |
|---|---|
| `SECRET_KEY` / `DEV_SECRET_KEY` | 会话密钥；按部署环境使用，不能输出秘密 |
| `WMS_BOOTSTRAP_PASSWORD` | 仅首次创建管理员时使用，不重置已有密码 |
| `DATABASE_URL` | SQLAlchemy数据库地址；默认sqlite:///inventory.db按应用instance目录解析 |
| `UPLOAD_FOLDER` / `LOG_FILE` | 上传目录和日志文件；默认锚定应用目录 |
| `WMS_NO_DB_TOUCH` / `WMS_SKIP_STARTUP_DB_UPGRADE` | 禁止启动数据库升级/初始化；不是禁止所有业务写入；还须核对 `WMS_NO_DB_TOUCH.flag` 标记文件 |
| `SESSION_COOKIE_SECURE` / `WMS_ALLOW_INSECURE_COOKIE` | 生产安全Cookie或受信HTTP显式放行；后者不是默认安全配置 |
| `WMS_SKIP_AUTO_UPDATE` | 跳过启动前自动更新 |
| `WMS_PORT` / `WMS_HOST` | 监听端口和地址；端口默认8080 |
| `WMS_THREADS` | 覆盖Waitress线程数；未设置时按CPU数量自适应，每核4线程，最少4、最多16 |
| `WMS_LOCAL_PRINT_AGENT` | 是否启动内置打印代理，默认开启 |
| `WMS_LOCAL_PRINT_BASE_URL` | 打印代理回连地址，默认本机当前启动端口 |
| `AUTO_BACKUP_ENABLED` / `AUTO_BACKUP_TIME` | 每日备份开关及时间，默认开启、02:00 |
| `WMS_BACKUP_DIR` / `BACKUP_RETENTION_DAYS` | 每日备份位置与保留天数，默认C:\wms_backups、30天 |
| `WECHAT_HELPER_TOKEN` / `WMS_WECHAT_HELPER_PORT` | 微信助手令牌与本机端口，默认端口8765 |

`WMS_DATABASE_URI` 和 `WMS_SKIP_DB_UPGRADE` 不是上述数据库配置与启动保护的有效替代名称。生产禁止关闭CSRF；安全Cookie和显式HTTP放行由生产配置硬校验。标准离线启动使用本机HTTP放行，HTTPS部署按 [服务部署说明](docs/SERVICE_DEPLOYMENT.md) 配置，不能一律写成“仅本地调试”。

生产会话密钥须按当前部署要求显式配置或使用已明确放行的文件持久化方式；不重生成已有secret_key。SQLite连接使用WAL、synchronous=NORMAL、busy_timeout；这些连接设置不能代替一致性备份与恢复验证，不承诺固定性能倍数或固定掉电丢失时间。

## 项目结构

```text
app/
  app.py                    主应用及待分批拆出的历史逻辑；禁止新增路由
  config.py                 运行配置
  run_server.py             Waitress生产入口
  startup_check.py          版本、Git SHA、配置与数据库启动检查
  version.py                应用版本
  requirements*.txt         运行/测试钉版依赖
  models/                   业务模型
  routes/                   业务路由
  services/                 仓库级库存与业务服务
  ai/                       AI识别、工具及助手
  android-native-wms/       Android客户端独立Gradle工程
  templates/  static/       页面与静态资源
  instance/  logs/  backups/ 本地运行数据，不提交
scripts/                    检查、验证与维护工具
tests/                      pytest及独立verify回归
samples/ai_documents/       脱敏golden样本
tools/                      安装、便携包及打印代理工具
docs/ledger/                BUG/AI月度台账及索引
docs/audit/                 审计、复核与整改证据
.githooks/                  本地Git钩子
.github/workflows/          CI配置
```

目录和测试数量持续变化，不在README维护易过时的行数、文件数或通过总数。

## 质量验证与记录

| 内容 | 当前依据 |
|---|---|
| 本地代码规则 | `python scripts/lint_wms_rules.py`；普通模式不等于存量已清零 |
| A11全量库存口径 | `python scripts/lint_wms_rules.py --rule a11 --full-a11` |
| 存量棘轮门禁 | `python scripts/lint_wms_rules.py --full --full-gate`；不是只运行--full |
| 已修BUG静态回归 | `python scripts/verify_wms_bugs.py`，数量以实际输出为准 |
| 全量测试/冒烟/编译 | 当前提交的CI与隔离环境实际结果，不能引用历史绿记录代替 |
| BUG和AI任务状态 | 月度分片及 `docs/ledger/INDEX.md`；查询 `python scripts/query_ledger.py --task <ID>` |
| 审计及整改关系 | [审计索引](docs/audit/INDEX.md)；原始发现须连同后续修复记录阅读 |

历史基线仅用于追溯，不证明当前提交或生产服务健康。Pillow13.0.0生产升级与重启的2026-10-21生效证据见 [复核记录](docs/audit/WMS_AUDIT_REVIEW_20261021.md)。后续版本仍需实际核验。

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
| `WMS_QUALITY_REPORT.md` | BUG 质量月报（类型分布、模块分布、Top 根因），保留最新一期；历史各期在 `docs/archive/WMS_QUALITY_REPORT_YYYY-MM.md` |
| `WMS_STABILITY_BASELINE.md` | 发布门禁覆盖的 10 条关键链路 |
| `DEVELOPMENT_RULES.md` | 开发规范：加功能 checklist、修复 BUG 流程、CI/pre-commit 门禁、防 BUG 规则详解 |
| [前端资源与 CSP](docs/FRONTEND_ASSETS.md) | 公共样式缓存、图表按需加载、默认脚本安全策略及验证入口 |
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
python3 scripts/lint_wms_rules.py --full --full-gate

# 验证 git hooks 是否启用
python3 scripts/check_hooks_installed.py
```

### 测试套件

```bash
# 提交前一键：lint + BUG 回归 + pytest
make check

# 本地全量；CI另按文件分片，参数以工作流为准
python -m pytest tests/ -q -p no:pylama -n 4 --dist loadfile

# AI 子系统全量验证（smoke / core / full 三档）
python3 scripts/verify_ai_all.py --level core
python3 scripts/verify_ai_all.py --level full

# 业务冒烟：先启动隔离测试库服务，显式指定它的端口
python scripts/full_smoke_test.py --base-url http://127.0.0.1:18080

# Linux/CI包装器：同样先配置隔离数据库，自动启停不等于自动隔离
python scripts/run_smoke_in_ci.py
```

`make check`当前封装lint、静态回归和串行pytest；与CI的分片并行参数不同。串行/并行失败都需定位，不能笼统宣称串行结果无效。Windows测试进程使用UTF-8：

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

冒烟脚本会尝试登录并可能创建/修改数据。禁止将上述冒烟默认指向正在使用的生产8080；测试服务须有独立数据库、端口和日志，并关闭打印代理及自动备份等外部副作用。不要把 `run_smoke_in_ci.py` 直接当生产巡检命令。

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

## 本地开发钩子

钩子位于 `.githooks/`，启用和检查步骤见前部“开发与发布规则”。pre-commit按实际扫描范围检查规则；pre-push检查分支和CI。不要用 `--no-verify` 代替验证。推送后验收三个必需工作流的最新结论，Android是否产生新运行由路径过滤和定时触发决定。

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
| A13 | WMS_BUG_BASELINE.md及docs/ledger/bugs/新增BUG条目必须含「生效确认」字段 |
| A14 | scripts/ 下新增 app 引用脚本必须显式放行生产硬门禁 |

> A8/A9/A10/A13/A14 仅对 git staged 新增行强制；A11 双模式：pre-commit 查新增行 + CI `--full-a11` 全量。业务 JS 的非 GET 请求必须走 `WMS.api.post/put/delete`（`app/static/js/api.js`），白名单外裸调 `fetch` 会被 pre-commit 拦截。

启用钩子：`bash .githooks/install-hooks.sh`

### 修复 BUG 流程

1. 登记前先检索台账查同根因历史（R6），运行受影响模块基线；同模式复发必须排查所有同类消费点。
2. 在BUG台账分片 `docs/ledger/bugs/entries-<当月>.md` 登记（`### BUG-YYYY-MM-DD-NNN: <标题>`，含「生效确认」）；查询 `python scripts/query_ledger.py --task <ID>`，新增记录后按需要重建索引。
3. commit message 关联 BUG ID：`fix: BUG-2026-09-29-NNN xxx`
4. 加回归测试，且回退修复后新测试必须失败（回归锁自证，R8）
5. 全量 + 相邻模块回归通过、lint 0 违规、CI 三工作流转绿后，改状态为"已修复"

### 什么时候更新README或AGENTS

每次修BUG更新BUG台账、回归和生效确认；只有使用步骤、配置、安装启动、功能入口或项目事实变化时才更新README/对应专题文档。代理规则变更写AGENTS并注明日期，AGENTS单独提交。无需把每条修复都复制进README。

物料档案的人工选择与合并操作见 [物料合并说明](docs/MATERIAL_MERGE_GUIDE.md)。

自动启动与新建Windows服务的配置及边界见 [服务部署说明](docs/SERVICE_DEPLOYMENT.md)。

备份管理可统一查看手动、每日自动和更新前备份，来源/保留策略与校验操作见 [备份管理说明](docs/BACKUP_MANAGEMENT.md)。
