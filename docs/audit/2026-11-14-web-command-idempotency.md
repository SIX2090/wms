# 网页复制及采购下推：请求回放的统一事务回执

固定产品基线38b5440c215e74a8fdc8d6c34639b5e94efd21ae。本组件仅改共用幂等服务、入库复制、采购选单及按单下推/core；其他同根因复制/BOM由同批组件沿相同服务接入。不是新单号架构、审批/状态设计或生产迁移。

## 旧版已证行为

受守卫的真实源码、实际模型、新内存库中执行真实require_role（合成admin）→实际request_input Pydantic→实际document_edit_guard/_identity→真实handler。相同X-Idempotency-Key、同一源/内容，首响应视为丢失后再次发送：copy/selection/按单push均200但id2→id3，采购预留1.01→2.02→3.03；库存一直20。8方法中3业务断言红、5正对照绿、0初始化错误；正对照包括既有新建保存同key回放、四入口不同key新意图正常新建。不以两个无key人工操作当BUG。

NEW_DOCUMENT_INTENTS对复制/下推的作用是保持其独立新单意图、避免把源单当编辑目标；它不提供重放回执。selection头部无目标id时_identity=None合法进入view。同源数量累计/剩余限额也不等价请求幂等。AI两采购match/context分支已有acquire/replay/complete，native/H5已有独立请求保护，本组件保留。

## 最小修复和事务

新增薄web_document_command_idempotent(view)，委托原_document_idempotent(command=True)，沿同一MobileApiRequest用户/endpoint/key唯一表。不增加schema或配置。旧web/mobile默认command=False分支不变；无key完全沿原行为，新key仍真正新建。命令不把payload.id/order_id当编辑绕过；fingerprint包含真实request.path、view_args和去csrf的原payload；command endpoint为真实request.endpoint（仅无路由源码调用fallback到view名）。同key换源/换内容409，不合并不同人工意图。

copy/selection把原成功响应对象在原commit前stage_document_response，commit后返回同一个对象，避免空回执或响应字段偏离。按单采购core仅在有web回执时，在它既有成功commit前stage与网页返回一致的完整payload；AI/内部无回执调用保持。core无可收行错误时，有claim不再提前commit空status0；原无claim的状态刷新/commit行为保留。错误、DML失败和原finally回滚释放claim；日志仍业务成功后best-effort，不另包长期事务。正式号分配/现有写锁对web_document_receipt的保护保持。

不同源copy正文同为{}，必须绑定源URL/args，不能只按view名+body判断相同。同一用户不同命令端点使用独立endpoint域，跨用户键独立。产品copy_to_out别名原有DocumentPushLine/短锁路径由相邻组件在claim前分派，不能把它的既有commit包成空回执。

## 验证和边界

新源码26方法使用原真实模型harness，在任何依赖前禁止WMS app导入、SQLite文件库、网络与其他子进程。实际role/input/revision guard与新回执函数都来自产品源码，明确只将app模块绑定接到真实提取模型；不是完整WMS请求钩子。配置、编号等fixture seam标明为合成，不把它们当真实正式号分配证据。

覆盖原8、同key异源path/异数量409、三用户隔离、三无key兼容、三实际IN_ORDER INSERT故障/rollback后同key重试、三源id字段不绕过，以及core无可收行错误不提交空claim。对缺回执先断言数量而不以NoResultFound冒充业务旧红。原110采购预留、188已完成入库、9模型、10编号源码相邻均分别通过。并发claim的数据库唯一/事务分支复用原服务，其他驱动及真实争用须以适用隔离运行证据为准，不称宿主已跑多进程业务。

新真实HTTP文件test_web_command_idempotency_runtime_20261114.py为同26×库位开/关=52实例：真实runtime guard先于app导入，复用已验source_scene的全新sqlite memory/PRAGMA与合成会话；只共享夹具/断言，source call_intent明确排除，每例至少两个真实document_post。真实ORM、权限/请求钩子、正式号和事务回执均交现有Linux隔离CI实际验收，不在宿主import/collect/run。记录所有最终status0回执为零，草稿命令不产生额外库存流水。

整个7文件组件在Git文本专用私有main做产品4→测试/本文3提交、逆序回退、全2514基线blob/整树恢复、旧断言真实失败、精确恢复后26及相邻重验；LF补丁应用和最终SHA256另外冻结。共享目录不做覆盖/回退/索引操作。统一前端12个命令URL的key生命周期与另外9域接入、最终整批R8、实际push及精确CI由主任务合批验收，不预报完成。

没有读取/连接/复制/备份/恢复/修改生产数据库或备份，没有真实账号、业务单据、默认8080、微信、打印、部署、重启或迁移。生效确认：待人工确认。


## 精确代码、CI 与包验收（2026-11-14）

最终纠正提交 `57df192705a37b593ef0e1a3690a01e2f126ee72`，Windows `2026.11.49`。原 `2fd6dd67` 的三项旧选单夹具失败及两个模块级生成器收集错误已按 R8 整批撤回（兼容回退提交 `36dbbf73a6be5f57e4ab3e15c6c7a4c94ccd0a52`、版本48），然后修正真实依赖并恢复本任务。未撤销已验收的 Android005、39/3.9.15 或其他任务。

- 纠正验证：封闭真实 pytest 显式3文件，旧177收集/172通过/3失败/2错误，新175全部通过；仅去掉两个误泄漏的全局辅助函数，161命令VM及14原选单有效测试标识、原业务断言全部保留。旧选单加载真实 `api.js`，无恒真API替身。20相邻组、5静态门禁及整批27文件逆序/恢复通过；2,515个回退基线源码blob、整树和逐文件哈希一致，13个业务文件与原候选相同。
- [WMS CI 43552705263](https://github.com/SIX2090/wms/actions/runs/43552705263) completed/success：unit分片6051/5504/4785通过，共16340通过、203跳过、1561子测试通过；静态、四verify、smoke、browser、gate全部success。新增52+22实际HTTP实例随该精确目标的标准Linux隔离分片通过，宿主未import/collect/run完整WMS。
- [AI 43552705307](https://github.com/SIX2090/wms/actions/runs/43552705307) 和 [性能 43552705234](https://github.com/SIX2090/wms/actions/runs/43552705234) completed/success。Android [43548469707](https://github.com/SIX2090/wms/actions/runs/43548469707) 的完整成功SHA `aa982156adb5007581775490ebbe32825024e5d4` 是最终目标祖先，`app/android-native-wms/` 与 `.github/workflows/android-build.yml` 零差异；不是声称本次重新构建APK。
- [Windows 43553284658](https://github.com/SIX2090/wms/actions/runs/43553284658) completed/success，日志实际 `built_verified`，不是陈旧任务跳过。[windows-v2026.11.49](https://github.com/SIX2090/wms/releases/tag/windows-v2026.11.49) 已发布，目标完整57df提交；4资产齐全。ZIP 97,268,305字节，SHA256 `34c3b21765507e23e8d27ac80c0a885dd15e27a8bf420abd0bd254a717328ce7`。
- 实际普通push先 `2fd6dd67..36dbbf73 main -> main`，后 `36dbbf73..57df1927 main -> main`，均退出0，远端完整SHA已反查一致；未跳过钩子、未force。原无关两删除/两未跟踪文件保留。测试数、入口数、注册标题数不换算BUG修复数。
- 代码与CI已验收；生产数据库/备份、账号、业务单据、现役服务、微信/打印、部署和迁移未操作。模板变更，生产需重启 WMS 服务生效；本任务没有重启。生效确认：待人工确认。其他数据库实际竞争、物理设备和生产业务生效仍各自待证，不称全WMS无BUG。
