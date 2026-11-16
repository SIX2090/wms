# WMS生产代码部署记录（2026-11-16）

> 后续部署：同日17:09:54（北京时间）已在用户明确授权下切换到物料防删版本813fb4ef，当前服务PID16728，详见[物料防删生产部署记录](2026-11-16-material-protection-production.md)。本文保留当日早间f161部署的原始证据与历史边界。

任务RELEASE-DEPLOY-20261116-001。状态：服务器代码已切换并完成受保护启动和被动身份核对；真实业务、手机与外设验收分别待确认。关联[候选准备记录](2026-11-15-production-release-preparation.md)与既有AI-APP-AUDIT-FIX-20261115-001，不新增业务能力。

## 授权与数据边界

用户明确要求“部署”，随后确认“允许正常启动访问；禁止迁移、初始化、回填、恢复、备份及测试单据”。本轮仅使用原受保护启动器对现有数据库做只读结构检查，检查完成后由WMS恢复正常业务请求。未运行数据治理SQL、数据库拷贝/备份/恢复工具、测试单据、生产登录/HTTP冒烟、微信发送、打印或APK安装；未修改账号密码和数据库保护。不能声称数据库完全未访问，也不以部署前后数据摘要冒充无变化证据。

## 已上线的精确版本

- 后台及UI来源：f161cbd3c7f15326eedad3d612ea3a7a91e7d6f7；程序目录C:/wms_releases/20261116_native_audit_f161cbd3。使用冻结提交与官方Windows76运行时，不发布共享C:/wms工作树或后续main改动。
- 制品ID：e88b90b5b02423f6fc2987f455eba72d5f909f76d935ea7288854f8f3f8e91ca；7430个不可变文件、4份兼容覆盖、Python3.11.9、34项依赖。APK54/3.9.30置于下载目录，未安装到手机。
- 发布ZIP：WMS-2026.11.76-f161cbd3-deployment.zip，78,217,897字节、7431项；SHA256=f93ed9f72ce8974c979c12c89be3fcd73547a8557abc2c7340d44813f3afc864。组合封包不冒充官方原ZIP。
- 代码目标的[WMS CI](https://github.com/SIX2090/wms/actions/runs/43719970569)、[WMS AI Verification](https://github.com/SIX2090/wms/actions/runs/43719970587)成功；Android按完整祖先/路径与对象证明复用[dbe构建896](https://github.com/SIX2090/wms/actions/runs/43718443363)。准备期544模块回归、10项真实Chrome检查与程序回退证据沿用，不重复累计。

## 实际执行及保护证据

1. 原服务仍运行时，将纯程序包解到独立新目录并核全文件；6个既有持久目录只建立原位置映射，不复制其中内容。
2. 第一轮预检在应用/数据库导入之前因程序清单拒绝目录联接而停止。准备包的broad recovery/current范围与持久映射冲突；按现役制品已有协议，将这一范围精确展开为654个原程序文件。7430项size/hash集合完全不变，原源码注入集合校验、链接检查、启动SQL authorizer及写保护均保留；仅清单includes和制品ID变化，原准备ID1f7b13bebd38246103d21504e8a861102bd8ef560b0c565e3ff52c421f3b2ee1不再作为上线ID。26项发布清单测试通过，新ZIP逐项回读通过。
3. 第二轮沿原launch.cmd current --preflight成功：schema_check=passed、read_only_startup=true、listener_started=false；97次启动业务行读取被authorizer拒绝，网络/凭据生成/文件写入/子进程拒绝计数均0。此时原生产服务尚未停止，没有用取消门禁获得通过。
4. 停止已核身份的原业务PID8896后，原监护按已稳定超过300秒的既有策略自然进入waiting/restarts=1；随后停止原任务，未手写状态、使用reset-budget或改变重试参数。仅将动作文件中的launch路径、工作目录、stdout目标改为新制品，原计划任务注册/解释器/监护入口/配置保持。
5. 切换动作文件时File.Replace的空backup参数封送失败，旧动作未改变、新任务尚未启动；核对无监听、原任务已停、原动作及候选临时文件摘要后，使用同目录File.Move覆盖完成切换。失败和纠正记录保留，没有绕过数据库或监护保护。
6. 只启动原WMS-Warehouse任务一次。2026-11-16 08:01:01（北京时间）观察到127.0.0.1:8080由新PID9372监听，任务Running，监护running/restarts=1。固定入口、解释器、完整SHA、父链、进程时间及任务归属的被动身份核对identity_verified=true；启动生成的runtime-mode证明后台/UI均f161、制品ID为上述新ID、维护禁用及原认证配置保留。
7. 上线后只读取程序清单，重新验证新7430及旧7525个程序文件全部完整。未为验证而再次停机或执行生产回退；原完整旧制品仍可用于程序回退。原入口仅import app，不走启动备份/通知scheduler的__main__块；本轮没有创建备份或微信调度任务，也没有擅自改动机器上其他既有计划任务。

## 回退与未验边界

旧完整制品：C:/wms_releases/20261113_toastfix_afe8c9ad，后台3652607ac6f381dd39e05e183c276dba443f508a、UIafe8c9ad89d0d9bc408482ba88846a9b9133b307，制品ID36d24a2bb6f7d4c6aa15a2e6f94beb513c714984c52fc6a6f07e54b623880722。原动作、任务XML及被动进程快照已留在外置证据目录。回退必须选择完整旧程序组合并沿原任务、原监护保护；不使用候选旧rollback参数，不恢复或覆盖数据库，重试耗尽不得绕过。

已验收的是受保护结构检查、程序完整性、真实启动与被动运行身份；未做生产登录/HTTP业务测试、真实单据、库存对账、微信、打印、手机安装、相机或系统回收验收。APK可下载不代表手机已安装；A01～A12的原生设备生效仍待人工确认。后续main及未提交视觉改动均未被本次发布。

外置证据根：C:/Users/Administrator/.codex/visualizations/2026/11/15/01a1de80-0f3b-75d1-bcbd-a7f2c7e704aa/release-deployment-20261116。包括deployment-receipt.json、deployment-repack-proof.json、protected-preflight-v2-result.json、cutover-live-process.json、passive-live-identity.json、live-runtime-mode.json、post-deployment-program-artifacts.json及原动作/任务快照。程序与状态目录的真实业务内容未复制入证据包。

生效确认：服务器于上述北京时间由原任务成功启动f161，PID9372身份相符；人工正常使用及手机/外设待确认。部署文档自身的提交/推送/CI另行精确验收，不将文档提交当作线上源码版本。
