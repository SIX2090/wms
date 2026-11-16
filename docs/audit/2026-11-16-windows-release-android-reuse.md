# Windows 发布 Android 祖先构建选择修复（2026-11-16）

任务 CI-ANDROID-REUSE-FIX-20261116-001，BUG-2026-11-16-016。用户在扫码修复进行时贴出 Windows Portable Release 连续失败截图；本项作为同次代码发布的阻塞修复，合入当前验证批，保留独立问题及验收证据。不是生产部署，不操作现库或服务。

## 实际失败

已通过 GitHub 连接器读取实际 runs/jobs/logs：最新 #227（43832634311，813fb4ef684f0b6de580c78f0be35b2505e9fc22）与 #225（43796722075，c9458bf3947c1ec72cb64bd2ebe733723a03794a）均在打包前 `Verify exact accepted main and choose release version` 失败。门禁实际输出 Android missing，WMS CI 与 AI green，api_error=null，未进入 wheel 下载或打包。

check_ci_green.main 在目标无 Android 运行时，仅查询 android_source_sha 所给最后 Android 输入提交。该提交为 5510ebf7，当时没有单独 push 触发构建；其后 b43e0ee76a63b244a1880906f280a36f16e72ecd 实际成功构建 APK #900，但不在旧候选范围，因此漏选。有效复用必须证明真实已构建提交是目标祖先、六类 Android 输入无变化，不能将最后改源码的提交等同于唯一构建来源。

## 保留的门禁与回归

只修候选选择及其精确来源验证，不修改必需工作流集合、生产授权或打包协议。目标已有失败、排队或运行中记录时，不得借旧绿；非 main、非祖先、未来 main、不同输入、缺对象或查询异常继续拒绝。候选祖先自身的最新运行具有优先权，不能跳过其失败/等待重找更旧成功。

新增锁通过真实临时 Git 对象树模拟“Android 改动提交未构建、稍后未改输入的提交已构建、再之后文档目标无新构建”，API 仅为合成回执；不访问网络、令牌或真实仓库写权限。旧实现须在真实既有 main 入口产生错误 missing，新版通过，不能以缺新增 helper 或夹具初始化失败充当旧版反证。R6 覆盖 Windows release 调用、现有 checker/输出编码/发布绑定及通用脚本消费者。

实现按目标自身最后输入提交到目标的真实 Git 祖先链逐个查询精确 SHA，找到第一条实际运行即保留其最新状态；非浅仓、祖先、六路径差异及全部相关 tree/blob 存在性均实际校验，禁止 lazy fetch 和 replace refs。超过200候选或任何证据失败继续拒绝。latest_run 同时核对返回的main与所查完整SHA，防止响应上下文错配。对象批协议沿既有lint/源码导出消费者的bytes+LF，不更改那些正确消费者。

最终纯回归25项通过，原脚本同入口13项业务失败/12项对照通过，均零错误或跳过；不是新增helper缺失导致旧红。8个既有相邻模块适用范围131项通过，另43个subtest通过；XML会列174个case，不能误报174个pytest测试。原有两个活网用例本地明确未执行：test_ci_green_gate.py::test_t7_checker_exit_code_on_failure、::test_t11_endpoint_reachable_shape，它们会运行真实CLI、解析令牌文件/环境及访问GitHub。未新增skip或改原断言，保留到原隔离CI规则，实际精确目标Windows发布步骤还须真实联网执行完整门禁。

初轮新helper在长私有工作路径下受到Git for Windows的MAXPATH影响：`source..target`组合参数触发failed to stat/Filename too long；改为可达集合等价的两个完整SHA参数`target ^source`，保留ancestry-path、拓扑顺序、201枚举上限及逐候选复核，已在原失败长路径实证恢复。正向回归先前5项失败、只读临时Git对象删除夹具问题均保留并排除出旧产品反证；最终新旧回归用短私有目录完整重跑，没有放宽断言。独立只读复核通过，最终checker SHA256为851369548b9607ede518bfec2d7dfe6e8b7db34fe57f96bec88ed679ee13dc07，新锁41748a6fc2793c364687c0cfc87479bbd70ece120ae185745f2a67f04f90a8f4。

本项代码、专项回归、整批逆序恢复、实际 push、精确三工作流和 Windows Portable Release 结果在执行后补证；当前记录不预填未执行的成功。扫码子任务的真实 Compose、SDK、Chrome 和 LPAC 应用证据见[扫码专项](2026-11-16-fullscreen-scanner.md)。生效确认：待软件验收；没有生产部署、数据库/备份、HTTP、账号密码或真实单据操作。

## CI纠正记录（2026-11-16，首次目标未验收）

266d6679133c453071856976af6ba21c2c8a6833 的Android构建/单测/lint、AI、WMS四verify、规则、冒烟和浏览器通过；WMS单测分片1仅test_mobile_stock_ledger_page.py::test_T8_version_bumped失败，仍锁56/3.9.32，而本次实际编译57/3.9.33。首次目标整体未验收，不能报告交付。此次遗漏由本任务负责，仅同步原注释及两个精确版本值，保留全部模型/查询/导航/括号/changelog断言，不改成范围或删锁。

全仓当前测试/脚本/工作流/原生源码检索仅此处残留56/3.9.32固定值；历史说明不机械改写。他人对同一注释“保留App名称WMS”的改动保留在工作区，本任务只按HEAD原文形成版本值投影，逆变换逐字节证明未覆盖其措辞。

并行faba8e535bbdc3fb62c04336e30ff16b3b25af03仅有他人的生产部署文档及BUG013状态；本任务不操作生产，也不回退这些已提交内容。最终代码批扩为17个自有路径，私有整批回退基线保留faba的四份文档改动，只撤本任务代码/记录；版本锁所在整模块10项与既有回归重新执行。原生六输入未变化，后续目标只能按完整祖先、真实成功APK901及所有输入对象证明合法复用，不拿失败WMS旧绿验收新目标。
