# 复制及来源下推的网页请求意图（Node VM 专项）

固定产品基线38b5440c。只扩展现有api.js的12个实际新单命令URL（9复制、采购选单/按单下推、BOM转领料），仍沿同一pendingDocumentKeys和X-Idempotency-Key协议。命令body里的id/order_id是来源身份，不能套编辑跳过；没有body的复制也需key。数据仅在documentRequestKey局部置空用于意图识别，真实请求body已先构造并完整保留。

原20保存路径、其编辑跳过、preview号键生成及清除行为保持字节相同。本专项不把原preview-cache源码观察宣称真实UI故障。命令用完整URL意图，未知响应/网络/JSON解析/HTTP/业务失败保留key，已知success后由原URL清除逻辑释放，下一次人工命令分配新key。显式调用方header、CSRF、same-origin credentials、JSON和FormData不变；不同源URL分开，不增加业务审批或状态。

141明确非空方法直接运行真实api.js到Node VM，传输全部由闭合fake fetch提供，无浏览器/真实服务器/数据库。12URL×8失败/正文/显式header模式，20旧保存、20编辑、5非命令对照；子Node只允许标准环境白名单，去掉继承NODE_OPTIONS/NODE_PATH/DB目标，并提前预载网络/child_process/worker_threads拒绝器。

旧源/新源方法和断言相同，旧应84断言失败/57正常对照/0初始化错误，新141绿。精确结果、3文件私有Git逆序回退及LF哈希见frontend-proof.json；根任务另做完整后端+前端整批R8和新SHA CI。源码VM不是实际浏览器。生产数据库/备份/账号/服务未触碰；生效确认：待人工确认。

## 活跃采购选单页面入口追加

完整12调用链检索发现in_order_add.html的createInOrderFromPurchaseOrderSelection仍裸fetch，绕过统一api.js，因此仅给api补命令key不够。只把它接到WMS.api.postRaw，保原选择/数量/上限校验、warehouse_id/remark/items payload、成功跳转和中文报错。其余活跃复制/下推均已走api.post/postRaw；禁用历史bom_detail不恢复。

独立20个Node VM实例：12真实postRaw命令响应丢失/同key重试/成功后新key，另8个真实模板函数的空选、零、非数、超量、成功、网络、业务/HTTP错误。旧模板同20应4断言失败/16正常对照/0初始化错误，新20通过；恢复候选后141+20共161 VM检查通过，与已有59相邻分开报告。

本追加为模板变更，生产需重启 WMS 服务生效；本任务没有重启、部署或访问生产。组件3文件独立Git逆序/恢复与最终whole批R8分别核对。生效确认：待人工确认。


## 精确代码、CI 与包验收（2026-11-14）

最终纠正提交 `57df192705a37b593ef0e1a3690a01e2f126ee72`，Windows `2026.11.49`。原 `2fd6dd67` 的三项旧选单夹具失败及两个模块级生成器收集错误已按 R8 整批撤回（兼容回退提交 `36dbbf73a6be5f57e4ab3e15c6c7a4c94ccd0a52`、版本48），然后修正真实依赖并恢复本任务。未撤销已验收的 Android005、39/3.9.15 或其他任务。

- 纠正验证：封闭真实 pytest 显式3文件，旧177收集/172通过/3失败/2错误，新175全部通过；仅去掉两个误泄漏的全局辅助函数，161命令VM及14原选单有效测试标识、原业务断言全部保留。旧选单加载真实 `api.js`，无恒真API替身。20相邻组、5静态门禁及整批27文件逆序/恢复通过；2,515个回退基线源码blob、整树和逐文件哈希一致，13个业务文件与原候选相同。
- [WMS CI 43552705263](https://github.com/SIX2090/wms/actions/runs/43552705263) completed/success：unit分片6051/5504/4785通过，共16340通过、203跳过、1561子测试通过；静态、四verify、smoke、browser、gate全部success。新增52+22实际HTTP实例随该精确目标的标准Linux隔离分片通过，宿主未import/collect/run完整WMS。
- [AI 43552705307](https://github.com/SIX2090/wms/actions/runs/43552705307) 和 [性能 43552705234](https://github.com/SIX2090/wms/actions/runs/43552705234) completed/success。Android [43548469707](https://github.com/SIX2090/wms/actions/runs/43548469707) 的完整成功SHA `aa982156adb5007581775490ebbe32825024e5d4` 是最终目标祖先，`app/android-native-wms/` 与 `.github/workflows/android-build.yml` 零差异；不是声称本次重新构建APK。
- [Windows 43553284658](https://github.com/SIX2090/wms/actions/runs/43553284658) completed/success，日志实际 `built_verified`，不是陈旧任务跳过。[windows-v2026.11.49](https://github.com/SIX2090/wms/releases/tag/windows-v2026.11.49) 已发布，目标完整57df提交；4资产齐全。ZIP 97,268,305字节，SHA256 `34c3b21765507e23e8d27ac80c0a885dd15e27a8bf420abd0bd254a717328ce7`。
- 实际普通push先 `2fd6dd67..36dbbf73 main -> main`，后 `36dbbf73..57df1927 main -> main`，均退出0，远端完整SHA已反查一致；未跳过钩子、未force。原无关两删除/两未跟踪文件保留。测试数、入口数、注册标题数不换算BUG修复数。
- 代码与CI已验收；生产数据库/备份、账号、业务单据、现役服务、微信/打印、部署和迁移未操作。模板变更，生产需重启 WMS 服务生效；本任务没有重启。生效确认：待人工确认。其他数据库实际竞争、物理设备和生产业务生效仍各自待证，不称全WMS无BUG。
