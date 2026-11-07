# 整改-05全站前端与模块维护冻结清单（2026-11-05）

第4项[生产生效验收](2026-11-05-release-identity-production.md)完成后，按用户要求进入第5项。本文件保留当时的完整范围冻结快照；2026-11-06已实施首批05-A并完成隔离验收，见[首批记录](2026-11-06-material-pages-csp-and-labels.md)。全站迁移仍分批进行，不把既有试点或首批结果写成全站完成。

冻结源码 `9e5d6db2b42083c1a9e3c5cfc880819706486fef`；[WMS CI42016754233](https://github.com/SIX2090/wms/actions/runs/42016754233)及[AI42016754278](https://github.com/SIX2090/wms/actions/runs/42016754278)成功。独立main副本只读取已提交源码，保留生产共用C:/wms中的未提交工作。盘点不登录生产、不访问生产数据库、不调用付费模型或外部收件人。

## 计数口径

- 147份HTML模板，包括页面、共享模板和片段，不能等同于147个独立页面或按钮。
- 23份app/static/js直属业务JS，不把第三方静态库列为本次自有模块。
- 119个内联可执行script开标签；另有2个application/json数据块，不计入执行脚本。
- 563处事件属性源码候选、8处javascript链接源码候选；含条件分支和生成HTML字符串，必须结合实际DOM、继承及动态行为复核，不能直接记为563个BUG。
- 当前新增确认功能BUG为0；这些数字用于冻结迁移范围，不表示功能完成率，也不自动改变独立审计评分。字段标签、模块拆分收益及实际操作仍逐项核对。

## 分批范围与验收

| 批次 | 范围 | 必须取得的证据 | 当前状态 |
|---|---|---|---|
| 05-A | 物料列表/新增、分类、单位、手机物料详情、档案预览，加上其实际继承的公共模板；复用既有material-add.js试点 | 隔离库真实Chrome的新增/编辑/取消/失败重试、筛选/分页/栏目设置/选择、键盘与焦点、字段标签关联；CSP实际无违规；保存及刷新后值一致；公共导航和相邻页回归 | 代码交付完成：9ed64878完整CI/AI成功；隔离冒烟119/119、Chrome23组及4组补充通过；生产未部署 |
| 05-B | 出入库、领料、售后及相关对话框 | 两账号版本/幂等边界、表头/明细输入、失败保留、模板预览、直接打印软件链路及相邻单据回归；合成多仓R2检查 | 待05-A交付 |
| 05-C | 库存、盘点、调整、调拨与报表 | 必填仓库、两仓隔离、历史空归属、合计等于全集明细、过滤/翻页/导出；CSP及标签实际DOM检查 | 待前批交付 |
| 05-D | 采购/销售/委外/BOM及其余业务；公共片段按消费点归属 | 实际有业务价值的入口与保存/校验/恢复动作、来源跟踪和权限；共享JS消费点完整回归 | 待前批交付 |
| 05-E | 管理、备份、微信/设备设置及其他管理页面 | 管理员/仓管边界、只读与暂停状态、配置失败回退；设备和真实外发仅代码/软件检查，现场验收另列 | 待前批交付 |

每批先核对现有实现，再冻结具体变更；只有清晰收益的函数/模块才拆分，不为行数指标重写架构。保留原有输入和库存边界，不通过删除断言、放宽CSP或隐藏功能来达标。每批完成适用本地验证、统一提交推送及精确目标CI后才能进入下一批代码写入；生产部署另按用户授权。

第一批的6份直接模板为category.html、material.html、material_add.html、material_archive_print.html、mobile_material_detail.html、unit.html。文件名分组只是索引，base及其他共享片段仍按实际消费链纳入；预览不等于打印机出纸，扫码/硬件动作按用户要求跳过实际设备测试。

## 模板完整清单

| 模板路径 | 初步分组 | 行数 | 事件属性候选 | 可执行内联script | JSON/其他数据script | javascript链接候选 | 文件SHA256 |
|---|---|---:|---:|---:|---:|---:|---|
| app/templates/404.html | other_business | 112 | 0 | 0 | 0 | 1 | `77ff0dd2fa98fddbbf9fe552bde5a2587b862093e969d0b88fa4caeddcd51ac8` |
| app/templates/405.html | other_business | 111 | 0 | 0 | 0 | 1 | `089a5c915463931cd91e59daedbb252617759df443be251e06d8be566f790e89` |
| app/templates/_autoprint_script.html | other_business | 88 | 0 | 1 | 0 | 0 | `88ace89699a679165be907582482fe57f77125cf64cf152c8d73415b1098ba14` |
| app/templates/_copyright_footer.html | other_business | 5 | 0 | 0 | 0 | 0 | `0c77046061231e7ac9a1717518131466ce06495e67fdd02bb068df50bcc88edf` |
| app/templates/_disabled_unused_20260506/bom_detail.html | other_business | 254 | 0 | 1 | 0 | 0 | `796254b7b5365b79c601615416b58d0ca26354034d74364c4fe59bcc0f746a3c` |
| app/templates/_disabled_unused_20260506/check_detail.html | inventory_reports | 691 | 17 | 2 | 0 | 0 | `7ae188e9d55021a4eea250e440c6e943922058abc972cb44b977b401d8e35fbf` |
| app/templates/_disabled_unused_20260506/requisition_detail.html | inbound_outbound | 651 | 8 | 2 | 0 | 0 | `80b017959be87228261d46c05ec6edc877a832a3126cea443b88a45b5bd5e1f1` |
| app/templates/_disabled_unused_20260506/transfer_detail.html | inventory_reports | 649 | 8 | 2 | 0 | 0 | `96f734ceea0f77c4698097f002551e84533feab35517aa7266da95cc405a761e` |
| app/templates/_list_macros.html | other_business | 193 | 0 | 0 | 0 | 0 | `a2c37bac96c3e7104af81ffbace5b0c5c13f51b7a5623f076e9d37fff6ac1c1b` |
| app/templates/_other_order_navigation.html | other_business | 7 | 0 | 0 | 0 | 0 | `36d15391f00d70613063930f387fed5b1e7f2cfb2ccf00a6155b889b6263a69c` |
| app/templates/_other_order_toolbar.html | other_business | 69 | 0 | 1 | 0 | 0 | `c7bef4dd8f9b7a789d961a8ea1d7e0b441ec9a5fc252a918c018540761fbd979` |
| app/templates/_report_toolbar.html | inventory_reports | 43 | 0 | 0 | 0 | 0 | `ee2616ef3ec18e1ef01130d8238d94701ba049f07863c03bef3be33750e7eec1` |
| app/templates/_requisition_bom_picker.html | inbound_outbound | 38 | 0 | 0 | 0 | 0 | `47a9ea7111e334aa460ba859bdcfe629deeae76f8c55c80a36a1ebd5f65d982d` |
| app/templates/_runtime_pause_notice.html | other_business | 7 | 0 | 0 | 0 | 0 | `00c11562eede5cd747a8442ecfad367870a82882bf7a728faff3fe47d4fa0016` |
| app/templates/_tplus_form_styles.html | other_business | 65 | 0 | 0 | 0 | 0 | `18da094cde90898216ad9cf8d2e67294cb6827c15839d24cf3d88d6cae414e9d` |
| app/templates/adjustment.html | inventory_reports | 316 | 3 | 1 | 0 | 0 | `8e5cc4e762c3aa2c86288f03726c97f24f239f7719d24b61002d93cc51cabc74` |
| app/templates/adjustment_add.html | inventory_reports | 946 | 12 | 1 | 0 | 0 | `9dd92b2073b1f7a7ca2b853c56d2618bc9144b3b103baf22c996d8e2198f260c` |
| app/templates/admin_console.html | other_business | 75 | 0 | 0 | 0 | 0 | `bca7a6b730fe518db8ba8a9e837791eb7d84fa555050c731bac0c20e39b04f37` |
| app/templates/admin_mobile_tokens.html | other_business | 41 | 1 | 0 | 0 | 0 | `4d30a836a0a0d0c19d80cad97d2c64aa469b89a3c3dd0a88d03b7dd291dccf0f` |
| app/templates/after_sale_out.html | inbound_outbound | 300 | 7 | 1 | 0 | 0 | `d167192d1715bba25379d5ba373fab5c59aab32a50af234150a724d38308fb07` |
| app/templates/after_sale_out_add.html | inbound_outbound | 891 | 10 | 1 | 0 | 0 | `8db8cd7d7d1a4fb186758df9ac77beee978c5fb85ffa7321999f175270431217` |
| app/templates/after_sale_out_detail.html | inbound_outbound | 259 | 4 | 1 | 0 | 0 | `d8129d25a2bbcd5012af396154568e313f2a44f4c3bbcbf49ba3471d4fbecce8` |
| app/templates/ai_acceptance.html | management | 95 | 0 | 1 | 0 | 0 | `d3b5bac86d2941ca5e19e8243694b40062bc38f6e3c0ed5b18fde8773f698d4c` |
| app/templates/ai_agent_task_detail.html | management | 75 | 0 | 0 | 0 | 0 | `daf71dff3e4b77a582f3a3438840975162ec1ddb2f55abe017cd5263793c33b6` |
| app/templates/ai_agent_tasks.html | management | 72 | 0 | 0 | 0 | 0 | `3c8e06a135cf314dfffc7a72d2c97f03268f3e8440e6e7726fe14b5742b25d54` |
| app/templates/ai_business_quality.html | management | 495 | 4 | 1 | 0 | 0 | `c1551743a81c242931c8d50bf34a05769dc6265f3d9b0f57e95713669c9f5d2a` |
| app/templates/ai_data_retention.html | management | 276 | 0 | 1 | 0 | 0 | `66753c46c0220d0462e1af3b588ebc371f536256aa3b42cbdf4456de727f0009` |
| app/templates/ai_demand_forecast.html | management | 377 | 3 | 1 | 0 | 0 | `9bb7b4db9d8b2378fae3e6de8d156eaa0cfb33f09efcc2b64736a69d797b8d3c` |
| app/templates/ai_document_confirm.html | management | 521 | 0 | 1 | 0 | 0 | `e5d82a0d7782951d3806441f4f7860b19b6e743e81e93d17021260bce35b068a` |
| app/templates/ai_document_job_detail.html | management | 217 | 0 | 0 | 0 | 0 | `bf8db077d6b53c166e53320f2b7ee3b1eb8536ffc4871001e003d010af760520` |
| app/templates/ai_document_jobs.html | management | 97 | 0 | 0 | 0 | 0 | `a1c8aef3d11c2d518fc81f0e4157f75f0b7ae1c66eb7f95dbce80b0f8cc68ec2` |
| app/templates/ai_feedback_review.html | management | 108 | 0 | 0 | 0 | 0 | `99c06e9f3211271dd6e52f8542439f908738459e1d306433583e4373077535c1` |
| app/templates/ai_inventory_health.html | management | 146 | 0 | 0 | 0 | 0 | `e1866eebabb983b65540687704a2ba425cc9e2f4856e69bb7bdf39f52d22b49c` |
| app/templates/ai_location_recommendation.html | management | 399 | 2 | 1 | 0 | 0 | `a249670de54ca4396114eeebcf14e9914ca67115abef254fb9bd18277d1b8f41` |
| app/templates/ai_material_alias.html | management | 171 | 1 | 0 | 0 | 0 | `2e88edcd52b3276ab7be314804ff0b04d69886ee6300c8cdc7382a9ac15ac44d` |
| app/templates/ai_ops_dashboard.html | management | 117 | 0 | 0 | 0 | 0 | `76b3b67962b5ee10f80beb8d17bdf4b1f58fa48b4029bbc0502a2aa75cc72622` |
| app/templates/ai_prelaunch.html | management | 93 | 0 | 0 | 0 | 0 | `900ef540f70c69aedb3c144491daca8c3dec22601be0f45299d88986e131db01` |
| app/templates/ai_processing_drafts.html | management | 16 | 0 | 0 | 0 | 0 | `3ffa69cc75bb43ba549143717a667e7a26a725588392545a889c9d168820b906` |
| app/templates/ai_purchase_workbench.html | management | 194 | 1 | 1 | 0 | 0 | `cd941162ca7cecef1e61691aa6bfae33a29d2386c135db135c1ee70cc66977c4` |
| app/templates/ai_replenishment.html | management | 132 | 0 | 0 | 0 | 0 | `1131990868dadb690f75eb04f178c4d6d5c053d0b6e650d2066988609fa8246e` |
| app/templates/ai_replenishment_smart.html | management | 133 | 0 | 0 | 0 | 0 | `3e8536092910739d9060a1dadd8c555bd16c2ad8b92f26e5795a420b287f8e27` |
| app/templates/ai_sales_workbench.html | management | 194 | 1 | 1 | 0 | 0 | `5146e1566b48c821f10bf42659a99e7f6fed28e4ba72991496f3d85b75170b2e` |
| app/templates/ai_supplier_evaluation.html | management | 283 | 4 | 1 | 0 | 0 | `4c3f4eff94ea75bc5a89583b56c0b2a6278de87f620fcc9e6daf063266388d4d` |
| app/templates/ai_warehouse_workbench.html | management | 193 | 1 | 1 | 0 | 0 | `b18178f8adef9f55e26aab70c100c492ab958c8b4cee11c0d56980e994776fc9` |
| app/templates/alert.html | other_business | 320 | 0 | 1 | 0 | 0 | `14af4c601e02e6bc982d08429e7d7280983cf3d59f0898106cc1dca751f749b8` |
| app/templates/approval.html | other_business | 194 | 2 | 1 | 0 | 0 | `1411c65864b1da3ee724e07dd9d8e18cb93662e3b97312e8ed17d2b260c281e2` |
| app/templates/backup.html | management | 84 | 0 | 0 | 0 | 0 | `bc7e8f1ea45bb6f7e2fb188abec4703d27c835cdf90a6c6b3bf855268020cbde` |
| app/templates/base.html | other_business | 1035 | 13 | 3 | 0 | 0 | `761cd481e84d58af3fba958a94e11ad29ccb169f9f8b08f11872ca388b366d4a` |
| app/templates/batch_import.html | other_business | 601 | 4 | 1 | 0 | 0 | `f05d7ec0900a03a38f65fba45904df68311e6db02909d73d2297db51a1739522` |
| app/templates/bom.html | other_business | 87 | 0 | 1 | 0 | 0 | `968919d6df69ba391b7668d5c4420ee7be2fa138863be3ab40779678fc5d635e` |
| app/templates/category.html | material | 378 | 3 | 1 | 0 | 1 | `62a3c0d1f0ca7638a77c7e7b036e2111dfcfff349059ce4d9ac6ce4601116ae9` |
| app/templates/change_password.html | other_business | 54 | 0 | 1 | 0 | 0 | `c38de81299aa50f428358bcf2ff3bfa4ea22a50edbe569913866a49249ff9abb` |
| app/templates/check.html | inventory_reports | 463 | 2 | 1 | 0 | 0 | `f50d30ba91ec275fb3d540cac86715dd464a49986adc680f102def0b8e1a9de3` |
| app/templates/check_print.html | inventory_reports | 93 | 0 | 1 | 0 | 0 | `7af9fcfeb9b38c78a01006430f3e0e05b536beb42301512d1a1314378c77f13e` |
| app/templates/contract.html | other_business | 451 | 10 | 1 | 0 | 0 | `a807aa4530415388c89a471d57ed8edfe7f21d6115e2adad3cab07a197189414` |
| app/templates/csrf_error.html | other_business | 117 | 0 | 1 | 0 | 1 | `6e322b8e16015934e1ba689c1006d5d8946fb5e666524b41880416340b2a44c7` |
| app/templates/customer.html | other_business | 314 | 2 | 2 | 0 | 0 | `a65c1bb0baa6ca4aa0323545f9deef327787d6cc6fcb4f3c064f65e1187f6df0` |
| app/templates/department.html | other_business | 228 | 4 | 0 | 0 | 0 | `44019ecdd077d15b2fa649c5b643be1778ca942ab94c2dc116a93fb7cec75f0d` |
| app/templates/document_ocr.html | other_business | 432 | 1 | 1 | 0 | 0 | `73cfaaa62f6a1441e6452c81de750a58782dfce1e0d6ce8de34130a7f476491f` |
| app/templates/document_print.html | other_business | 203 | 2 | 0 | 0 | 0 | `b807de8692651f9f4f5a9ff479e6f56c4140620a42fe4452c8383af627108b14` |
| app/templates/document_table_form.html | other_business | 1142 | 14 | 1 | 0 | 0 | `d04e2dc870945621cf601d8c75cc95d468295416c0029a38983f685fc62e540a` |
| app/templates/employee.html | other_business | 224 | 8 | 0 | 0 | 0 | `93b02e28351531aa19d2f980d05c9c18b69c33c7e57a962f975f3f73a08e2e63` |
| app/templates/in_order.html | inbound_outbound | 667 | 8 | 1 | 0 | 0 | `503b99eebecb26b2bcdf18f434ae47c13893a12e6f6dd52e48d00ae0dd10ed67` |
| app/templates/in_order_add.html | inbound_outbound | 2395 | 27 | 2 | 0 | 1 | `78dfffdcc998cadb3ba28cd1c6b842ef85a344646af9d6c3ce8383ceb423b884` |
| app/templates/in_order_detail.html | inbound_outbound | 1707 | 30 | 2 | 0 | 0 | `96fe5384a3f7736e2e01624ca35b58f21fc93f2bf2c951dce69f9fccc2475cca` |
| app/templates/in_order_print_template.html | inbound_outbound | 798 | 10 | 1 | 0 | 0 | `ada8a44fddc132b9303a3b01581c5f164c6eee20d4b385011c6cff23596c8244` |
| app/templates/in_order_push.html | inbound_outbound | 192 | 0 | 1 | 0 | 0 | `45b0946fddc8284f3fc88f650cebca8626f7b621788a642b672bced713cdc50f` |
| app/templates/index.html | other_business | 935 | 1 | 0 | 0 | 0 | `efdfd4f387da005c55a224f2eef4f2a824f74ebb98f4522991075de5b5c8cf2a` |
| app/templates/label_preview.html | other_business | 272 | 3 | 1 | 0 | 0 | `91391898d36de5c8a3f96a81aabf0ad77bbe0d379e92cb0e384e01a3da96b59b` |
| app/templates/label_template.html | other_business | 205 | 2 | 1 | 0 | 0 | `c1ad5312b9c5cae067b5c9e486e2c1397345d3e8f449b18c83abf9dcce626bce` |
| app/templates/label_template_detail.html | other_business | 919 | 11 | 1 | 0 | 0 | `ddd4f074b5674209852c29a88860fa3e048a2b4bf144242fa7304294a7b7e2e1` |
| app/templates/login.html | other_business | 917 | 0 | 1 | 0 | 0 | `cfdbdeb57c970fdd2b0161dac7783053462c6f4ac27aea72c93e0b3fb202bb30` |
| app/templates/material.html | material | 3919 | 52 | 2 | 0 | 0 | `5dc7ac3f2fad6e30ce58cb3e0e0e92c219e3fa658641b484942919fcfd29d88a` |
| app/templates/material_add.html | material | 135 | 0 | 0 | 1 | 0 | `383ae254c299ef8f9d7ce39dcc539d781d04ef6129aa5776cbd3b2b926271ebd` |
| app/templates/material_archive_print.html | material | 143 | 1 | 1 | 0 | 0 | `7cc608c0ce4c835d6249ead80acc4ab31eb4a253e652f11e5cc38fda54d591df` |
| app/templates/mobile_app_download_fallback.html | other_business | 45 | 0 | 0 | 0 | 0 | `c269b267c482b38092d7486e13d696022309ef071b45627fbc5e55f29937f918` |
| app/templates/mobile_connect.html | other_business | 119 | 0 | 1 | 0 | 0 | `9111b258816373340546aa8c2cfbd6b281e72cf94a0a2bbb13c2df5610f879ab` |
| app/templates/mobile_material_detail.html | material | 44 | 0 | 0 | 0 | 0 | `3c3cafdd50959f607d068fa915dcfcf62620d6cc9ab93b0df22d693271df6b3c` |
| app/templates/mobile_scan.html | other_business | 1723 | 0 | 2 | 0 | 0 | `5c64cb19b3e2939e80cd08e985499b504d1a297e9bf774e81d9dd1a4daa8970d` |
| app/templates/my_profile.html | other_business | 76 | 0 | 1 | 0 | 0 | `425afa2f8c75a3729be37a441c8700714f9178e35353c25517ccda3220c65dd8` |
| app/templates/opening_stock.html | inventory_reports | 318 | 20 | 1 | 0 | 0 | `e44c7c7f7f1722d57f199aab6ddc7a597aab6801c5c53100f8a0516cd04b1e86` |
| app/templates/opening_stock_list.html | inventory_reports | 159 | 2 | 1 | 0 | 0 | `f579297daaae09c56bbe9ec295e08b872e92cd982337828d83068847eaebb66c` |
| app/templates/opening_stock_progress.html | inventory_reports | 230 | 1 | 1 | 0 | 0 | `c06791b4798e060b279334d1bc57f608e1e042a2f293c47de2dd3489fcf48e22` |
| app/templates/operation_audit.html | other_business | 208 | 1 | 1 | 0 | 0 | `b8723c204ac46378b6cffed080ccb3e85fe493f3e95132c3f15f359ec74be4a9` |
| app/templates/out_order.html | inbound_outbound | 476 | 8 | 1 | 0 | 0 | `bdb31db26362937107ac8e36dae7e2d57adf5346250bf0aec287be76be20291f` |
| app/templates/out_order_add.html | inbound_outbound | 2131 | 18 | 2 | 0 | 0 | `875f84041513c0ab7dbf65d7cfa413a34fac065df2585c8843ba9ff355e21319` |
| app/templates/out_order_detail.html | inbound_outbound | 1715 | 29 | 2 | 0 | 0 | `822e5e98ae9fe8a9a452d1e9d050e66bf9b82cd8096fe72895fb417c94c16123` |
| app/templates/out_order_print_template.html | inbound_outbound | 581 | 8 | 1 | 0 | 0 | `8c994a75832b41558915acea8faef4fef2d6706428f46880af5b154a4269de24` |
| app/templates/partials/ai_report_pagination.html | management | 7 | 0 | 0 | 0 | 0 | `b043eca02798adc2dc07c4b48345c6bf4670cebc5d474659cc62b924ca052a35` |
| app/templates/pending_documents.html | other_business | 129 | 0 | 0 | 0 | 0 | `fb3ee028d997942cda601b1dda67bada48d27c4a67570a4a0bd89ddaaf8de68a` |
| app/templates/print_alerts.html | other_business | 119 | 0 | 1 | 0 | 0 | `7d54eeef95c5a15082d7b207fb1e8a0511a70d7039510cd69574315b1fbd850a` |
| app/templates/print_batch_labels.html | other_business | 720 | 4 | 2 | 0 | 0 | `13a6ea83160f1acdcfa8e7ed0980e3d40269298534c805b49b1ed4d771b85b0a` |
| app/templates/print_in.html | other_business | 118 | 2 | 1 | 0 | 0 | `6bba0eadef1f162e3d5390dc65f3a6a18b0ef5d157ccfb80c4554162b819d0ce` |
| app/templates/print_in_with_excel.html | other_business | 143 | 3 | 1 | 0 | 0 | `6bdcb7a42ddf028f70258d11b161133fcbdead9871b8c1755af8331f976bbc63` |
| app/templates/print_in_with_html.html | other_business | 177 | 3 | 1 | 0 | 0 | `7a7314e03c7be46a3a872fce67e84a6bb13d099ab31d085b3bb8ef0b32a0f4be` |
| app/templates/print_label.html | other_business | 407 | 6 | 1 | 0 | 0 | `f145d366ceac81b31c27384317925f064ef2ad497dd1988fa52b4b9bcc60f70e` |
| app/templates/print_out.html | other_business | 117 | 2 | 1 | 0 | 0 | `a33397de4f7ec7996bbbf98f93f731dea37d5999ad5338eb511e54e20fb4a8d5` |
| app/templates/print_out_with_excel.html | other_business | 141 | 3 | 1 | 0 | 0 | `8a4b66c59941aca2c3a87b122cd4edc64f97b00e43f0c64af89d5d4d47a24854` |
| app/templates/print_out_with_html.html | other_business | 69 | 3 | 0 | 0 | 0 | `337e63aab1bde6538954e876d54b3893b863971c5e3fff94f3a68291e614dee7` |
| app/templates/print_routing.html | management | 617 | 16 | 1 | 0 | 0 | `8f19dee3538105841fdfc576dcf99f855cc9833e0cc8208d1fbc66b00f01e523` |
| app/templates/print_station.html | management | 327 | 3 | 1 | 0 | 0 | `ce6c2cc7f7ebdf4859752a4daee85a0572360833d724605e66269e845f473d38` |
| app/templates/print_template_center.html | other_business | 112 | 2 | 1 | 1 | 0 | `ba8963a427419bd609936caa275a9b70353890814d2ff4290a31a5e0e1b45d4d` |
| app/templates/print_template_editor.html | other_business | 267 | 0 | 1 | 0 | 3 | `56d71205eae20c319a7e03cbbc1a76591f177f192b644bc2cc59d9f84aaedd1c` |
| app/templates/product_receipt_print.html | other_business | 83 | 2 | 1 | 0 | 0 | `9b6f26c8ef56ffee3297151af8f935864b5aaf7d31067068ea437ec2a59c76b5` |
| app/templates/purchase_order.html | other_business | 352 | 6 | 1 | 0 | 0 | `38a3a9e173f73717c4a49d25ee3fa95e1fcb0c648ee0d000f1f7ec5314390851` |
| app/templates/purchase_order_add.html | other_business | 1181 | 6 | 1 | 0 | 0 | `e27cc9dec29f9b7f25bf1ec61b3b51cad471e52c1a02d79df8a55edce49b878a` |
| app/templates/purchase_order_detail.html | other_business | 470 | 8 | 1 | 0 | 0 | `5cbee41353297e878de98066e9e6f718af692a9b8ee0b1b0d621f39754609c0c` |
| app/templates/purchase_report.html | inventory_reports | 151 | 0 | 0 | 0 | 0 | `abdc3b333270874ef783235773e711eb7e52ecbb33c37c43480762bc489dc201` |
| app/templates/purchase_request.html | other_business | 414 | 11 | 1 | 0 | 0 | `26743679fda48deb91ae4629222164308571eca240da5df731b181e0c265f419` |
| app/templates/purchase_request_add.html | other_business | 1161 | 4 | 1 | 0 | 0 | `04638de331838f2ce16c9f964b0d44557691a12a640b654bd8681b43da540226` |
| app/templates/purchase_request_detail.html | other_business | 472 | 10 | 1 | 0 | 0 | `95973e34af9d0a579134594c9a0bf86f81fd292c12ede73d63e99ae547ba5790` |
| app/templates/purchase_request_print.html | other_business | 81 | 2 | 0 | 0 | 0 | `ecda0e57597e53840c0eede8a257777561f017d0972d12fd61cb57f388c06121` |
| app/templates/report.html | inventory_reports | 148 | 0 | 0 | 0 | 0 | `c247bcb4ff25b8776ee0a4cbc4a1b01da529c42f6aaef13a54c6cd58a879db1b` |
| app/templates/report_dashboard.html | inventory_reports | 421 | 3 | 1 | 0 | 0 | `37b114bf3bac21c35f81939ad093559862bf1438de4272e76a0364a6679c7685` |
| app/templates/report_print_preview.html | inventory_reports | 69 | 0 | 1 | 0 | 0 | `86eaffdfd116e982b97c4d900e6ca51dcaaef2e76f554c3de1809017eaa76c4b` |
| app/templates/report_view.html | inventory_reports | 1248 | 0 | 1 | 0 | 0 | `8767f0d526ebf8a6ee4eb69f638ec00453043345a9be282390ce0334b2c18c39` |
| app/templates/requisition.html | inbound_outbound | 448 | 0 | 1 | 0 | 0 | `dad4494eabc888bda901fcabce71995a51b8c73b65ecf504518025894400dd65` |
| app/templates/requisition_print.html | inbound_outbound | 103 | 0 | 1 | 0 | 0 | `12a34406a5a494abaf2be80b978bc43477b53fa216f0ecb4702be9fb93ab4ae2` |
| app/templates/sales_dashboard.html | other_business | 14 | 0 | 0 | 0 | 0 | `fb4d67fae8a13ebc152f33184eb24582660f75e35bb70416c69f64108ee0eb49` |
| app/templates/sales_exceptions.html | other_business | 25 | 0 | 0 | 0 | 0 | `78196d7acf41cb9d7879265fd1f47ca5305aaec0e08c259673d661a0be014fa9` |
| app/templates/sales_execution_report.html | inventory_reports | 32 | 0 | 1 | 0 | 0 | `fb026384694fac5be881e367bad7aef25d4af641c2b873f127937af5aa07739e` |
| app/templates/sales_order.html | other_business | 346 | 2 | 1 | 0 | 0 | `0ab2d7496e24364f548a35251370bb0d6f1ecab1154f9a1acf6600df4cc26706` |
| app/templates/sales_order_add.html | other_business | 768 | 0 | 1 | 0 | 0 | `cf82a5e459a60a7bb4e931b735a7eae940d7224f8d8415e7430f9602bd6bec3d` |
| app/templates/sales_order_detail.html | other_business | 361 | 6 | 1 | 0 | 0 | `f9af726e6021b983eaa1f4bd267689790e7a8d8629a70333c5fb96e9900dc5d9` |
| app/templates/sales_order_edit.html | other_business | 1193 | 0 | 1 | 0 | 0 | `14eda12f569ec0122751b90f09042c5c0aea63ddc69c23bb451370e5446c55b5` |
| app/templates/sales_outbound_list.html | other_business | 205 | 0 | 1 | 0 | 0 | `e03ec610bf67322f585e698eb0c5b945aefe59e654e2ff9cec9b071bb1ae2d81` |
| app/templates/sales_outbound_selection.html | other_business | 404 | 6 | 1 | 0 | 0 | `137ff8329b9bc9bd0d28ad1ae2f29897974f4e80049aa82f79a3017ffdcc5301` |
| app/templates/sales_outflow_report.html | inventory_reports | 149 | 0 | 1 | 0 | 0 | `2452ec07f40043f071bec37e0014131a4f5ff4cb666feb54ab39b4ab0f54ab29` |
| app/templates/sales_price_analysis.html | other_business | 20 | 0 | 1 | 0 | 0 | `6aaf56bbb7c467098c74cf1cdf43b28c27fe627686121a37549deaa46fea132a` |
| app/templates/sales_reconciliation_report.html | inventory_reports | 214 | 0 | 1 | 0 | 0 | `f8b712dcf49d409b8bd1eca86a339951b46862a3562237e32089ee313d1112e5` |
| app/templates/sales_report.html | inventory_reports | 231 | 0 | 1 | 0 | 0 | `d98f0270950e857f48228bdb1172ccfe5c3ce39992f697e09f5e9472110ecc09` |
| app/templates/sales_trend_report.html | inventory_reports | 144 | 1 | 1 | 0 | 0 | `8d751e972c9c8dc905e132ccc8d9065502f7c6f4a3bff274c0b65faffd019f37` |
| app/templates/stock_query.html | inventory_reports | 168 | 0 | 1 | 0 | 0 | `7a163676e55e88eb65343aa72851d3f41d5506262279946e7358a7b5da574c8a` |
| app/templates/subcontract.html | other_business | 406 | 5 | 1 | 0 | 0 | `d413a487d0b00d941a33c5851425a41161936696e693d0df42f4c0070cc6da5d` |
| app/templates/subcontract_detail.html | other_business | 1104 | 13 | 1 | 0 | 0 | `21751cbee87eb7bd6f70e8859fb6843da08eaa864ca846c4d1f41d55a7f13d94` |
| app/templates/subcontract_issue.html | other_business | 508 | 9 | 1 | 0 | 0 | `f9e45073abf46e7c5c0c0d081bcb99688b4c71de0926b14656bb6cb246ef4159` |
| app/templates/subcontract_progress.html | other_business | 171 | 0 | 0 | 0 | 0 | `1e54ea99d5fac8af3dd171d44ab047b6b02aaa4fa686d82c6645fa31087fbcc5` |
| app/templates/subcontract_receive.html | other_business | 523 | 9 | 1 | 0 | 0 | `1b96d6acafe60fb02af37f714fda26211cf797b356afcf4a57ada38e362a2d7f` |
| app/templates/supplier.html | other_business | 330 | 2 | 2 | 0 | 0 | `9df7c133c9d70eab7eadc8d64786434d87364fccbe6e0424889de7940d55ae0c` |
| app/templates/system_settings.html | management | 521 | 1 | 1 | 0 | 0 | `6e6cccfc7268894a93cecf01e235c0a133645e88065b32e0d829cb2a1aca917f` |
| app/templates/system_status.html | management | 37 | 0 | 0 | 0 | 0 | `19ddc5b094f4b468f02e049a2581ca4b8e47cae3c20868cbefec2d7d618aded8` |
| app/templates/transfer.html | inventory_reports | 398 | 2 | 1 | 0 | 0 | `4fcc09d3c9d948875392c4c790214250b3aff97db45991929e68075eda7472ad` |
| app/templates/transfer_print.html | inventory_reports | 106 | 0 | 1 | 0 | 0 | `e64985cd303f7db76bdc4711ac3b62ca2a3819c45338b17d33fe5448c80f91d1` |
| app/templates/unit.html | material | 249 | 2 | 1 | 0 | 0 | `e417bafcdd6c5d807db01aeeceaaeae16b666c76a6ba5aeb6ff5a4069a8ccf43` |
| app/templates/user.html | management | 358 | 6 | 1 | 0 | 0 | `ebf24cfab2aad2f09e66d2c350803b54d9c163737310249f13af412b544ef5e9` |
| app/templates/warehouse.html | other_business | 272 | 5 | 0 | 0 | 0 | `776fc6462adeadc5332c8a06a8c6b70ae20756ab43dab127b5974422459f96a1` |
| app/templates/wechat_share.html | management | 554 | 11 | 1 | 0 | 0 | `dba119c50d6310ae45474b98f76c30a9943a4b2656d3cef6437b86421502b9e8` |

## 业务JS完整清单

| 路径 | 行数 | 字节 | SHA256 |
|---|---:|---:|---|
| app/static/js/api.js | 253 | 10360 | `ffac5f7ed43acf654fb263373acbb9e1e36eefcb5f51088169c2d0385358d836` |
| app/static/js/app.js | 4650 | 214243 | `42880ec359bdbcfc36e830ed94a48723f02260d5370db25d985a7d416a62ad8d` |
| app/static/js/backup.js | 60 | 3584 | `95eefb4bc54bbdebeee4d9724e0d97f77180fe486f78bbc825820a435dac4581` |
| app/static/js/decimal-input.js | 25 | 1060 | `397525e0eb46200eea7f2adf1bed54c5e9e5f776d9694d55139d9e4a938392d6` |
| app/static/js/document-action.js | 31 | 1401 | `aa4a1f4a706869c0269e291db8d861dbd90141595e980d7f25089b54d0d7c512` |
| app/static/js/document-edit-guard.js | 46 | 2269 | `bb233d0edbe91f033cd4db1f08fbe09a71de08582c2ca474449db533cec4000e` |
| app/static/js/dropdown-position.js | 50 | 2623 | `e0335c4af50cacdc197a7548959de314781a7039ffea3984ef1ae6b4a92c4618` |
| app/static/js/excel-import-export.js | 520 | 21647 | `7496b19c8e1aba2ea3b05a295676f2d30192f962b0c972d5cc351b2a7e1cc155` |
| app/static/js/excel-table.js | 627 | 23049 | `1dda3d42e5ea0c1c0947095d5637129743fbe7b52bd4601fb045efa7d2a6344e` |
| app/static/js/list-cache.js | 33 | 1313 | `dc5bd13765293036db32fbf38c279a4a79e56921b8a9e55d7cbb11098adc75ab` |
| app/static/js/material-cache.js | 94 | 5126 | `75b9bc2d4ca26c5e664f34875f549add105f4f088525c01a9ad01e10dc95ec27` |
| app/static/js/material-movement-report.js | 11 | 532 | `09a14533565fd5879f690f7d16f6fd54b77bb28c313ba2313abc092f2f4c7da8` |
| app/static/js/material-picker-keyboard.js | 65 | 3557 | `efd36f931638dfe47dcd97aa9c163f1d2fefa33eff33a48b3e2ba5ca0ececf74` |
| app/static/js/material_merge.js | 173 | 10723 | `d284d35bfe8d38b0b39a83a7e89316e7cfc9ad94128d02163dbf84926d46af17` |
| app/static/js/product-receipt-contract.js | 76 | 3419 | `99f403729f8a88194fffd2b4cc0edd831be8915d0c8dc8cc86d6e3fa38619ee7` |
| app/static/js/quantity-summary.js | 55 | 2826 | `5ce9dad80c6bc4bc324b679a0dfca600f9654f8db9e29e518cae027431f04215` |
| app/static/js/quick-select.js | 579 | 25184 | `c25369fec57ebb0fb91595f277c5b21358ba113f1432a56dc09d83d61e0eed28` |
| app/static/js/report-workbench.js | 153 | 8664 | `d6054be0b25bf8e63a0c7979d1b98d8acbff9a6d455f352a8273b2362166979f` |
| app/static/js/requisition-bom.js | 47 | 2260 | `0ddab33f3f19589c93ed3dc1ea9f9e05f27f2bf5248d96bf4c2dfbe56344391d` |
| app/static/js/select-refresh.js | 54 | 2697 | `0e6bc230d7c3dca7bb5e5f3d9e0f790ab3dc770aec8d92372cfb0b671a1fcfb3` |
| app/static/js/subcontract-material-selection.js | 113 | 6058 | `e6f95c8ab18ec60480e06ec68024943a7b3b8f3d0b8725ffb6e83dcdd9d54d71` |
| app/static/js/warehouse-monthly-report.js | 27 | 1386 | `88b07b2ab20db884d2d5e8120b08362eee5ce97b20677ecef94c2dc6e5be3d80` |
| app/static/js/xlsx.full.min.js | 122 | 944491 | `36a42f409fe9b8b8e4d112f0edc826883e40ed88eae071987a427a0389b06c03` |

## Python模块维护范围

下表冻结app.py及现有routes/services直属模块。行数与函数数只用于定位维护成本；没有把大文件、复杂函数或已有路由拆分自动登记为功能BUG，也没有承诺重写每个模块。实际拆分须说明边界、消费点和可验证收益。

| 路径 | 行数 | 函数数 | SHA256 |
|---|---:|---:|---|
| app/app.py | 36441 | 971 | `66eb858996f0efd86ec24afb6bbf19ddba4cc1ff8a31d5337761a52993942467` |
| app/routes/__init__.py | 9 | 0 | `3252669f73ce8134638511ec6be18a9622196ab07e0b8d3f7b15fba667b6beb4` |
| app/routes/adjustment.py | 849 | 12 | `7d92e3eaaba6a93b65c4f613f91664b446f5190c66dc0f4b726bea30a366a1f8` |
| app/routes/after_sale_out.py | 890 | 16 | `62e4737bbe30be6eaa60323cdeb445f7db52b4223fea03f7e37fce74c0554efb` |
| app/routes/ai_excel.py | 219 | 5 | `96406a2c412cb1924ec14bbf78d7f2ea33113f2bdedac0056f86af47bbd76a6e` |
| app/routes/ai_feedback.py | 93 | 2 | `f24b20f4a9d19de2b7fbc284ab8f024c39ae218786d5ca8bd1d0fc8a7cfeab3d` |
| app/routes/approval.py | 121 | 4 | `73f1d65b743ded03451260f5a683950d1343005fbacf458694a7cde1f684362e` |
| app/routes/backup.py | 175 | 10 | `7d5a4b672cb17ede26e62d09f81af98670daccb37782dce8e87f095a158cc19d` |
| app/routes/batch_import.py | 1080 | 20 | `464b6f125a3de55ee4ede3e414b1eafc69e7b11c57b45e80c76c5e0faef111b0` |
| app/routes/bom.py | 822 | 23 | `7ba13b1c257125e965f08c5d8f18f3d909654d4e34e0578666605a07c5363d3a` |
| app/routes/category.py | 300 | 9 | `65fb7284e0607a21930f33400ce97e72aaca1be99cce4705ed05074888197b38` |
| app/routes/check.py | 1214 | 21 | `df86db137119ce400268232243ab64d7979d724001d8a45e391fc31b05d743b1` |
| app/routes/contract.py | 372 | 12 | `a55d0f70c3bafb1b47dfcfc03c84b802007936db56c50bab985e8f0607010e1b` |
| app/routes/customer.py | 328 | 9 | `c247e33b0d5b1213464a69af9266590695d2658f846b93cadf9e410ab68a2050` |
| app/routes/department.py | 296 | 11 | `d8f9d739c58940b3d7cbdc75ec8756e33e53dfb4d9950c384e1f7ea4a89c580b` |
| app/routes/doc_print_excel.py | 125 | 4 | `57796bc10fc8cf21d4a68b82b7915c53568482ba08c849a9043a4f8694cac4a2` |
| app/routes/employee.py | 351 | 10 | `39fde649d522d3418bb1a046d94ce0357b56806f5d2f4374df54d211e4d43851` |
| app/routes/export.py | 444 | 16 | `660bee72900a1ef5de2a8788c90d01b4404462730445984f029dded3fd49a6f5` |
| app/routes/health.py | 33 | 3 | `d5c0c3ab68e202c38220fc25ce5a455fc3850d34d2e96fd6ee5f5e56ee401be8` |
| app/routes/in_order.py | 3524 | 50 | `9186edb0b895d53744df8e0c83276f34d1b39529807e77e71e7dfc87137ec260` |
| app/routes/inventory_alert.py | 380 | 6 | `9aaefcac701a4b4045067508b326e730bd5557fd0a5857d4f5f7a26204587792` |
| app/routes/label.py | 148 | 4 | `719f7e7fa501897b801cbfb6a97c302f7456caff197de16159673bbd0b98f80d` |
| app/routes/label_barcode.py | 456 | 15 | `8541e97ff0bd40cd080460afe4bc5abc179c860724c9f3350717ba9c08ca28d6` |
| app/routes/material.py | 1443 | 25 | `ba787842037028d9fa8b7e6e9eaa1fcef3fbe56f8f38f81c555e387cb9ec374d` |
| app/routes/mobile.py | 1584 | 39 | `949947f9822db9068666a1d22cd36474bc90ca7c014383c9fd369e15f5e75469` |
| app/routes/native_api.py | 4151 | 67 | `87f00e73fc8b45a4c2ae4bd5341bfcf499a881f02b610b4924b652c6efd10696` |
| app/routes/opening_stock.py | 1330 | 17 | `dc94cd8a643c589c19810e7c616cbe857e8da5e5af2d5758b26b63c3703f0241` |
| app/routes/options_api.py | 345 | 12 | `99200054b2ca4a74fcd5ad33a1850ec57425a85641f675be1c97a4a8afc680d8` |
| app/routes/out_order.py | 1968 | 33 | `0bf946e7fe13d86b0e50454bfefdc26905aeec8059317c0f498f6ff9ea61f23f` |
| app/routes/pending_documents.py | 83 | 3 | `4fdf9303415996677e01c4c76bd5251ded3d4cb20320ee25e2abd96e1d54678b` |
| app/routes/print_alerts.py | 493 | 13 | `a0d23a1e18a3b93934a67118af386e600ce114ff734e83d1ddd1f5bc0126dbd3` |
| app/routes/print_queue.py | 922 | 39 | `58a409517aca0260a3b2b4aaab8379f9488c43a4e3086128b58a774f7e0cdcde` |
| app/routes/print_routing.py | 592 | 27 | `1af668135b50f6fb7577e6ed1991f95991117aa062c50bce908600cdfddadf09` |
| app/routes/print_template_center.py | 305 | 16 | `16934bc6275cb77bb4cfc28e1d85851a48141e03bc7b1f7ab06eccd0b0f7e8a0` |
| app/routes/print_template_editor.py | 447 | 26 | `60c4809ef7c1064903d92dbe66a531e929d77b2be20cd02e5678cc6c28e08f27` |
| app/routes/purchase_order.py | 1087 | 17 | `8d88a0f4f2ff828651a8d5136a603fa3cf04d239d3d25321a8240ca528f23e99` |
| app/routes/purchase_request.py | 927 | 16 | `53c7d5fd82a806320d4f4c43b8bcb7023d5327b8b1d2437c63ca7c5437b0d001` |
| app/routes/report.py | 670 | 15 | `240dffa51bb972ad3e48101c06849e39b4c680cbc423d153f87d4d6bd61d4f15` |
| app/routes/requisition.py | 1050 | 20 | `5636300273ad6828d948a94a631258b78a9e3c238ca921d6d2f0cca30d07b043` |
| app/routes/sales.py | 1875 | 42 | `5629365475e5717371082ffdbdc46684644a73ef64d8802d3b6aca68cf34850b` |
| app/routes/stock_query.py | 253 | 7 | `3ec409cfe893d542eff0da0e2e32428dbaa22cd795798739243a21e67a265af8` |
| app/routes/subcontract.py | 2518 | 45 | `42e4a960655d14b2b6f167fc1fb5dce61a40b1f6030ddac13dfcc9133a8dffbd` |
| app/routes/supplier.py | 244 | 7 | `e3deee5f0f8f74dc6dfd9b5ca4fdd8e7fd685d81fbf10fa13acbcbb233792408` |
| app/routes/system_settings.py | 263 | 10 | `2f8d571ff34eb99c0de2ef9a75cae976f4ed7720e95e2a5724a31f72728f4690` |
| app/routes/transfer.py | 1094 | 22 | `64865f004ad4b60079b0847e6daf4e96891ca16b870420838c66673ece515182` |
| app/routes/unit.py | 152 | 5 | `9731e71d0e1af32d6fdd73af10499aa5f5a648974680d0be0edecb5a8cb5e17c` |
| app/routes/unit_supplier_import.py | 236 | 7 | `6d5a2b08f483665fc7cab3b55315fa5f301b60e41971be78fc98a36a8a446ad5` |
| app/routes/user_auth.py | 846 | 15 | `578842770d3425c311cb055f3dee48a2c0319b974bc6bf3a2c04d29b25e76bd6` |
| app/routes/warehouse.py | 373 | 12 | `14cea920d7ce70a77849d9c0ca6f43675af2e36507394570ad9f5182e8b928ee` |
| app/routes/wechat_share.py | 357 | 11 | `9461625a6890905b1489660974252a794497ba352f7002b1e79710eced4b4118` |
| app/services/__init__.py | 5 | 0 | `8409567dbb86c26b273d2fce1e3d44b029eb25131466d812443efc075b66b77d` |
| app/services/business_initialization.py | 142 | 7 | `0c38b5e5c74a68fa336525845ac0ee0364cc872ef98ab85822a682c9cbb4bcfe` |
| app/services/document_duplicate.py | 49 | 3 | `39b87d76b565c6b6437b3031912fd1cc28a6a53f1609f9b0810819e77c2fdd65` |
| app/services/document_edit_guard.py | 277 | 11 | `f4221298171f73f61cc7533b3d4973322c167909cfb277a3727a957cc3ff2a0d` |
| app/services/document_ocr_feedback.py | 30 | 2 | `d3fe9ba9f7c7c1473e7dfb4fb3149848cfe19753cda2290fa3faa270ee7b4679` |
| app/services/document_ocr_numbers.py | 103 | 4 | `222155dc0db0613a36838950a5851a99038bdb0359ffd922fbe2923ed56fa92b` |
| app/services/document_return_guard.py | 43 | 2 | `07d9ae09781c9137fe077c230b9e28911a3f0818b7a3a61190e0aff7f74238f2` |
| app/services/label_excel_preview.py | 148 | 3 | `e900bd4559c0743461f5b168c0b4dc87cfd0f51e2d0129f86cffeded79c2dbb6` |
| app/services/material_delete.py | 101 | 1 | `6f0ecf4d91b0a224a822302829d895284cf5684e41b897db42360d89f7c34ee4` |
| app/services/material_form_policy.py | 24 | 1 | `43905486b88482cdd3279e53b1734be578927357f58793cec8c9fb3a04bf964e` |
| app/services/material_image_candidates.py | 36 | 2 | `f585e032c9a12847c070bdd1219892a4121e67579d29bca2fae23e00f983a318` |
| app/services/material_label.py | 35 | 2 | `c3c94a4b589fef9dbc32a2e545b585562d71aa08080f0c49c1079df97d75fca0` |
| app/services/material_merge_preview.py | 69 | 4 | `14377eb0bbb722580453a557fb64773055e2e422d53d80f3c27632d4b24523ef` |
| app/services/material_movement_report.py | 125 | 3 | `190264fd8d116e1ae448a428dc18812a72cd2c3f7dffe6fe7dad686ba875f47a` |
| app/services/product_receipt_print.py | 114 | 3 | `c75286a297c08ef159aa5da71d816c065a96bf20c9cdfb0c4c6e518f3d3dba12` |
| app/services/release_manifest.py | 160 | 10 | `f1920523849a996da5332de790f4df7fd8a0bc824301a6ff71991a38cd623ba8` |
| app/services/report_print_preview.py | 304 | 7 | `e1031186f70f95bbc01db56ee82bf4f5e1befaf98428a72399b78d03da972b99` |
| app/services/runtime_status.py | 125 | 6 | `274e1d6465f6f213fa9c6d5cb90446d371b9ca9f34f0a2262a4626bab1a10e40` |
| app/services/sales_report_print.py | 460 | 9 | `77b219c14fb7ffb0751c0f00dee2683a12509bf89ab49f6b4d738d66c7d2eb0c` |
| app/services/stock_print_preview.py | 136 | 6 | `faaf6bf9404836281bd4670bc1e4ace996e13cc9786e54db31dc448b96f05b6f` |
| app/services/stock_unit_guard.py | 15 | 1 | `e911a754e6af62b22a0ee367eb631eb32c7266d6ab55338ca2b6f9ddcf6933d9` |
| app/services/warehouse_monthly_report.py | 130 | 4 | `a60fb7e59aeb9a81aefa41b6536584326f6356cf7934890b26987e33077924e0` |
| app/services/warehouse_scope.py | 58 | 1 | `b970f0dad1b2c353dea5320eb5dc405ca0ab7e2348fcf16cfafb9391432afaa9` |
| app/services/warehouse_stock_service.py | 395 | 8 | `beb62361a318fd0ae5d0295bd0f52b860f166505d9949bc62e3c45e1ed7e5cdb` |
| app/services/web_document_idempotency.py | 104 | 5 | `b860eb4433d8b628e0b7872f92f8a50785e7bcce2fe978f9db2da9faa5cb8b1e` |
| app/services/wechat_share_cleanup.py | 185 | 10 | `92ca19fe58648c61647321defc6de730c612c175142e0a6d8ec6d586ac1e549f` |
| app/services/wechat_share_dispatch.py | 190 | 6 | `b475f3c468299df0ee0c62cf745ad35d6e52cdee682392b25a22ad0e9eddbeaa` |

## 原始明细及复核方法

仓库外 `C:/Users/Administrator/Documents/Codex/2026-11-05/wms-operations-recovery/audit05-inventory` 保留summary.json、templates.json/csv、execution-points.json、javascript-modules.json和python-modules.json；执行点带文件、行号及类型，公开冻结表保留完整文件摘要。重验从上述完整Git SHA提取源码，按实际渲染补齐继承、条件分支和动态HTML，再逐项关联交互用例。两份JSON数据块继续保留为数据，不为减少静态数量删除。

本次只完成范围冻结及验收设计。尚未宣称CSP全站完成、标签全部合格、模块拆分完成或全部按钮穷尽验收；下一步05-A从既有新增试点和物料列表实际DOM开始。
