# B9 高频表单标签与焦点（2026-11-08）

本批针对审计A09/P2。基线215469e40f527b2794cf904238199155da6a3208及三个required工作流已核实绿色；仅独立main工作区。当前为候选，精确新CI未验前不计交付。生产未部署，生产需重启 WMS 服务生效。

## 最小范围及根因

六份实际新增/编辑模板：document_table_form（调拨/盘点/领料，BOM共享相邻）、adjustment_add、purchase_order_add、purchase_request_add、sales_order_add/edit；另三列表transfer/check/requisition包含筛选与旧模态入口。原可见标签未关联输入，flatpickr隐藏原日期输入，动态明细无名称，两处自建粘贴框无焦点圈定/关闭归还。旧script延迟聚焦在快速取消后也可能访问已移除输入。

新增一个仅由上述九模板引用的外置交互文件。为标签所对应控制建立稳定且避碰id/for，日期关联插件可见替身；动态行按当前实际列名和行号命名，保留已有明确名称，栏目重命名/删除行后同步。既有只读、禁用、required及提交字段保持。粘贴框单实例、对话框语义、首焦点、Tab/Shift+Tab/Escape及关闭归还；盘点风险确认框复用相同焦点边界，Escape只取消确认不完成业务；Bootstrap模态复用原焦点圈定，只补首字段和关闭归还。不新增接口/权限/库存/schema/配置，不大搬业务脚本或移除全站unsafe-inline。

## 验证证据

完整模块旧基线、最终候选及整批R8计数见后续本地闭环；旧断言全部保留。原产品入库并发两个夹具首次因未声明fresh文件库被驱动拒绝，使用原精确print-lab白名单完整重跑通过，未放宽连接边界。初26契约整批10产品撤回为26failed，恢复哈希一致；随后补盘点确认和按钮被禁用后的焦点两项，最终28契约须实际完成整批复验。

真实Chrome：lab/b9-form-browser-04完成21组，05-rest在相同10产品SHA256下复用21已成功组并执行剩余2组，总23组。包括八类单据16个新增/编辑、3列表筛选及模态、栏目改名保存/刷新/恢复默认和嵌入返回、真实ArrowDown/Enter选料及数量可见、真实shell iframe标签聚焦、保存503失败保留精确内容/忙锁双击仅一个请求/恢复后真实POST保存成功。97表全量前后哈希，只有允许的sales_order/sales_order_item/operation_log随唯一实际合成销售编辑改变；其他94表完全一致。没有CSP/runtime或外源请求；实验自产账号/数据不来自生产。两实际截图已目视，仓库/数量可见、原样式保持。

浏览器早期01误查外壳隐藏表单；02在Bootstrap关闭动画结束前检查焦点；03全部21组通过后假定日志表audit_log而实际operation_log；04在iframe URL尚未提交时提前查frame。均为驱动定位/等待/表名问题，保留失败记录、没有改变产品或放宽业务断言。05-rest只补最后2项，不无故重跑已经成功的21项。

## 保留与未覆盖

现有物料键盘、Ctrl+S普通保存、保存忙锁、错误内容保留、栏目设置和历史已选字段复用原实现并验收。实体读屏软件、触摸设备和硬件验收仍待人工；本批覆盖明确九模板，不代表全站低频页或整个第5项完成。B5业务角色问题仍待用户答复。本计划任何生产DB/旁文件/链接的读、连接、复制、校验、写入，生产HTTP/账号令牌/库存单据/服务/监护/恢复预算均未执行。


## B9本地闭环（2026-11-08）

最终17完整模块504 passed、0failed/errors/skipped；原16完整模块476项断言和文件逐字节不变。其中11模块旧基线307 passed，扩入5相邻模块169 passed在最终整个15非测试候选物理撤回后实际执行，故总旧基线476 passed。最终28正确契约在同次整批撤回为28 failed；169原对照全部通过，0error/skip，15文件全部SHA256逐字节恢复。候选504与Chrome23组的10产品哈希相同；两真实截图已查看。保留所有原断言和初始驱动失败，不把跳过当通过。

证据：B9-candidate-results.json、lab/r8-b9-whole-final01/proof.json、lab/b9-form-browser-04和05-rest/acceptance.json。源码/台账三模块33项、8静态及正常hooks随后补证；本段未声称精确CI或生产生效。实际浏览器只编辑一次自有合成销售单，97表中3预期表改变，其他94表完全相同。


B9台账登记补记：源码/台账首次32通过、1失败，原因是新增BUG004尚未加入拆分后的显式登记集合，原历史unknown计数多1。整个15非测试候选再次物理撤回，旧源码三完整模块33通过后逐字节恢复；仅补新BUG004的固定状态映射和本地修复状态说明，原历史分布常量/断言完全不变。产品10文件、504项运行和Chrome23组字节不变；候选源码33项仍须完整重验，不把首次失败记为通过。


B9源码门禁闭环：新增登记还需处于“已修复”章节，现有月报按最近一/二级标题而非状态行分类；第二次32通过/1失败保留。已补正确章节并保留原分布常量与全部断言，新登记仅增加一项固定映射，原文件是新增行前缀且全部assert AST一致。最终源码/库存/台账3完整模块33 passed、0skip（lab/b9-source-03）。产品10文件、完整17模块504项、整批15文件28旧失败/169对照和真实Chrome23组哈希不变；后续8静态/正常hooks/精确新CI仍须验收。


B9提交前门禁：8项静态全部退出0，正常pre-commit仍启用；源码/库存/台账33 passed，17完整模块504 passed、0skip，整批15非测试撤回197项为28旧失败/169对照，所有字节恢复。Chrome23组按10产品精确哈希闭环。仅新BUG显式登记增加一行，旧断言/常量完全不变。精确新目标完整CI待验，生产未部署。


## B9完整CI失败、整批撤回与纠正（2026-11-08）

首目标88225cac9abc23ead5d8f60f45e24aee87a7a452（正常本地953cab47、treeae929b12）经17精确blob/full tree/parent/expected_sha force=false发布并fetch同tree CAS；完整WMS CI42416051471失败，unit1领料传输33fail/5259pass34skip，unit2盘点列表41与数量输入30合计71fail/3831pass23skip。其他unit0/4verify/lint/smoke/browser及AI/Perf成功不能抵消104失败，Windows正常跳过。没有宣称交付或部署。

立即整个17文件正常revert，本地0815948c与failed/revert bundles保留；以失败目标为父、已验收B8完整tree8b0cbbd4非强制发布575aee9925662c8d79e9f2a05087825e5e9457f5。fetch核对14旧blob、3删除及完整tree、CAS对齐，工作树干净；未reset/stash/强推。回退精确WMS42416715534、AI42416715519、Windows42417114970及Perf42416715527全部success，Android最新42311667571/8d3b4c5d祖先与输入无差异，恢复门禁后才纠正重放。lab/b9-ci-whole-revert、b9-revert-publication、B9-revert-exact-ci.json存证。

根因是三个测试消费者先在raw HTML定位offset，callback却从page_source展开外置JS后的源码提取，执行错函数：领料误选到排序的URL代码，盘点列表和数量监听同根。全仓排查callback(start_at)消费点后，本批九模板受影响仅contract_requisition/check_list/quantity_input_rounding三个模块；其他in/out详情未新增脚本不夹带修改。精确重放17文件后仅这三个既有测试改用现成tests.frontend_page_source.page_source统一定位与提取；全部Python assert AST和Node完整断言程序字符串均相同，不补URL全局、不放宽断言。

增加五完整消费者旧基线367 passed（205+162），故旧21完整模块843项。纠正三消费253项已完整通过；最终22完整模块871项、整批15非测试R8450项（28旧失败/422对照）、源码33、8静态及新精确CI仍须后续补证，不能把预计数当通过。10产品SHA256与失败目标及已成功Chrome23组完全相同，严格复用23组，不无故重复已成功UI。B9仍为候选、生产未部署，生产需重启 WMS 服务生效。


## B9纠正候选本地闭环（2026-11-08）

最终22完整模块871 passed、0failed/errors/skipped，含原17/504完整重跑及新增5消费367，旧完整21模块843项。纠正三个完整消费者253 passed，Python原assert AST与Node完整断言程序字符串逐一相同。最终15非测试候选整批物理撤回到575aee99：原5相邻169及纠正3消费253全部通过，新增正确契约28 failed、0error/skip，总450项28旧失败/422对照，15文件全部SHA256逐字节恢复。旧未纠正消费104失败严格复用精确失败CI42416051471，三个旧测试与10产品字节均匹配，未删除或放宽原断言。

10产品SHA与failed882/已验Chrome23组相同，严格复用真实23组及两截图目视，未无故重跑成功交互。产品/测试最终字节均已实际执行；源码33、8静态、正常hooks及精确新CI随后补证。证据B9-corrected-candidate-results.json、lab/r8-b9-corrected-whole01/proof.json及B9-corrected-local-results.json。仍未交付、未部署生产。


B9纠正提交前闭环：源码/库存/台账3完整模块33 passed（lab/b9-corrected-source-01），8静态门禁全部退出0（lab/b9-corrected-static-01），正常hooks仍启用。20文件整批候选含全部10产品/全部原断言和3取源修正；22完整模块871 passed、0skip；全15非测试撤回450项28旧失败/422对照全部字节恢复。Chrome23组与产品精确同哈希复用。精确新目标完整CI待验；生产未部署，本批不冒充整个第5项或90分目标完成。


## B9精确目标代码交付（2026-11-08）

最终bcac09b0c91014ee4f02e5c1d3c381ecd89eaf40，父575aee99，treef6ac1d65d6a50bd7dd38588744fe61c8adffb287；本地/远端一致且干净。正常本地50cf43d1及bundle保留，20精确blob（14原SHA复用+6新）/完整tree/parent/expected_sha force=false发布并逐对象fetch、CAS对齐。

[WMS CI42418212956](https://github.com/SIX2090/wms/actions/runs/42418212956)、[AI42418213035](https://github.com/SIX2090/wms/actions/runs/42418213035)、[Windows42418513830](https://github.com/SIX2090/wms/actions/runs/42418513830)及[Perf42418212952](https://github.com/SIX2090/wms/actions/runs/42418212952)全部completed/success，三unit/四verify/lint/smoke/browser/changes/gate成功；docs-checks全量代码分流正常跳过。最新Android42311667571/8d3b4c5d成功，main两页及祖先/原生源码/工作流零差异已核实。B9-corrected-exact-target-acceptance.json与local-results已code_delivered=true，覆盖之前待验状态。871本地、33源码、450整批R8及23Chrome证据完整；不冒充生产上线、整个第5项或90分达标。
