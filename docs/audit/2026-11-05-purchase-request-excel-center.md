# 采购申请材料申请单接入Excel打印模板中心（2026-11-05）

用户明确要求将专用材料申请单接入现有Excel模板中心。本批归属FEAT-2026-11-05-106 / PRINT-TEMPLATE-F04-PR-001；不增加另一个编辑器，不引入新数据库字段。

## 入口与操作

1. 系统管理 → Excel打印模板中心 → 采购申请模板，或采购申请新增/详情中的“打印模板”。可直接访问`/print_templates?target_type=document&target_code=purchase_request`。
2. 内置“采购申请·材料申请单”始终可见，下载不写库。管理员点击“新建并在线编辑”，复用原create_blank POST创建副本；支持现有字体、边框、合并、列宽、行高和页面设置。
3. 保存后回中心，将副本“设为默认”。采购申请详情“打印”自动输出填充该默认模板的Excel；`/purchase_request/<id>/print_excel`可显式模板打印。“普通打印”（`?format=html`）保留现有HTML版式。

## 版式与打印链

- 内置Excel与已确认图片相同的7列：序号、合同编号、名称、规格、单位、数量、备注；公司为广东惠电科技发展有限公司，制表固定余国珍，日期取采购申请日期。
- 每页15行，不足补空白，0/1/15/16/31行覆盖；超过15行按工作表分页，每页重复公司、表头、制表及日期，保证全部行都在打印区。序号连续，备注仅取手工内容。
- 复用已有_Filler、模板选择器及网格编辑/原子保存链；采购申请专门适配手工物料、独立行合同与空规格/单位。复制分页保留样式、行高列宽、打印区、页脚及图像；源Excel不被打印操作改写。
- 业务字符串以字面量写入Excel，不把以等号开头的合同或备注当公式。用户在模板中主动编写的公式保留。
- 默认文件损坏或临时不可读时，主打印回退普通版式并给中文提示；显式Excel出口返回中文400操作指引，不裸抛堆栈。查询复用既有busy_timeout和模板解析降级。

## 验证与边界

- 写入基线285b4611bdf07cedcf779e3a3d25afd2066eb385：WMS CI41957609340、AI41957609240成功；Android41937038001的成功SHA5a753090为祖先，相关目录和工作流无差异。独立main克隆开发，C:/wms原未提交源文件未覆盖。
- 修前新增11项均失败；实现后相关15模块166 passed。开发中修正openpyxl打印区返回字符串及纸张编号int/str的夹具表达，不放宽旧断言。追加图像跨页后专项13 passed。最终16模块177 passed（24项既有SQLAlchemy弃用告警），不与阶段166重复累加。
- R8：9产品文件整体换回绿色基线，新增专项13 failed、原模板中心8对照passed；finally逐字节核对恢复。未使用reset或stash覆盖共享目录。
- 真实Chrome：中心内置行可见且GET不建记录，点击新建进入现有编辑器；实际改抬头、字号18、列宽19、行高25，保存、重开、预览、设默认成功。读取真实HTTP打印出的Excel，文字、样式、尺寸、合同、申请日期及手工备注均正确；普通打印仍可用。
- 隔离合成97表数据库，119/119 HTTP冒烟通过。测试账号、模板和单据均为合成数据，未对生产登录POST或写入测试数据。
- 没有模型、迁移或库存改动；生产部署不运行初始化或模板登记，不向生产自动写入ExcelPrintTemplate记录。内置入口无需数据库行；用户在界面主动新建/编辑/设默认属于现有模板管理操作。保留生产WMS_NO_DB_TOUCH及受控只读启动保护。
- 生产需重启 WMS 服务生效。精确完整CI、最终发布包及上线回执待补。

外置证据位于C:/wms_backups/column_settings_20261105：prtpl-focused.log、prtpl-regression.log、prtpl-rollback.log、prtpl-browser.log、prtpl-browser-actual.xlsx、prtpl-source-smoke.log。


## 最终验收与生产回执（2026-11-05 12:33）

本节为最终结果，替代上文开发阶段的待验收记录。

- 源代码及界面8a16972e2e0a5694aeb27236e0bbd74384ce6e97；本地main与origin/main一致，经连接的GitHub通道推送，全部blob/tree与本地提交一致，expected_sha校验main且无强推。
- WMS CI [41967471273](https://github.com/SIX2090/wms/actions/runs/41967471273)、AI [41967471270](https://github.com/SIX2090/wms/actions/runs/41967471270)完成success；Android [41937038001](https://github.com/SIX2090/wms/actions/runs/41937038001)的成功5a753090为祖先，Android目录及工作流无变化。
- 最终16模块177 passed、24项既有SQLAlchemy弃用告警；新增13专项和9文件整批回退证明保持。没有放宽旧断言，没有已知新失败。
- 发布包759源文件逐份匹配Git blob，39界面文件匹配清单哈希。独立合成97表状态下完整新建/编辑/保存/重开/预览/设默认链验证，真正HTTP Excel输出包含修改后抬头、字号18、列宽19、行高25及实际测试单据合同、日期和手工备注；默认Excel及普通打印同时可用。实际发布包119/119 HTTP冒烟通过。
- 首次包验收脚本在设默认触发页面重载后读取已释放的CDP响应体，产生脚本协议错误；产品操作及默认设置成功。改为等待成功状态与页面默认标记，再核对实际Excel、重开和普通打印；未修改待验代码，复验通过。证据prtpl-package-browser-initial.log和prtpl-package-browser.log均保留。
- 原生lab/生产预检均schema_check=passed、read_only_startup=true；仅97次业务行读取被启动保护阻断，网络/凭据/文件/进程副作用0；没有初始化、迁移或模板自动登记。
- 沿用SYSTEM的WMS-Warehouse任务，2026-11-05 12:33:03（Asia/Shanghai）新PID13320健康，11.04秒切换，8080单实例。部署目录C:/wms_releases/20261105_pr_templates_8a16972e；旧f70826cf目录保留应用回退。
- 本机127.0.0.1:8080与外网gd2026.top的/login、/healthz、app.js共6次匿名GET全部200，后台及界面头均8a16972e，app.js哈希匹配发布清单。没有对生产登录POST或写入测试数据。
- 本批没有模型/结构变更，没有备份/恢复/迁移生产数据库，没有代用户创建模板记录，没有修改单据、库存或账号。内置版式入口来自代码；用户点击新建/保存/设默认后由既有管理功能保存模板配置。
- 原C:/wms的未提交源文件未覆盖。外置最终证据：prtpl-ci-final.json、prtpl-prepare.json、prtpl-lab-startup.json、prtpl-lab-preflight.log、prtpl-package-browser.log、prtpl-package-smoke.log、prtpl-production-preflight.log、prtpl-activation-result.json、prtpl-production-attestation.json。
