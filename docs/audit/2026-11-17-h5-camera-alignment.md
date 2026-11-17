# H5相机取景与原生App对齐（2026-11-17）

任务MOB-SCANNER-FULLSCREEN-20261116-001，本轮子阶段CAMERA-ALIGN-20261117，关联BUG-2026-11-16-015续修。用户明确本次差异在取景、对焦或操作体验，不能把昨天“解码提速已部署”当成这些体验已对齐。基线main/0df4d87399c7f90318d636598bed982768d9dc1f；共享工作区另有未交付原生视觉/台账改动，本批排除。

## 实现核对与最小修改

原生ScannerDialog使用PreviewView.ScaleType.FIT_CENTER等比完整显示，并显式请求Camera2 CONTROL_AF_MODE_CONTINUOUS_PICTURE；H5共享mobile_scan.html使用object-fit:cover，会在长宽比不一致时裁切画面，没有主动请求focusMode。两端解码器仍分别是MLKit/ZXing，这不意味着可以承诺手机性能或设备能力完全相同。

本次H5视频改为object-fit:contain和object-position:center，保持整个网页视口取景容器及贴边8px蓝色提示角；黑边属于保留完整画面的等比适配，不把裁切放大伪称完整视野。沿现有decodeFromVideoDevice后置环境相机入口，在decodeFromStream现有reader身份守卫之后，仅当首个live视频轨道公开的focusMode数组含continuous时申请applyConstraints({advanced:[{focusMode:'continuous'}]})。不等待该可选Promise，不阻塞attach/play/解码；API缺失、只支持manual、同步异常、拒绝或挂起均沿原采流继续，迟到返回不写任何界面或新会话。旧流仍按原规则释放。不是断言浏览器此前没有自动对焦，也不保证所有微信/手机支持该控制。

不改变9种条码支持、3帧快扫/第4帧强化、扫码结果/单次业务确认、仓库库存、账号权限和提交协议；不擅自增加连续制单、缩放、手电或设备选择。原生源码/APK不变，Windows候选版本2026.11.84。

依据：[W3C CSS Images的object-fit定义](https://www.w3.org/TR/css-images-3/#the-object-fit)、[W3C MediaStream Image Capture](https://www.w3.org/TR/image-capture/)的能力探测与对焦约束。设备支持须由getCapabilities提供，不能依据浏览器名称或接口存在就假定支持。

## R6同类消费者与验证边界

核对全仓ScannerDialog、BrowserMultiFormatReader、decodeFromVideoDevice、decodeFromStream、object-fit、focusMode及模板路径；产品ZXing扫码仍只有此共享模板，覆盖入库、出库、查库存和盘点。原生CameraX与识物拍照不消费该CSS/相机流包装，保持原行为。QA30双副本、QA46真实SDK采流、frontend_audit_failure_runtime、既有H5导航、insecure-origin及速度调度消费者均纳入相邻验证；可选对焦代码放原函数闭包内部，不增加提取器隐式全局。

实际运行结果、旧红/新绿、整批R8、提交推送与精确CI以执行后补证为准。截图/合成视频可证明画面保留范围与浏览器状态流转，不能冒充真实手机、微信、物理镜头/对焦或安装验收。无生产数据库/HTTP、账号、服务、部署或硬件操作；生产尚未切换本轮代码，模板需要受控重启生效，部署前核对本轮目标、完整CI和既有授权范围。

## 本地行为验证

真实vendored ZXing设备→约束→流→reset→连续解码链执行，18项通过；同SDK/测试/网络guard的旧0df模板6项业务断言失败、12项兼容控制通过，0错误/跳过。覆盖受支持continuous申请、缺getVideoTracks/空轨道/轨道API异常、只manual/非法能力、缺约束API、已结束轨道、拒绝/异常/永不结算的可选请求；旧流、取消、迟到拒绝均验证不污染新会话，实际空白像素解码仍到达。媒体/DOM与能力是合成边界，未测真实光学对焦。

Chrome157.0.8103.52/Playwright1.62.1真实640×480合成视频截图：375×812、414×896、812×375三个视口，旧cover全部因源帧左右或上下边缘实际不可见而业务失败；候选三项通过，图像分别375×281、414×311、500×375，保持等比居中，蓝框仍为viewport inset8。断言基于截图颜色像素边界，不以object-fit字符串冒充画面验证。已有真实Chrome扫码/QR回传一次/关闭释放/全屏/权限/迟到流8场景在旧、新各8通过，外部请求/pageErrors为0。

Fresh Windows LPAC/WFP/Job完整应用同套6模块，基线80/候选80通过，0失败/错误/跳过。实际两URI/engine为内存、PRAGMA无文件，primary/descendant负探针通过，Job归零/双栈filters移除/profile清理核实；9601输入重hash无变化，旧新差异仅run-mode和冻结的template/version，不包含新锁或共享视觉脏改。纯源码统一回归、整体回退恢复和精确CI执行后补证。

外置证据：h5-camera-alignment-20261117的summary.json（4条实际ARGV、旧新3视口PNG/像素proof及既有两轮8场景）、h5-camera-alignment-20261117/new18.xml与old18.xml、h5-align-app-adjacent-20261117.json及其原始LPAC目录。18项焦点测试与真实光学对焦分别验收，不用canvas轨道缺focus能力冒充手机已支持。

## 统一回归与整批回退

先核暂存7个自有路径与A1–A14（0新增违规），再冻结纯Git基线2838文件、候选2841文件。69项统一纯源码/真实SDK/文档契约回归全部通过；私有副本将本批5个非锁路径整体回退（新增文档移除、2个新回归锁保留），2838父树文件逐字节匹配。旧实现69项中6项行为失败/63项控制通过，真实Chrome截图3项裁切断言失败，0夹具错误；逐字节恢复候选后69项及Chrome3项全部通过，完整源清单恢复一致。共享工作区未回退，未撤销他人文件。

全量规则诊断基线381项既有违规（因此直接--full退出1，不是新缺陷）；候选全量仍381，--full --full-gate棘轮通过，无新增，未修改基线或削弱断言。严格AI台账44标记/144已完成映射及UTF-8编码通过。受影响完整应用基线80/候选80、纯源码69、实际浏览器3及既有8分开计数，不混称硬件验收。

证据h5-camera-align-20261117/whole-batch-rollback-proof.json记录7路径、2锁、旧红/新绿和全部源hash恢复；batch-old.xml/batch-restored.xml与batch-old-pixels/batch-restored-pixels保留实际结果。当前本地验证完成；提交、实际push输出、精确目标三个工作流及后续生产状态在执行后补证，不预填通过。
