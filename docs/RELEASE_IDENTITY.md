# 发布身份与暂停功能状态（2026-11-05）

本项对应独立审计IA-07/08。管理员从“系统参数 → 发布与运行状态”打开只读页面；普通仓管没有管理员页权限。页面不显示数据库地址、磁盘路径、Cookie值、密钥或外部服务凭据。

## 一份制品如何识别

`wms-release.json`记录完整源码来源SHA、界面来源SHA、明确的覆盖目录、应用目录、封存范围、每个文件的长度和SHA256、实际Python/固定依赖版本，以及制品声明的外部任务暂停策略。清单的规范JSON摘要是制品ID。源码SHA是制作时的来源记录；实际覆盖或生成文件以各自摘要及制品ID核对，不能把SHA标签当作所有字节均等于Git源码。此格式提供完整性核对，不是数字签名。

Windows构建从干净的已提交app/tools导出，完成解释器安装、实际依赖检查和启动器生成之后封存，使用当前完整Git SHA填入来源。标准包没有独立覆盖时，覆盖清单为空；已有多层制品需显式把覆盖、受控启动器及实际运行目录纳入范围，不能只登记后端源码。

实例数据、上传、日志、备份、凭据文件及可重新生成的字节码不属于程序制品；公开的certifi CA证书仍属于运行依赖。校验拒绝路径越界、符号链接/目录联接、重叠范围、大小写冲突，以及封存范围中的额外程序文件。不要在已运行的目录原地更新封存文件，应另建完整新包。

## 新包制作与空目录验收

以下示例只适用于新的隔离构建目录，不能指向生产目录：

```powershell
# 依赖按项目便携构建流程先备齐；本命令不负责生产部署。
./tools/build_portable_dist.ps1 -DistDir ./dist/WMS-new -PauseExternalOperations
./dist/WMS-new/python/python.exe ./dist/WMS-new/tools/manage_release_manifest.py verify --root ./dist/WMS-new
python tools/check_portable_runtime.py --package ./dist/WMS-new
```

构建默认保留普通部署行为；`-PauseExternalOperations`为该新制品封存暂停策略。便携验收把整个制品复制到新空目录，先执行既有依赖门禁，再校验同一完整清单，然后才在临时副本初始化合成数据库并启动。原包和现有数据库均不作为测试写入对象。版本已递增为2026.11.2，不能用2026.11.1的既有标签跳过本项实际构建。

`run_server.py`在取得数据库运行锁及导入WMS之前校验制品和实际解释器/依赖；应用加载时还确认清单对应实际app目录。清单未登记时保留开发/旧部署兼容，状态页明确提示“未登记”；如果显式指定清单但它丢失、损坏或不匹配，则拒绝启动，不能退回未登记状态。启动时校验时间和当前非敏感配置指纹分开显示，刷新页面不会声称重新扫描全部磁盘文件。

已有多层制品可使用同一工具，所有输入须是相对该制品根目录的路径：

```powershell
python tools/manage_release_manifest.py create --root ./isolated-release --source-sha <完整来源SHA> --ui-sha <完整界面SHA> --application-root recovery/current/app --include recovery/current --include overlay --include runtime --include launch.cmd --overlay-root overlay --runtime-report ./accepted-runtime-report.json --external-operations-paused
python tools/manage_release_manifest.py verify --root ./isolated-release
```

示例的include必须按该制品实际依赖补齐受控启动器、辅助模块和其他程序文件，不可照抄后遗漏实际消费点；清单已存在时工具拒绝覆盖。使用该类布局时，将`WMS_RELEASE_MANIFEST`明确指向其清单；普通便携布局自动发现app同级清单。

## 暂停状态与业务边界

清单声明暂停、`WMS_EXTERNAL_OPERATIONS_PAUSED=1`，或已有受控启动器的`WMS_RELEASE_STATE_ROOT`标记，任一成立即保持暂停；显式环境值0不能覆盖清单或既有保护。普通部署无这些条件时仍由原权限和业务开关决定可用性，页面不会据此声称打印机已在线或微信已送达。

暂停时：微信配置保存、实际发送/重发、助手任务获取、设备队列写入及GET/HEAD任务认领被拒绝；自动打印和内置打印代理不启动，微信定时/完成触发不发送，受保护模式的自动图片清理不执行。微信页面打开不会自动创建默认配置或联系助手。双通道建队列接口保留原会话CSRF校验；暂停不是关闭鉴权、CSRF或断言。

页面保留查看记录和设备配置的入口，说明暂停；微信发送/保存按钮禁用，设备守护页不轮询或认领，物料勾选不会把暂停按钮重新启用，入出库单及手机扫码页的队列按钮也标明不可用。单据登记、库存查询、模板预览、浏览器直接打印、导出和已有权限继续使用原路径。

## 上线、恢复与回退

发布新包、停旧服务或调整真实任务需独立生产授权；本项代码交付不自动部署、不迁移业务库、不恢复数据库、不改账号。保留当前完整发布制品及服务任务定义，回退按整份制品和原动作核对，不能只替换app.py或漏掉覆盖和依赖。

真实微信恢复须核对助手/企业微信通道、目标收件人、人工确认和失败重试；设备恢复须核对工作站、令牌、路由、重复认领和实际出纸结果。它们分别授权、分别现场验收，本页不提供一键全开。硬件不可用时只记录软件验证，不把浏览器打开模板当成已出纸。
