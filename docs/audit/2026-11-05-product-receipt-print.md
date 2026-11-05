# 产品入库单字段及打印格式验收

2026-11-05，FEAT-2026-11-05-107。

用户提供图片模板并确认NO使用现有合同编号。交付范围为产品入库表头客户/合同/工程、明细箱体编号及该业务类型的默认打印，不变更库存计算或单据状态流转。

- 基线：`d3f771093497b375d321fc8cf571610f875eed58`；WMS CI41990749958、AI41990749970成功；Android41971520345成功，祖先和保护路径无变化证明已核实。
- 原工作区21份已修改文件及5份未跟踪文件先备份后保留；本批只提交准确文件集合。备份位于本机`C:/wms_backups/product_receipt_20261105_161836`。
- 修前基线7模块65 passed。物理恢复7份原产品文件并撤下新服务后，专项15 failed/1 deselected；finally逐字节恢复。本批新增结构预演及文字字面量用例另行通过。
- 受影响及相邻模块最终56模块852 passed/4 skipped，台账/A13契约15 passed。`verify_wms_bugs.py`、A1–A14及业务JS请求检查通过。
- 初次扩大回归中的GBK/Node UTF-8输出错误保留原日志，使用`PYTHONUTF8=1`复验；Excel表格测试假DOM补齐原本缺失的textContent setter，原有业务断言保留并扩充箱体文本、备注不被覆盖及版本冲突用例。
- 隔离HTTP冒烟119/119。真实Chrome使用一次性合成SQLite数据库和`127.0.0.1:18081`，验证可见保存按钮、客户/工程/合同保存、箱体前导零、详情编辑不覆盖备注、编辑回填、20行表单及Excel下载；无页面脚本错误。浏览器脚本按实际嵌入页访问，并在请求转交前捕获真实保存响应，避免导航使响应体失效。证据位于本机`output/playwright/product-receipt/`，不将测试输出或本机路径加入业务页面。
- 浏览器PDF核实1页；Excel核实9列映射、20行明细、NO为合同号、物料名称/规格、合并单元格、按页合计/人民币大写、A4纵向及打印区域。21条明细用例核实两页及末行保留，各页金额合计等于全单。未验实体打印机，未将浏览器版式验证等同Excel原生应用打印验收。
- 生产只读结构预览列出可空`in_order_item.box_no VARCHAR(100)`；本批[已审阅SQL](2026-11-05-product-receipt-schema.sql)只增加该列，不处理预览同时提示的存量普通性能索引。备份、停服、数据库租约、执行DDL和沿原入口重启须取得本次明确授权。生产需重启 WMS 服务生效。

纠正提交的精确CI与实际推送结果见末尾“软件交付验收”；本批未写入生产数据库、单据、库存或账号，未重启服务。

推送前匿名GitHub API返回403限流。本次改用已连接GitHub工具逐页读取main最近运行（每页10条，读取第1、2页直到找到Android），确认最新WMS CI [41990749958](https://github.com/SIX2090/wms/actions/runs/41990749958)与AI [41990749970](https://github.com/SIX2090/wms/actions/runs/41990749970)均为d3f771093497b375d321fc8cf571610f875eed58且completed/success；最新Android [41971520345](https://github.com/SIX2090/wms/actions/runs/41971520345)为86043f560b6b1a17d90046d9eaadb3135dc66ce9且completed/success。Git再次确认远端main仍为同一d3f77109基线，旧Android提交为其祖先，两端提交对象完整，Android工程和构建工作流差异为空。按AGENTS的同一基线替代证据程序，仅本次push临时设置既有WMS_SKIP_CI_GATE=1处理同一查询故障，不绕过未核实或非绿状态，提交钩子保持启用。

## 首次CI失败与完整撤回

- 原批次为0bad46f689e3b1a3e7d46f8df9fe2cd4c8719856及345667e1989ec6d62e96284ff858f7ff294cf7af，已实际推送`d3f77109..345667e1 main -> main`。
- [WMS CI41997811265](https://github.com/SIX2090/wms/actions/runs/41997811265)失败：三分片分别4 failed/3622 passed/28 skipped、32 failed/4686 passed/145 skipped、3 failed/4038 passed/16 skipped。36项源于submitForm中新增的Jinja控制块不能被既有直接执行JS的消费点解析；3项是旧产品打印默认布局断言。AI41997811335、静态、四组verify、浏览器及HTTP冒烟均成功，不抵消全站单测失败。
- 按R8把两个提交整体撤回，形成本地37114b972fa8874a8251f1357690f42b621107a0；`git diff d3f77109 HEAD`为空，证明受跟踪内容与原绿色基线完整一致。四个失败关联模块在撤回后129 passed。没有选择性留下首批产品代码。
- 在此基础上重新应用完整批次并纠正：submitForm使用普通JavaScript按产品表头存在与业务类型收集字段；产品标题保留doc-title消费点；旧模板回归显式传入既有template_id，所有旧标题、单号及源模板字节不变断言保留，新产品默认格式继续由新专项校验。库位运行时回归扩充采购/产品两类型及客户、合同、工程和箱体前导零。
- 修正专项150 passed；真实Chrome再次验证客户/合同/工程保存、箱体编辑、备注保留、回填和打印下载成功。修正后的产品app/与初版只差两个模板文件，其余完整恢复。修正后扩大到60模块，985 passed/4 skipped，既有断言未删除或放宽；推送与精确CI仍待验收。
- 纠正推送前远端main为已确认失败的345667e1。此时不能继续沿用只用于查询故障的WMS_SKIP_CI_GATE规则；纠正推送须取得该次明确例外授权后才能执行。生产未部署首批或修正批次。
- 修正后静态BUG回归、A1–A14和台账/A13契约15项通过；在动态空闲端口启动新合成库，先核对专属X-WMS-Product-Fixture身份头再运行HTTP冒烟，119/119通过。测试服务已停止。纠正批次本地验证完成，尚未推送，不能宣称目标CI通过。

## 预览辅助脚本的快照清理

一次只读预览辅助进程使用合成数据库，但漏设WMS_SKIP_STARTUP_BACKUP，旧启动入口在默认`app/backups`生成auto_startup_20261105_165048.db。已以只读连接逐表核对该快照与本次TEMP合成库的92张表完全一致，随后把这一个精确文件移到`C:/wms_backups/product_receipt_20261105_161836/isolated-preview-startup.db`，保留证据并移出系统备份目录。该入口自带自动快照轮换；预览前未保存目录清单，无法仅凭当前目录证明此前最旧自动快照未被轮换。生产inventory.db未被该进程连接或修改。其余隔离服务均显式设置WMS_SKIP_STARTUP_BACKUP=1，后续预览须同时设置该开关和隔离备份目录。

重跑冒烟曾误用已被历史隔离服务占用的18082端口，新服务绑定失败，既有隔离服务返回401后测试中止。只读核实PID4796来自Documents/Codex/2026-11-02/task/wms-isolated-20261102/lab.py，该脚本明确使用synthetic.sqlite并断言自身数据库路径；未停止或改动该服务，也未执行成功登录后的业务请求。随后改用动态空闲端口，并要求专属身份头与本次随机TEMP目录名一致后才允许冒烟登录，最终119/119通过。

## 软件交付验收与空间恢复

2026-11-05，用户对明确限定的“整批回退＋完整修正重放”纠正推送回复“授权本次纠正推送”。该授权不包含生产补列、版本切换或服务重启。实际Git输出为`345667e1..8dc3d926 main -> main`；本地HEAD、origin/main及实时ls-remote均核对为`8dc3d926c50b289dd5565e4ae1ea42f91ba8a0b9`。临时WMS_SKIP_CI_GATE变量在本次操作结束后撤除，未永久修改钩子或门禁。

- [WMS CI42000605834](https://github.com/SIX2090/wms/actions/runs/42000605834)：精确纠正SHA，completed/success；三个单测分片、四个verify分片、浏览器、HTTP冒烟、静态规则及聚合均成功。docs-checks因全量分支正常跳过。
- [WMS AI Verification42000605823](https://github.com/SIX2090/wms/actions/runs/42000605823)：同一完整SHA，completed/success。
- [Android APK Build41971520345](https://github.com/SIX2090/wms/actions/runs/41971520345)：main最近一次Android运行，completed/success，SHA为`86043f560b6b1a17d90046d9eaadb3135dc66ce9`。Git对象完整、祖先关系以及Android工程和构建工作流差异为空均已核实，按既有路径过滤规则复用，不冒充重新构建。

补记前远端已正常前进至`4e1e130cee154248ec8d44b0d219bb81df3e4865`，保留本批代码。逐页核对main最新[WMS CI42008149748](https://github.com/SIX2090/wms/actions/runs/42008149748)与[AI42008149752](https://github.com/SIX2090/wms/actions/runs/42008149752)均匹配该基线且success，Android祖先及保护路径不变证明再次通过后才写入本次纯文档回执。本地安全快进保留原21份未提交文件及5份未跟踪文件；3份交叠界面文件合入上游功能并保留原外观差异，未纳入本批提交。备份压缩后191615字节，保存在本聊天visualizations工作目录，不复制解释器或生产数据库。

此前准备候选时复制运行环境遇到C盘0剩余空间，候选未完成、未发布。工具自动审批拒绝了对自建半成品runtime目录的递归删除，因此未换工具绕过。用户手工清理后回复“我全删了，太多了搞不清”，只读复核发现本次`product_receipt_20261105_161836`临时验收目录已删除，原先置于其中的日志、工作区备份及合成快照不能再当可访问证据；已提交代码、审计文字及`output/playwright/product-receipt-corrected/`浏览器结果仍在。没有继续清理其他目录，也未为补记重建大型运行环境副本。

清理后C盘可用约3.7GiB。正式版本`C:/wms_releases/20261105_audit03_85df6437`的759份源码、39份界面覆盖及12份封装文件逐项SHA256与既有清单一致，运行环境文件数仍为12486；生产SQLite以mode=ro执行quick_check结果ok，box_no仍未补列。PID3024继续监听127.0.0.1:8080，WMS-Warehouse仍运行。第一次匿名登录GET超时，随后直连且禁用代理的GET返回200；不将最初超时等同文件缺失或已经定位根因。本批未执行生产登录、账号变更、单据操作、库存写入、结构升级或重启，生产生效仍待专项授权。

上述摘要仅覆盖正式应用清单。随后收到另一聊天“全面检查 WMS 按钮功能”的告警：18:10后的清理曾使生产任务引用的监护脚本、动作环境配置及状态文件缺失，相关恢复由该聊天处理。本聊天再次只读核对时脚本与动作配置已存在，supervisor-status.json仍缺失；不能以应用摘要、端口监听或一次HTTP200替代整套监护及备份链路的验收。本聊天未对这些目录执行删除、恢复、计划任务变更或服务重启，不重复介入现场恢复。

本次仅修改本审计及107台账条目。使用`python -m pytest --noconftest -q -o addopts= -p no:cacheprovider tests/test_f4_4_ledger_split.py tests/test_inventory_truth_line_refs.py tests/test_audit_readme_inventory_identity.py tests/test_lint_wms_rules_a13_golden.py`复验39 passed；全量规则棘轮`python scripts/lint_wms_rules.py --full --full-gate`退出0，保留存量报告，不声称全仓零违规。匿名API已恢复，`python scripts/check_ci_green.py --target-sha 4e1e130cee154248ec8d44b0d219bb81df3e4865 --json`返回ok=true且退出0；本次文档推送按正常钩子复核，不沿用此前纠正推送例外。文档收尾的精确提交另按Actions所选文档分支验收，不能把原业务CI当作未执行的文档检查。
