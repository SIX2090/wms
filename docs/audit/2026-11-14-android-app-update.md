# Android App 自动更新（MOBILE-UPDATE-20261114-001）

日期：2026-11-14（Asia/Shanghai）。基线 `349850df5423a6abc8e4d220f27fe39a7ec98b38`。

## 当前交付状态

实现与适用本地验证已完成，尚待推送后精确目标 CI，不能视为已交付。
Android 候选版本 3.9.16 / versionCode 40。Windows 发行版本 2026.11.51。
实际手机安装、厂商免确认效果及升级后现场数据保留均待设备验收。

## 现状与查重

原 App 只有版本显示，没有更新管理器、安装权限或安装会话。
原 `/mobile/app` 依次使用管理员配置地址、本地 APK 或说明页，可能提供旧包，
本任务不改变该入口或生产配置。服务器 Git 更新 AI-DEPLOY-F01 与本功能不同。
固定签名沿用 BUG-2026-09-04-003；不可变候选发行沿用 BUG-2026-11-10-005。
草稿/队列保护沿用 BUG-2026-11-08-012，定时补传沿用 BUG-2026-11-14-005；不重复登记 BUG。

## 稳定通道与信任来源

候选 APK 仍由 Android APK Build 构建，使用固定签名 Secret；缺失时拒绝构建，
不临时生成替代身份。aapt 读取实际 APK 的包名、版本和 minSdk，apksigner 验证签名，
计算文件 SHA-256。候选 Release `android-apk-<run_number>` 的 body 保存 JSON，
绑定完整 SHA、实际 APK 元信息、固定产物 URL、大小、签名证书 SHA-256 与更新说明。
本批起候选 tag 为 `android-apk-<run_number>-attempt-<run_attempt>`，重跑使用新候选，
不覆盖已锁定的上一 attempt；历史候选直链保留。
既有 `latest/download/wms-mobile-scan.apk` 人工下载入口继续沿用候选发行；
它不是完整 CI 验收证明，新自动更新客户端不会访问该别名。

新增 Android Stable Update Promotion 在三个 required 工作流完成后触发：
仅接受本仓库 main 的 push/schedule/workflow_dispatch，排除 PR/fork。
以候选精确 SHA 查询 Android APK Build / WMS CI / WMS AI Verification 的最新运行和 attempt，
必须全部 completed/success，核对祖先关系、候选 Release、资产大小及 GitHub digest，
发布前再查一次运行。异常时保持既有稳定记录，不写 main。

稳定记录使用不可变的新 Release：`android-stable-v<versionCode>-<完整SHA>`，
body 为候选元信息和三工作流 ID/attempt，不复制 APK。
只对同 SHA 的重复稳定发布串行；不同目标保留各自队列，不取消构建、业务 CI 或其他目标的发布。
跨 SHA 仅创建不可变记录，手机按最大 versionCode 选择，创建先后不能回退当前稳定版本。
同号/较低版本不提升，已有稳定签名变化时拒绝自动提升。

手机通过固定 `https://api.github.com/repos/SIX2090/wms/git/matching-refs/tags/android-stable-v`
查询该前缀全集，按数值 versionCode 选择最高正式记录并核对 tag/body/目标 SHA。
不使用 latest 别名，不依赖整个 Release 列表的第一页顺序。
信任边界是固定仓库的 HTTPS API、受限 promotion 工作流及本机已安装签名；
不是接受服务器地址设置中的任意更新 JSON，也不向手机下发 GitHub Token。

## 手机使用方式

1. 等本任务目标的三工作流和稳定发布验收成功，手动下载该固定候选 Release 的 APK。
2. 覆盖安装；保留原 App，不卸载、不清数据。签名冲突时停止并核对，不能靠卸载规避。
3. 打开 App，在“我的 → 应用信息”查看版本和更新状态。
4. App 回前台最多每 6 小时自动检查一次，手动检查立即执行；高版本自动下载到
   `filesDir/app_updates/update.apk.part`，校验后原子替换 `update.apk`。
5. 首次点击“安装更新”，若尚未允许 WMS 安装应用，则进入对应系统设置；
   返回后重新检查权限，不假设授权成功。
6. 业务操作空闲时进入系统安装；系统要求时确认，也可取消后继续使用当前版本。
7. 下次打开以实际安装版本确认升级完成，更新模块只清理自己的包和会话。

更新请求使用独立 OkHttp 客户端，不带业务 Token/Cookie；所有重定向逐跳校验
HTTPS、443、精确托管域名，限制响应、包大小与超时。APK 安装前再次验证文件、
包名/实际版本/minSdk、apksig 密码学签名和与本机当前签名一致性。
不支持未经批准的证书更换、降级或破坏性数据库迁移。

## 安装与业务互斥

进程级锁原子协调新业务写请求与安装。三类直接提交持锁至本地日志/失败入队完成，
离线回放持锁至 Room 状态和删除完成，Retrofit 拦截器补充保护其他原生写接口。
安装先验证再尝试取得互斥，忙时等待，不改变幂等键和账号/服务器归属。
暂缓期间的队列行完整保留，安装结束后原键恢复回放。

PackageInstaller Session 绑定持久化目标、会话 ID 和随机回调 nonce；
回调组件不导出，Mutable PendingIntent 明确指定组件。
Android 12+ 请求 USER_ACTION_NOT_REQUIRED，但始终处理 STATUS_PENDING_USER_ACTION；
后台不强行打开界面，回前台继续确认。取消、失败及 120 秒等待超时终止会话并释放业务锁。
若系统仍报告会话存活或安装服务暂不可查询，先继续终止/核对，不能提前放行写操作后又发生迟到安装；
界面明确提示完成/取消系统安装，必要时重启手机。正常取消或确认会话结束后即恢复写操作。
安装可能终止进程，不保证自动重开 App。

## 验证记录

- 基线 Android 单元测试任务命中既有缓存（原 161 用例结果）；后续执行新增及全模块实际验证。
- 第一轮新增 Kotlin 编译通过。
- 更新状态持久化使用显式 JSON 键，避免 release R8 混淆字段名破坏进程恢复。
- 发布协议 11 项 unittest 通过，使用内存 API 替身，不访问数据库或真实服务；含同运行重跑的独立 attempt 产物绑定。
- 第一轮安装状态测试 19 项中 8 项失败，定位为首次检查的时间节流初值问题，
  已增加 last_check>0 条件，纠正后相关用例通过；未提交该失败候选。
- 新增签名样本是无代码、无活动的合成 APK，测试资源只含签名产物的 Base64；
  证书为 WMS Synthetic Unit Test Only，不含私钥，不使用真实发行签名。

- 本地完整 Android 单元测试 188 项、23 类、0失败/错误/跳过，lintRelease 通过。
  最后追加检查失败节流与提示校正后，更新模块 27 项专项通过；两组有重叠，不相加。
- 私有副本实际 aapt + apksigner 运行生成合成 APK 候选，版本、签名和哈希与文件一致。
- 6 个纯源码/协议相邻模块验证，覆盖既有签名、工作流并行、版本消费者、队列保库/归属及新发布协议；
  不将其冒充 Android 运行时或完整 Flask 验证。
- 全量规则 0 违规、暂存规则 0 违规、源码编码与严格 AI 台账映射通过。
- 宿主 verify_wms_bugs.py 被真实 LPAC 隔离门禁阻止，在导入应用前退出；不绕过，完整验证交目标 CI。
- 私有 release 构建在 R8 阶段出现 1GiB 堆不足，停止自有构建进程；未将其记为成功，正式 APK 由目标 CI 构建验收。
- 36 文件完整批次在私有 main 仓库逆序/恢复逐字节一致；旧工作流被新固定签名断言拒绝，
  去除发布绿灯判断的变异被行为测试拒绝，恢复后发布协议通过。最终冻结版本再次核验后提交。

提交与精确目标 CI 待推送后填写实际证据，不预填成功。

## 边界

app/app.py、后端业务路由、生产数据库及 -wal/-shm、备份、账号密码、现役服务均不修改。
不探测生产端口、不在真实手机安装，不更改业务权限、库存计算或单据状态。
无需重启后端才能让新版 App 访问固定 GitHub 更新通道；实际手机须可访问对应 HTTPS 域名，
网络不可达时更新失败可重试，原业务仍可使用。

## 官方接口依据

- [PackageInstaller 自更新与人工确认条件](https://developer.android.com/reference/android/content/pm/PackageInstaller.SessionParams#setRequireUserAction(int))
- [安装应用授权检查](https://developer.android.com/reference/android/content/pm/PackageManager#canRequestPackageInstalls())
- [GitHub 前缀引用查询](https://docs.github.com/en/rest/git/refs#list-matching-references)
