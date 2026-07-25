# WMS 仓库管理系统

这是一个基于 Flask 的单人 WMS，面向低压成套电气设备企业。当前重点是快速登记物料出入库，并通过拍照识别、AI 建议物料编码和草稿生成减少仓管员录入工作。

## 主要功能

- 基础资料：物料、分类、单位、供应商、客户、仓库、库位、员工、部门。
- 库存管理：库存查询、库位库存、库存流水、库存预警、期初库存。
- 入库管理：采购入库、产品入库、其他入库和入库单打印模板。采购入库可手工录入，采购订单是可选来源。
- 出库管理：领料单、其他出库、销售出库、售后出库和出库单打印模板。
- 盘点管理：库存盘点、扫码盘点、盘点差异处理。
- 库内业务：调拨单、调整单、库存扣减和库存增加流水。
- 采购业务：采购申请、采购订单、采购到货执行跟踪。
- 生产与外协：BOM、生产领料、外协发料、外协收货、外协进度。
- 移动端接口：移动扫码、物料查询、扫码提交。
- 系统管理：用户、登录日志、操作审计、系统参数、通知任务。
- 数据导入导出：Excel 表格导入、导出和前端表格处理。
- 单据效率：明细字段设置、复制行、合同/工程/仓库向下填充，合同编号和工程名称按明细行保存。
- 单据下推：采购入库和其他入库可按明细及数量下推领料单、其他出库单或售后出库草稿。
- 客供登记：其他入库明细可勾选客供并选择客户；当前尚未做库存所有权隔离，客供行禁止直接下推普通出库。
- AI 单据助手：上传照片或截图后识别明细、匹配已有物料、人工确认新物料编码，并生成入库或出库草稿。

AI 只能创建和检查草稿。完成、审核、作废、删除以及库存变动必须由操作人员在业务页面手工执行。

## 技术栈

- Python 3.11
- Flask 3.0
- Flask-SQLAlchemy
- SQLite 默认本地数据库
- Waitress 生产 WSGI 服务
- APScheduler 定时任务
- openpyxl / pandas / reportlab / qrcode 等业务工具库

依赖清单位于：

```text
app/requirements.txt
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

访问地址：

```text
http://127.0.0.1:8080/login
```

默认管理员账号：

```text
用户名：admin
初始密码：优先使用 `WMS_BOOTSTRAP_PASSWORD`；未设置且首次创建管理员时为 `admin`
```

如果设置了 `WMS_BOOTSTRAP_PASSWORD`，系统首次创建管理员时会使用该环境变量。安装和启动不会重置已有管理员密码。

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

该目录内包含 Python 解释器、依赖包、WMS 程序和启动入口。把整个 `dist\WMS\` 文件夹复制到用户电脑后，用户只需要双击：

```bat
启动WMS.bat
```

或：

```bat
WMS.exe
```

然后浏览器访问：

```text
http://127.0.0.1:8080/login
```

默认管理员账号：

```text
用户名：admin
初始密码：优先使用 `WMS_BOOTSTRAP_PASSWORD`；未设置且首次创建管理员时为 `admin`
```

便携包由 `tools\build_portable_dist.ps1` 生成，`dist/` 是构建产物，不提交到 Git。

### 源码离线安装

项目根目录提供离线安装入口：

```bat
install.bat
```

安装脚本会将系统安装到：

```text
C:\wms
```

并使用本地 `wheelhouse` 安装 Python 依赖。安装完成后可通过以下脚本启动：

```bat
wms.bat
```

或：

```bat
cd /d C:\wms\app
start_wms_offline.bat
```

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
SQLALCHEMY_ECHO             是否打印 SQL，true/false
WECHAT_HELPER_TOKEN         微信助手访问令牌
WMS_WECHAT_HELPER_PORT      微信助手本地端口，默认 8765
WMS_BASE_URL                WMS 主服务地址
```

生产环境应显式设置 `SECRET_KEY` 和相关访问令牌，不要使用弱默认值。

## 项目结构

```text
C:\wms
├── app/                         应用主目录
│   ├── app.py                   Flask 主程序、模型和路由
│   ├── config.py                配置
│   ├── run_server.py            服务启动入口
│   ├── requirements.txt         Python 依赖
│   ├── templates/               页面模板
│   ├── static/                  前端静态资源
│   ├── instance/                本地数据库目录，不提交
│   ├── logs/                    运行日志，不提交
│   └── backups/                 数据备份，不提交
├── scripts/                     检查和验证脚本
├── runtime/                     离线运行环境资源
├── tools/                       安装和维护工具
├── wheelhouse/                  离线 Python 依赖包
├── build_portable_dist.bat      生成 dist\WMS 便携包
├── install.bat                  离线安装入口
├── wms.bat                      快速启动入口
└── README.md                    项目说明
```

## 部署说明

腾讯云 Windows 服务器部署说明见：

```text
上线部署说明.md
```

公网部署时通常由 Nginx 将域名转发到本机 WMS 服务：

```text
http://127.0.0.1:8080
```

## 项目文档

当前有效文档入口：

| 文档 | 用途 |
|---|---|
| `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` | 唯一 AI 开发台账：已有能力基线、真实待开发任务、依赖、验收和完成记录 |
| `AI_PERMISSION_MATRIX.md` | AI 能力角色、风险等级和人工确认边界 |
| `WMS_BUSINESS_SCOPE.md` | 当前单人 WMS 业务口径和客供料处理边界 |
| `PRODUCTION_DEPLOYMENT_CHECKLIST.md` | 每次生产发布前重新填写的验收模板 |
| `WMS_BUG_BASELINE.md` | 已核验 BUG、风险、误报和暂缓项基线 |
| `上线部署说明.md` | 腾讯云 Windows 部署和数据保护说明 |
| `AGENTS.md` | AI 和开发代理必须遵守的项目规则 |
| `docs/archive/` | 已结束的 BUG、巡检和专项审计历史报告，仅供追溯 |

为避免计划冲突，仓库只保留 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 作为 AI 开发主计划。

## 开发校验

统一使用项目 Python 入口执行检查：

```bat
.\scripts\python.cmd -m compileall -q app scripts
.\scripts\python.cmd scripts\verify_ai_all.py --level full
```

BUG 基线和候选风险检查：

```bat
.\scripts\python.cmd scripts\verify_wms_bugs.py
.\scripts\python.cmd scripts\scan_wms_risks.py
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
.env
secret_key
wechat_helper_token
```
