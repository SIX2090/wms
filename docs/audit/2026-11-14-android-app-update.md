# WMS 手机端自动更新（新旧 App 并存）

2026-11-14，任务 `MOBILE-UPDATE-20261114-001`。本阶段基线 `ee24269b8d5f22eb0ade77d8ed05eb81fb10be75`。

## 授权与当前状态

用户在核实原 CI 的两份同版本 APK 使用不同临时签名后，明确批准建立并备份长期固定签名，
改用新旧 App 并存方案；随后明确批准将该签名私钥及密码保存到 SIX2090/wms 的
Actions Secret `WMS_MOBILE_SIGNING_BUNDLE`。GitHub 页面已显示 Repository secret added。
这是对原方案“沿用旧签名、首次覆盖安装”的明确变更，不尝试覆盖签名不兼容的旧 App。

本阶段代码与适用本地验证完成，尚未用新目标 SHA 验收，不能将前一阶段成功测试或旧绿视为交付。
Android 41 / 3.9.17；Windows 2026.11.53 为本批发行版本。

## 使用方式与数据边界

- 新 App 包名 `com.factory.wms.mobile`，桌面显示“WMS 手机端”；namespace 仍为 `com.factory.wms`。
- 第一次从本阶段验收后提供的**固定 APK 链接**下载安装新 App，旧“WMS扫码”保留。
- 在新 App 正常登录原服务器和账号，服务端数据按现有权限可用。两个 App 的本地存储彼此隔离，
  **新 App 不自动读取旧 App 的登录、草稿或离线队列**。旧待办留在旧 App，用户先核对，避免两边重复录单。
- 新 App 后续覆盖升级保留自己的登录、草稿、Room v3 与离线队列，不要求清空队列或卸载。
- 启动/回前台按六小时尝试间隔检查；“我的 → 应用信息 → 检查更新”可立即手动检查。
- 发现新稳定版本自动下载至私有目录，显示进度/失败/重试；校验通过后等待当前提交或队列请求结束。
- 首次需在本 App 的系统设置允许安装未知应用，返回后重新核对。Android 12+ 请求免确认自更新，
  实际是否允许由系统条件决定；任何版本均兼容系统人工确认、取消与失败。后台只保留提示，回前台继续。
- 安装使用 PackageInstaller.Session，不扩大 FileProvider 目录、不请求无关存储权限。下次打开按实际 versionCode 确认升级。

## 签名与稳定通道

公开证书 SHA-256：`2f50f0d7552be34d83316ee5d1e88b328a5914b1a08c552f5d0d0f2dd5619e4c`。
新固定 RSA 3072 私钥及恢复材料仅在仓库外受限目录和用户本机备份中，未打印或提交。
同机备份不等于异机灾备；维护人应将整个备份目录安全复制到独立介质，不把私钥/密码发到聊天。
CI 从加密 Secret 恢复到 runner 临时目录，先用 keytool 核验证书指纹，密码通过环境变量传递并逐项 mask。
缺失、损坏或证书不符立即失败，不生成临时发行签名；候选 APK 还经实际 aapt/apksigner 再核对。
历史入库后删除的旧 keystore 不恢复、不复用。

候选资产：`android-apk-<run_number>-attempt-<run_attempt>`，元数据绑定完整提交 SHA、实际包名、
versionCode/versionName/minSdk、固定资产 URL、大小、SHA-256、签名证书与更新说明。
候选的 latest 别名只沿用既有人工下载入口，**手机自动更新不使用 latest**。

稳定记录：GitHub Releases 中 `android-mobile-stable-v<versionCode>-<40位SHA>` 的 JSON body。
App 只访问固定仓库 SIX2090/wms 的该 tag 前缀，再核对 tag/body/target SHA；发行流程使用该仓库 Actions 权限，
不向手机下发 GitHub Token。独立 OkHttp 无 WMS 拦截器、Cookie 或 Bearer，所有下载跳转均校验 HTTPS/443 和精确托管域名。
APK 经大小、哈希、包名、版本、minSdk 和 apksig 密码学签名验证，证书须兼容当前已安装 App。
元数据不能使不同签名 APK 变为合法更新；发布端另固定新证书身份。

提升必须核对**同一完整 SHA、main、自有仓库来源**最新的 Android APK Build、WMS CI、WMS AI Verification，
全部 completed/success，并在写记录前再次核对 run/attempt。失败、缺失、取消、运行中或查询异常均不提升。
不可变记录只新增不覆盖，手机取最大 versionCode；乱序构建不能把有效版本回退。
每个 SHA 独立协调发布，同一 SHA 重跑的候选资产不会覆盖原不可变 release；无稳定记录时当前 App 正常可用。

## 实现范围与验证

独立 update 模块、应用生命周期、Profile 应用信息、提交/回放协调、Manifest、Gradle、发布工作流及脚本、
对应真实 JVM/Compose/Room/apksig 测试及发行协议测试。新增 apksig 8.7.3，与现有 AGP 版本相同，
用于真实签名验证。更新元数据显式 JSON 键避免混淆破坏协议。不改变库存算法、单据状态或服务端权限。
`app/app.py` 未修改，CI 行号锚点未移动。无数据库迁移改动或 destructive migration。

冻结产品/测试/工作流版本的本地验证：

- 私有 Android 副本 testReleaseUnitTest：23 类、189 项，0失败/错误/跳过；lintRelease 通过。
- 发布协议 11 项、签名恢复 3 项 unittest 通过（真实行为、合成凭据，不导入 WMS）。
- 固定签名实际 keytool 导出核对通过，主私钥与备份、恢复密码逐字节一致，未输出敏感值。
- 6 个相邻源码模块 49 个原测试函数通过；另 6 个原测试函数参数实例以真实私有 Git 仓库
  验证 Android 输入改动不得复用旧构建、文档祖先可证明复用。未把源码检查当成真实手机验证。
- 暂存 A1–A14、全量 A11、严格 AI 台账及源码编码检查通过。
- 私有 main 仓库对本批 39 个文件（含范围登记）实际整批 revert/恢复，逐字节一致；旧工作流不能通过
  固定正式签名约束，去除发布绿灯判断的变异会使行为测试失败，恢复后通过。
- 私有正式签名 assembleRelease 成功（含真实 R8 压缩和签名）。aapt/apksigner 核实新包名、41/3.9.17、minSdk26、上述固定证书；本地 APK 25,545,011 字节，SHA-256 `b6b897104cd7b77bfb94e5c86304e8645a21729e29bd8344321042ca57a8c44d`。本地核验元数据使用明确合成提交占位，不作为发行来源凭据；CI 将对实际提交重建并绑定元数据。完整目标 CI 尚未核实。
完整 Flask 测试交给真实隔离 CI，宿主不直接 import app、不伪造隔离标志。
完整目标 SHA、实际 push 输出、三个工作流链接和稳定记录待本阶段验收回填。

官方依据：[SessionParams.setRequireUserAction](https://developer.android.com/reference/android/content/pm/PackageInstaller.SessionParams#setRequireUserAction(int)) 与 [Session.commit](https://developer.android.com/reference/android/content/pm/PackageInstaller.Session#commit(android.content.IntentSender))；API31+ 免确认是有条件的，自更新仍须兼容 STATUS_PENDING_USER_ACTION。目标SDK35的安装回调按要求使用显式、可变 PendingIntent。

真实手机尚未安装：首次并存、安装权限、取消/失败恢复、厂商免确认条件、升级后本地数据保留仍待设备验收。
无需部署或重启 WMS 服务即可由 GitHub 提供更新；本任务未执行生产服务、数据库、账号密码或手机操作。

---

以下保留前一阶段的真实失败与回退证据，不能作为本阶段目标的成功凭证。

# 前一阶段：等待原签名并已回退

日期：2026-11-14（Asia/Shanghai）。任务 `MOBILE-UPDATE-20261114-001`。

## 前一阶段结论

**功能尚未交付。** 已实现并测试的更新代码因缺少原签名材料，未能通过完整 Android 构建门禁，
已按 R8 整批撤回。当前仓库恢复原 Android 39 / 3.9.15 行为，没有启用自动更新。
本次回退的 Windows 发行版本前移为 2026.11.52，仅用于满足已有版本不可复用门禁，
不表示手机更新功能完成。回退目标完整 CI 已通过，证据如下；签名前置条件仍未满足。

回退目标 `4d9e4f86e32e9be22347ddfe2f410e00604157e7` 实际正常推送为
`fd56b6dd..4d9e4f86 main -> main`，本地 HEAD、origin/main 和实时远端一致。

| 回退验收 | 运行 | 结果 |
|---|---|---|
| Android APK Build | [43567672542](https://github.com/SIX2090/wms/actions/runs/43567672542) | completed/success，原 Android 39/3.9.15 构建 |
| WMS CI | [43567672637](https://github.com/SIX2090/wms/actions/runs/43567672637) | completed/success |
| WMS AI Verification | [43567672566](https://github.com/SIX2090/wms/actions/runs/43567672566) | completed/success |
| 性能记录 | [43567672635](https://github.com/SIX2090/wms/actions/runs/43567672635) | completed/success |

这些结果证明回退基线恢复，不代表撤回的自动更新功能已完成。
本次收口仅修改两份 Markdown，其自身提交按文档分流独立验收，不借旧绿冒充本提交通过。

## 原始目标与实现快照

开工基线 `349850df5423a6abc8e4d220f27fe39a7ec98b38`。
登记检查点 `1e738466475961f4ecb475d54b931a35a8827b1a`、
`fc1e4229afa0294980dc700869b70209b049e038`；
实现目标 `fd56b6dd947971ff6998b6fbf6cf2f745988ba25`，正常 push 输出为
`349850df..fd56b6dd main -> main`，已核对远端一致。

该实现包含：固定仓库的不可变稳定版本记录、精确 SHA 三工作流门禁、
下载/重定向/包名/版本/哈希及 apksig 密码学签名校验、PackageInstaller 安装和确认回调、
原生提交与真实 Room 回放互斥、进程恢复及“我的 → 应用信息”更新入口。
元数据使用显式 JSON 键，保留草稿、队列和凭据；不修改服务端库存或单据业务规则。

实现仍可从上述历史提交审阅和恢复。仓库外另保留完整补丁及私有逆序验证快照，
后续恢复必须重新核对当前 main、版本、签名和完整 CI，不直接复用旧绿或旧版本号。

## 已完成的验证

- 私有 Android 副本：完整 188 项测试、23 类、0失败/错误/跳过，lintRelease 通过；
  末次更新模块 27 项专项通过，两组存在重叠，不相加。
- 精确实现 SHA 的 Android CI：unit-test 实际 **189 项 PASSED**，lint 成功；
  [Android 43566988062](https://github.com/SIX2090/wms/actions/runs/43566988062) 整体失败原因见下。
- [AI 43566988179](https://github.com/SIX2090/wms/actions/runs/43566988179) completed/success。
  [WMS CI 43566988091](https://github.com/SIX2090/wms/actions/runs/43566988091) 最终 completed/success；
  Android 构建门禁仍失败，因此整个功能目标不算验收。
- 发布协议 11 项 unittest 和 6 模块源码/协议相邻共 64 项通过；严格 AI 台账、规则和编码检查通过。
  这些不替代实际 Android 构建或完整 Flask 测试。
- 合成签名 APK 经实际 aapt/apksigner 生成元数据；样本仅为无代码测试包，不含真实发行私钥。
- 私有 36 文件整批逆序/恢复逐字节一致；旧签名工作流不能通过新增断言，
  去除发布绿灯判断的变异导致行为测试失败，恢复后通过。
- 本机 release 构建曾因 1GiB R8 堆不足停止自有构建进程，没有记为出包成功。
  宿主完整 WMS 验证被真实 LPAC 门禁阻止，没有绕过或导入生产应用。

## 签名阻碍的直接证据

[构建任务 132362874600](https://github.com/SIX2090/wms/actions/runs/43566988062/job/132362874600)
在 2026-11-14 14:34:51（Asia/Shanghai）显示固定签名变量为空：
`WMS_FIXED_DEBUG_KEYSTORE_B64` 未提供，固定签名恢复步骤退出 1。
拒绝原因是用户附件明确要求“自动更新发行不得因签名材料缺失而临时生成新证书”。
没有放宽门禁，没有发布候选 APK 或稳定更新记录。

此项属于既有 `BUG-2026-09-04-003` 签名链的实际配置前置条件，**不登记为新 BUG**。
旧工作流缺 Secret 时只警告，不能将过去编译绿灯当作签名长期稳定的证明。

仅检查了三个已知默认位置的文件元数据：项目正式签名路径、项目 debug.keystore、
当前用户 `.android/debug.keystore`，均不存在；没有扫描其他私人目录，也没有读取或输出密钥。

需要用户提供与当前手机 APK 对应的原签名文件路径，或在 GitHub 安全恢复原 Secret。
不得在聊天发送私钥或密码。若原签名已经丢失，APK 的公开证书不能还原私钥；
不能承诺仍可直接覆盖旧 App。换签名或迁移手机数据属于需要另行明确范围的工作，
本任务不通过卸载、清库、root 或设备管理接管绕过。

## R8 实际回退

依次逆序回退本任务三个提交：

- `cf0bc750` 撤回功能实现；
- `b2fe2fbf` 撤回状态指针；
- `7cea3cb8664eebff0c36c8c29d7c345b4bd3f509` 撤回开工登记。

在添加本记录和发行元数据前，实际执行
`git diff 349850df5423a6abc8e4d220f27fe39a7ec98b38..7cea3cb8664eebff0c36c8c29d7c345b4bd3f509 --quiet`
退出 0，证明完整树恢复，不是只挑部分文件回退。随后仅重新登记等待事项，
并前移 Windows 版本至未使用的 2026.11.52；业务代码和 Android 工程保持原基线。

本批没有修改 `app/app.py`，没有移动 CI 行号锚点。
原有两项删除和两项未跟踪文件原样保留；没有撤销其他任务。
生产数据库及 -wal/-shm、备份、账号密码、现役服务、真实手机均未操作。

## 后续条件

1. 核对原签名材料与当前安装 APK 的证书一致性。
2. 按明确授权安全配置 CI 所需签名，不打印、不提交私钥和密码。
3. 基于当时 main 重新恢复实现、递增版本、复验并推送新目标。
4. 三工作流全部验收后才提升稳定记录，首次手动覆盖安装，再做真实手机验收。

前一阶段结束时状态为**待原签名配置，未交付**；本阶段按文首用户新授权继续。
