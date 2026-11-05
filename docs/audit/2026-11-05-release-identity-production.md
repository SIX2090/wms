# 整改-04生产部署与生效验收（2026-11-05）

用户明确授权“先完成第4项的生产部署与生效验收，再进入第5项”。本次仅部署已交付的 FEAT-2026-11-05-108/109，并保留已上线的产品入库模板、外观覆盖、图片联网与生产保障；未修改生产业务记录、库存、账号或数据库结构，没有执行生产业务测试。

## 实际生效的制品

- 2026-11-05 **19:19:12（北京时间）**完成启动和本机验收；成功切换阶段94秒。程序和界面来源均为 `256e05abfa92463e956d18a527abc04b545fa908`，第4项产品来源为其祖先 `3be6e2229876a1c9d2e372e9c2225c7db3a68863`。合同联动修复9e5d6db2属于另一批，未冒充已随本次部署。
- 生产目录 `C:/wms_releases/20261105_audit04_256e05ab`，实际入口 `verified_entry.py`，独立解释器 `python/python.exe`。制品 ID：`1b03590c14aafdfe373625fa9a9491b538d93c0a31441b63bf72626faa48b2be`。
- `wms-release.json`封存 **12,317份文件、39份覆盖文件、34项固定依赖**；Python3.11.9，PDF/TLS实际导入路径均来自本制品。程序来源记录767文件；原有APK另按摘要纳入。私有持久目录通过明确映射继续使用原状态，实例数据、上传、日志和备份不作为程序文件封存。
- 程序文件逐项来自目标Git对象并核对SHA256；覆盖层保留既有主题并逐项核对。受控启动器、覆盖清单、独立解释器及库文件也纳入同一清单。入口在数据库租约及应用启动前校验，并核对源码范围没有额外程序文件；应用加载后再次核对实际身份，运行回执记录实际PID、制品ID及配置指纹。
- 本生产制品包含现场覆盖层和受控启动适配。公开Windows2026.11.2的7328文件发行制品及其ID仍按[软件交付证据](2026-11-05-release-identity-and-paused-operations.md)独立记录，不能把两个封存范围的身份混用。

## 验证与生产边界

1. 同一实际制品先映射到全新合成库，创建97张模型表和专用测试账号。真实Chrome13项检查通过、页面错误0：从系统参数实际点击进入/刷新，制品ID与来源SHA显示正确；普通仓管访问管理员状态页403；微信表单禁用及实际run_now请求503；设备页跨轮询周期没有认领请求，GET认领503。合成库存为0，出入库/流水/队列/微信配置及日志均0。没有把测试账号用于生产。
2. 停服前完成生产只读预检，完整身份已登记、HTTPS安全Cookie开启、暂停策略为真，结构门禁通过，未开启第二个监听服务。受控启动器禁止启动期业务行读取，97次读取尝试被拦截；没有把“有读取尝试”写成“已读取业务行”。既有缺外键警告仍是警告，本次未自动迁移或修补历史结构。
3. 启动后监听PID10300与运行回执一致，制品ID与预检、合成Chrome验收相同；源码/UI均为256e05ab，配置指纹 `f0bde287e581d53bc65e1b8ae5837b31326d4dab977af23afd1dd789ed35e5ab`，Secure/HttpOnly及启动禁止自动维护为真，SameSite=Lax，外发和设备队列保持暂停。
4. **19:26公网真实Chrome**访问 `https://gd2026.top/login` 返回200，证书正常校验，Cookie为Secure/HttpOnly/Lax，匿名状态页302返回登录，脚本错误0。没有登录生产账号、提交表单或执行写操作；浏览器预设阻止非GET/HEAD和设备队列入口，实际拦截请求为0。登录是独立模板，未把不存在的主界面暂停meta当验收项。管理员页面实际交互来自前述同一制品合成库，生产暂停状态来自实际进程回执，二者分别记录。
5. 原 `WMS-Warehouse` 任务定义及每日备份任务定义均未变；服务无限时、IgnoreNew，原SYSTEM监护接管新入口。监护running、计数2，来源为本次计划启动，未改写成0或补造状态。每日02:00、保留30天继续生效，下次任务为2026-11-06 02:00。

## 备份、纠正与回退

切换前实际SYSTEM在线备份任务返回0，最新备份 `auto_daily_20261105_191735_976871_inventory.db` 为5,976,064字节，SHA256 `20c31b336d75206329891cda2f369ed9628a97266df2aa86bab35771ef6cbdfb`；只打开备份校验，完整性ok、100张表。源库由既有工具以mode=ro在线快照，不对业务源库执行恢复或写入。

首次切换停旧服务后，PowerShell向File.Replace传入空值被转换为空路径，原子替换拒绝，新启动动作未生效。脚本已恢复原任务启动，复核原动作摘要 `e2a602449ca24b493d32331ca3ee9a8ba89af19ff2f63a120e437c2f5fb6afe1`、原产品入库版本及HTTP200。随后在独立文件中提取同一替换函数，先复现原失败并确认旧文件未变，再验证显式备份路径的新配置替换、原字节备份及反向回退全部成功，才重新切换。首次失败和两次备份记录保留，不写为“一次成功”。产品源码及断言未改。

新启动动作原子切换到新目录，保留替换前原文件。失败路径恢复整份原动作、由原监护任务重新启动；不恢复数据库。原 `20261105_product_receipt_256e05ab` 是直接代码回退目标，`20261105_audit03_85df6437` 仍承载监护/备份解释器依赖，`operations_c6048a09` 仍承载运维源文件，均继续保留，不以清理临时目录方式删除。后续业务发布须沿用完整制品校验，并在程序/覆盖/启动器变更后重新封存，不退回未登记身份的布局。

## 门禁、证据与当前进度

部署前最近main为9e5d6db2，[WMS CI42016754233](https://github.com/SIX2090/wms/actions/runs/42016754233)、[AI42016754278](https://github.com/SIX2090/wms/actions/runs/42016754278)全部success后才切换；[Android41971520345](https://github.com/SIX2090/wms/actions/runs/41971520345)成功祖先，Git对象、祖先关系与Android源码/工作流输入无变化证明成立。该运行中CI曾阻止第一次切换准备，未绕过门禁。生产部署目标256e05ab自身[CI42010690371](https://github.com/SIX2090/wms/actions/runs/42010690371)、[AI42010690223](https://github.com/SIX2090/wms/actions/runs/42010690223)成功，实际第4项全量及Windows构建证据见软件记录。

现场证据在 `C:/Users/Administrator/Documents/Codex/2026-11-05/wms-operations-recovery/audit04-production`：`sealed-artifact.json`、`actual-runtime.json`、`actual-artifact-browser.json`及截图、`synthetic-business-state-proof.json`、`production-readonly-preflight.log`、`activation-first-attempt-failure.json`、`atomic-action-regression.json`、`activation-result.json`、`before-switch-backup-proof.json`、`public-browser-acceptance.json`、`operations-after-activation.json`及任务原定义。未把此前清理后丢失的审计目录日志补造为现存证据。

第4项产品交付及本次生产生效验收完成，前四项均有生产生效记录。第5项进入只读清单冻结，见[全站前端冻结范围](2026-11-05-frontend-inventory.md)，尚未完成模块迁移，不自动提高评分。本回执为纯文档批次，统一提交推送后仍按自身精确SHA验收文档CI。
