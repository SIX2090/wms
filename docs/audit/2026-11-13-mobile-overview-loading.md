# Android 首页及日报加载修复（2026-11-13）

关联 BUG-2026-11-13-003。Android 3.9.11（35），Windows 构建输入版本 2026.11.26。

## 行为与范围

首页由最多三次概览请求收敛为确定仓库后查询一次，日报由默认仓／首仓重复查询改为确定仓库后查询一次；返回页面仍刷新。相同在途请求合并，筛选变化取消旧请求并拒绝迟到成功／失败，切换条件不再显示旧条件数据。

没有修改后端 API、报表或库存口径，没有新增持久化缓存。保留失败重试、仓库列表失败时服务端默认仓兼容，以及同一报表刷新失败保留已有内容。公开 Application 构造入口继续使用现有 Repository，会话恢复／分页由 Repository 原实现负责。

同类排查覆盖 App 的页面进入、init、选仓与报表刷新；首页和每日报表的重复首次查询已一起修复。另三张分页／台账页在仓库或物料尚未确定时不会发起首次查询，不属于此重复模式。网页、后端、Android API、AI 及脚本的概览消费点已检索，没有其他相同首登触发链。

## 本地验证及边界

- 基线 cf3027a7d4423587ff4eb1477de244bafd79c48c；七个相关源码模块完整 51 项通过。
- 候选保留仓库传参／日期刷新／分页／下钻断言，更新两处页面接线测试；51 项既有源码断言与 2 项新接线锁共 53 项通过。
- 在独立源码快照恢复旧产品文件后，最终两个新接线锁均失败；候选恢复后通过。没有回退共享目录、使用 stash 或纳入其他任务的改动。
- 新增 OverviewLoadingTest 16 项真实 ViewModel／协程用例；合成数据源、普通 Application，不构造 Repository，不连接数据库或网络。此处仅登记测试已编写，实际运行由 Android CI 验收。
- 扩大到十个明确的源码／台账模块，73 项通过（13.29 秒），没有导入 WMS 应用；规则扫描 0 违规。verify_wms_bugs.py 在普通主机进程被真实 LPAC 身份守卫阻止，未绕过，动态回归由本目标 CI 执行。
- 本机未发现 Java／Android SDK，未完成本地 APK 编译或真机操作。源码检查不能替代 Android 运行结果，也不能给出现场加载秒数。
- 隔离证据：本任务临时目录 wms-home-load-20261113-t50iti7q 中的 baseline-checks.json、old-wiring.log、candidate-wiring.log、rollback-and-candidate-proof.json。

## 精确提交与 CI

实际推送输出为 `cf3027a7..cedf7d78 main -> main`，代码目标为 `cedf7d783409513a3ed7ec5d9340ca01dc3a58a2`；推送时本地 HEAD、origin/main 与实时远端完全一致，后续 main 正常推进不改变此验收目标。

- [Android APK Build #875](https://github.com/SIX2090/wms/actions/runs/43395806327)：精确目标 completed/success，build、lint、unit-test 全部成功。
- [WMS CI #2136](https://github.com/SIX2090/wms/actions/runs/43395806479)：精确目标 completed/success；三片全站单测、四片 verify、规则与安全检查、隔离 smoke、browser 和 gate 全部成功。
- [WMS AI Verification #2431](https://github.com/SIX2090/wms/actions/runs/43395806328)：精确目标 completed/success。性能基线 43395806470 同样 success。
- Android unit-test 作业 `131786286639` 日志逐项确认 OverviewLoadingTest 的 16 项全部 PASSED，随后 BUILD SUCCESSFUL。此为实际运行证据，与本地源码检查分开登记。
- 匿名 check_ci_green.py 查询遇到 HTTP 403 限流；已通过连接的 GitHub 工具分别读取上述三个 run，逐一核对完整目标 SHA、completed/success 和聚合 gate，未设置跳过标志或把查询失败当通过。

APK 资产来自上述运行，artifact `14022368983` 关联相同 head_sha；固定发布 tag `android-apk-875`。[下载本批 APK](https://github.com/SIX2090/wms/releases/download/android-apk-875/wms-mobile-scan.apk)，25,462,963 字节，GitHub 公布 SHA-256 `05392d2524a00d98b69bf63a6b8a9c7842813c8b10f1b21f3721ebff75c16dbd`。本补记只修改文档，不改变已通过验收的 Android 产品字节。

## 生效

待手机覆盖安装本批 APK 后人工确认。未部署、重启、修改生产数据库或操作真实单据；不需要因本次 Android 修改重启 WMS 服务。
