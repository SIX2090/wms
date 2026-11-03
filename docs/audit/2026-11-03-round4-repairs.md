# 2026-11-03 第二批浏览器问题修复与受限项代码检查

本批口径：8项BUG + 9项功能不足，共17项修复；另7项其他受限及29项硬件相关共36项仅检查代码。36项不计入真实设备/外部服务测试通过数，也不作为36项已修复缺陷。已接受的无作废态、单跳完成流程不重复列为问题。

## 环境与安全边界

- 基线 main：`9791d92c2d924e407e65fb3a2647994d641def28`。写入前三工作流门禁通过；Android复用记录有祖先和路径无差异证明。
- 独立 main 克隆：`C:/wms_audit/20261103_fixes`；生产共用目录 `C:/wms` 有既存改动，未写入该目录。
- 真实Chrome仅访问隔离服务 `http://127.0.0.1:5094`；数据库 `C:/wms_audit/20261103_evidence/runtime/audit.db` 来自本轮合成测试库。生产数据库、服务、密码均未操作，未部署。
- 独立启动器校验数据库绝对路径和测试账号/物料前缀；不启用打印代理及微信等外部工作线程。WMS_NO_DB_TOUCH仅禁启动升级，并非运行期只读；隔离库允许专用数据写入。
- 证据目录：`C:/wms_audit/20261103_evidence`。浏览器原始尝试含脚本选择器/等待失败，不能将这些尝试计为通过；有效结果见后续成功记录、下载文件和数据库核对。

## 17项修复对照

| 台账 | 原报告 | 问题 | 修复结果 |
|---|---|---|---|
| BUG-2026-11-03-011 | UI-R2-001 | 手机更换查询编码后仍显示旧物料 | 清空旧选择并按查询版本、仓库和当前编码核对响应 |
| BUG-2026-11-03-012 | UI-R3-001 | 入库Excel合并往来单位列错配且无效行留下档案 | 按采购/其他入库解释合并列；提前校验物料、数量、批次、有效期；出库同类无效行提前拒绝 |
| BUG-2026-11-03-013 | UI-R3-002 | 手机默认仓库的待盘点列表不自动加载 | 初始化即加载；仓库请求带版本，旧响应不得覆盖 |
| BUG-2026-11-03-014 | UI-R3-003 | 被引用合同删除返回500 | 格式化器兼容字符串及数量元组，保留引用阻断 |
| BUG-2026-11-03-015 | UI-R3-004 | 仓库工作台待盘点队列字段错误 | 采用 InventoryCheck.check_no |
| BUG-2026-11-03-016 | UI-R3-005 | 工作台链接指向不存在的页面 | 仓库链接改真实入口；补只读分页草稿队列；横向修正采购、销售同类路径 |
| BUG-2026-11-03-017 | UI-R3-006 | 合同、员工批量删除被全局函数覆盖 | 使用页面专用函数并同步按钮绑定 |
| BUG-2026-11-03-018 | UI-R4-001 | 第二张采购退货使用重复PR编号 | 两表共同计算当前月份最大数字序号，避免按ID误判 |
| BUG-2026-11-03-019 | G-R2-001 | 台账空物料仍可导出或打印 | 浏览器校验必填，导出/Excel打印/预览后端拒绝空物料 |
| BUG-2026-11-03-020 | G-R2-002 | 台账难区分反提交冲销和正常业务 | 依据历史 transaction_type 标明“反提交冲销”，不改数量和净结存 |
| BUG-2026-11-03-021 | G-R2-003 | 手机查找按钮缺少明确名称 | 增加“查找物料”标题和无障碍名称 |
| BUG-2026-11-03-022 | G-R3-001 | 其他入/出库八个翻页按钮永久禁用 | 按类型和主键查询首/前/后/末，详情保留翻页；边界禁用 |
| BUG-2026-11-03-023 | G-R3-002 | 盘点系统库存可输入但保存后被忽略 | 冻结数量只读并解释来源，实际库存继续可编辑 |
| BUG-2026-11-03-024 | G-R4-001 | 调整单详情无反提交入口 | 为有权限角色增加确认后调用现有反提交接口的按钮 |
| BUG-2026-11-03-025 | G-R4-002 | 采购申请未查询库存却显示0 | 缺失数量显示“未查询”，真实0仍显示0 |
| BUG-2026-11-03-026 | G-R4-003 | Excel纸张设置刷新丢失且不进入下载文件 | 每工作表保存纸张、方向、尺寸、边距、缩放；后端校验并写入xlsx |
| BUG-2026-11-03-027 | G-R4-004 | 手机待确认页选第一仓而非配置默认仓 | 按配置默认仓库设置 selected |

### UI-R2-001：手机更换查询编码后仍显示旧物料

- 根因：输入未清除已选物料，迟到结果可能覆盖新输入。
- 修改：清空旧选择并按查询版本、仓库和当前编码核对响应。主要入口：`app/templates/mobile_scan.html`。
- 验证：手机查询切换 AUD-M001/AUD-M002、无效编码；前端运行时回归。

### UI-R3-001：入库Excel合并往来单位列错配且无效行留下档案

- 根因：供应商分支先匹配“供应商/客户”；创建档案后才校验明细。
- 修改：按采购/其他入库解释合并列；提前校验物料、数量、批次、有效期；出库同类无效行提前拒绝。主要入口：`app/routes/batch_import.py`。
- 验证：真实上传混合Excel：2张成功、1行拒绝；核对客户/供应商及无孤立档案。

### UI-R3-002：手机默认仓库的待盘点列表不自动加载

- 根因：只监听仓库 change，初始默认值未触发加载。
- 修改：初始化即加载；仓库请求带版本，旧响应不得覆盖。主要入口：`app/templates/mobile_scan.html`。
- 验证：打开页面即显示 CK26110002，无需先切换仓库。

### UI-R3-003：被引用合同删除返回500

- 根因：引用检查返回字符串而公共格式化器只接收二元组。
- 修改：格式化器兼容字符串及数量元组，保留引用阻断。主要入口：`app/app.py`。
- 验证：真实删除 AUD-HT-001 返回中文引用提示且合同保留；无引用合同正常删除。

### UI-R3-004：仓库工作台待盘点队列字段错误

- 根因：读取不存在的 order_no，异常被吞后队列显示空。
- 修改：采用 InventoryCheck.check_no。主要入口：`app/app.py`。
- 验证：有待盘点单时计数为1并显示正确编号；路由回归。

### UI-R3-005：工作台链接指向不存在的页面

- 根因：详情和列表使用旧路径，未完成草稿入口未实现。
- 修改：仓库链接改真实入口；补只读分页草稿队列；横向修正采购、销售同类路径。主要入口：`app/ai/ops/warehouse_workbench.py`。
- 验证：仓库23个实际链接逐个点击；三工作台路由用例；保留角色约束。

### UI-R3-006：合同、员工批量删除被全局函数覆盖

- 根因：页面 batchDelete 与共享工具栏同名。
- 修改：使用页面专用函数并同步按钮绑定。主要入口：`app/templates/contract.html`。
- 验证：两页实际创建及删除专用记录；取消/空选/HTTP异常原断言保留。

### UI-R4-001：第二张采购退货使用重复PR编号

- 根因：PR分支只查询采购申请表，未查询已保存采购退货。
- 修改：两表共同计算当前月份最大数字序号，避免按ID误判。主要入口：`app/app.py`。
- 验证：真实连续保存采购退货；两表交错序号测试。

### G-R2-001：台账空物料仍可导出或打印

- 根因：导出入口未执行必填校验，后端缺少相同守卫。
- 修改：浏览器校验必填，导出/Excel打印/预览后端拒绝空物料。主要入口：`app/routes/report.py`。
- 验证：空导出不新开标签；三个接口返回400；有效物料正常查询。

### G-R2-002：台账难区分反提交冲销和正常业务

- 根因：流水类型标题未标明反向来源。
- 修改：依据历史 transaction_type 标明“反提交冲销”，不改数量和净结存。主要入口：`app/app.py`。
- 验证：混合入库/冲销/再次完成净结存测试，页面显示冲销字样。

### G-R2-003：手机查找按钮缺少明确名称

- 根因：图标按钮缺可读标签。
- 修改：增加“查找物料”标题和无障碍名称。主要入口：`app/templates/mobile_scan.html`。
- 验证：真实页面及渲染断言。

### G-R3-001：其他入/出库八个翻页按钮永久禁用

- 根因：只有禁用占位，没有同类型单据导航。
- 修改：按类型和主键查询首/前/后/末，详情保留翻页；边界禁用。主要入口：`app/templates/_other_order_navigation.html`。
- 验证：同类型多单据四向导航及不串业务类型用例；真实点击。

### G-R3-002：盘点系统库存可输入但保存后被忽略

- 根因：前端将服务端冻结数量做成可编辑字段。
- 修改：冻结数量只读并解释来源，实际库存继续可编辑。主要入口：`app/templates/document_table_form.html`。
- 验证：草稿输入实际库存并保存刷新；系统库存只读，无向下填充入口。

### G-R4-001：调整单详情无反提交入口

- 根因：后端已有反提交，完成态模板未展示操作。
- 修改：为有权限角色增加确认后调用现有反提交接口的按钮。主要入口：`app/templates/adjustment_add.html`。
- 验证：真实完成盘亏2后反提交，状态恢复草稿，库存恢复90。

### G-R4-002：采购申请未查询库存却显示0

- 根因：缺失库存被默认值0掩盖。
- 修改：缺失数量显示“未查询”，真实0仍显示0。主要入口：`app/templates/purchase_request_add.html`。
- 验证：选择物料后的真实页面及运行时断言。

### G-R4-003：Excel纸张设置刷新丢失且不进入下载文件

- 根因：设置仅存在浏览器内存，未纳入保存模型。
- 修改：每工作表保存纸张、方向、尺寸、边距、缩放；后端校验并写入xlsx。主要入口：`app/routes/print_template_editor.py`。
- 验证：A5横向/9mm/90%保存刷新和下载工作簿核对，非法值拒绝且原文件不变。

### G-R4-004：手机待确认页选第一仓而非配置默认仓

- 根因：下拉列表未标记默认项。
- 修改：按配置默认仓库设置 selected。主要入口：`app/templates/mobile_scan.html`。
- 验证：首个仓库与默认仓不同的回归；真实页面默认材料仓。

同类排查：批量删除对照共享工具栏；导入对照入/出库；工作台对照仓库/采购/销售。采购、销售“查看全部”落到真实业务列表，不能把该列表理解为完全按工作台某个统计子集过滤。调整单缺按钮位于 adjustment_add 模板；旧报告引用的 app.py BOM can_revert 行不是本问题根因。台账冲销只增强标识，流入流出为流水发生额，净结存仍按原有算术计算。

## 7项其他受限：逐项代码检查

| 原清单 | 操作 | 代码依据 | 检查结论和未验边界 |
|---|---|---|---|
| CASE-0002 | 修改密码 | app/routes/user_auth.py:change_own_password | 登录、旧密码校验、两次新密码一致、强度验证、异常回滚均存在；不提交改密请求。 |
| CASE-0660 | 开始识别 | app/app.py:api_ai_document_ocr | 核对登录/角色、图片类型和大小、视觉模型可用性、识别失败降级与人工确认；未调用在线模型，准确率/计费未验。 |
| CASE-0681 | 物料找图 | app/routes/material.py:material_image_candidates | 核对登录、候选查询、失败提示；源码中百度失败回退Bing；未联网查图，外部可达性与匹配质量未验。 |
| CASE-0691 | 网上找图并绑定 | app/routes/material.py:material_image_select；app/app.py:_save_material_image_from_url | 角色及参数验证；HTTP(S)、内网地址和逐跳重定向检查、大小/图片解码限制、事务回滚；未下载或绑定真实图片。 |
| CASE-0776 | 初始化业务数据 | app/routes/system_settings.py；app/services/business_initialization.py | 默认关闭环境门禁、管理员/密码/确认短语、签名预览、数据指纹、一次性nonce、校验备份、事务回滚；未执行预览/清理，不认证真实恢复。 |
| CASE-0863 | 微信今日发送 | app/routes/wechat_share.py:run_wechat_share_now；app/app.py:run_wechat_share_for_today | 核对管理员、确认框、主开关、发送目标、租约/幂等和失败处理；未调用发送接口。 |
| CASE-0865 | 微信重新生成并发送 | app/routes/wechat_share.py；app/templates/wechat_share.html | force 分支由明确确认触发，共用发送配置/调度通道；未生成或发送外部消息，送达结果未验。 |

## 29项硬件相关：逐项代码检查

| 原清单 | 页面及按钮 | 代码依据 | 检查结论和未验边界 |
|---|---|---|---|
| CASE-0005 | `/mobile/scan?mode=in`：拍照识物 | app/templates/mobile_scan.html：拍照输入/识物分支 | 核对图片入口、取消/超时处理及人工选择；未开摄像头、未识物请求，真实拍照效果未验。 |
| CASE-0006 | `/mobile/scan?mode=in`：条码扫描 | app/templates/mobile_scan.html：startBarcodeScanner / stopBarcodeScanner | 核对ZXing加载、手工输入回退、扫描会话隔离、关闭/pagehide释放轨道；未开摄像头，识码/授权/设备兼容未验。 |
| CASE-0011 | `/mobile/scan?mode=out`：拍照识物 | app/templates/mobile_scan.html：拍照输入/识物分支 | 核对图片入口、取消/超时处理及人工选择；未开摄像头、未识物请求，真实拍照效果未验。 |
| CASE-0012 | `/mobile/scan?mode=out`：条码扫描 | app/templates/mobile_scan.html：startBarcodeScanner / stopBarcodeScanner | 核对ZXing加载、手工输入回退、扫描会话隔离、关闭/pagehide释放轨道；未开摄像头，识码/授权/设备兼容未验。 |
| CASE-0017 | `/mobile/scan?mode=check`：拍照识物 | app/templates/mobile_scan.html：拍照输入/识物分支 | 核对图片入口、取消/超时处理及人工选择；未开摄像头、未识物请求，真实拍照效果未验。 |
| CASE-0018 | `/mobile/scan?mode=check`：条码扫描 | app/templates/mobile_scan.html：startBarcodeScanner / stopBarcodeScanner | 核对ZXing加载、手工输入回退、扫描会话隔离、关闭/pagehide释放轨道；未开摄像头，识码/授权/设备兼容未验。 |
| CASE-0023 | `/mobile/scan?mode=query`：拍照识物 | app/templates/mobile_scan.html：拍照输入/识物分支 | 核对图片入口、取消/超时处理及人工选择；未开摄像头、未识物请求，真实拍照效果未验。 |
| CASE-0024 | `/mobile/scan?mode=query`：条码扫描 | app/templates/mobile_scan.html：startBarcodeScanner / stopBarcodeScanner | 核对ZXing加载、手工输入回退、扫描会话隔离、关闭/pagehide释放轨道；未开摄像头，识码/授权/设备兼容未验。 |
| CASE-0030 | `/purchase_request/add`：打印 | app/templates/purchase_request_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0051 | `/purchase_order/add`：打印 | app/templates/purchase_order_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0074 | `/in_order/add`：打印 | app/templates/in_order_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0104 | `/out_order/add?type=purchase_return`：打印 | app/templates/out_order_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0203 | `/sales/add`：打印 | app/templates/sales_order_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0238 | `/out_order/add?type=sale`：打印 | app/templates/out_order_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0266 | `/after_sale_out/add`：打印 | app/templates/after_sale_out_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0357 | `/in_order/add?type=product`：打印 | app/templates/in_order_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0386 | `/out_order/add`：打印 | app/templates/out_order_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0415 | `/other_in_order/add`：打印 | app/templates/in_order_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0445 | `/other_out_order/add`：打印 | app/templates/out_order_add.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0679 | `/material`：打印 | app/templates/material.html / out_order_detail.html；标签打印路由 | 核对物料ID/数量、标签模板及预览/浏览器打印入口；未发送标签任务，尺寸、驱动、实物位置未验。 |
| CASE-0680 | `/material`：发送打印 | app/routes/print_queue.py；app/local_print_agent.py | 核对创建任务参数/角色、目标、认领租约和状态回传；代理有锁重试、心跳降级及Spooler中文指引。未创建硬件任务，队列成功不代表出纸。 |
| CASE-0783 | `/print_alerts`：打印工作台 | app/templates/print_alerts.html → /print_routing | 此项实际是打开打印工作台的导航入口；代码核对完成，不等于打印机在线或能出纸。 |
| CASE-0787 | `/print_templates`：单据打印 | app/templates/print_templates.html | 此项实际是单据/报表/标签模板分类入口；代码核对完成，未执行系统打印。 |
| CASE-0788 | `/print_templates`：报表打印 | app/templates/print_templates.html | 此项实际是单据/报表/标签模板分类入口；代码核对完成，未执行系统打印。 |
| CASE-0789 | `/print_templates`：标签打印 | app/templates/print_templates.html | 此项实际是单据/报表/标签模板分类入口；代码核对完成，未执行系统打印。 |
| CASE-0945 | `/out_order/1`：打印 | app/templates/out_order_detail.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |
| CASE-0946 | `/out_order/1`：发送打印 | app/routes/print_queue.py；app/local_print_agent.py | 核对创建任务参数/角色、目标、认领租约和状态回传；代理有锁重试、心跳降级及Spooler中文指引。未创建硬件任务，队列成功不代表出纸。 |
| CASE-0950 | `/out_order/1`：打印标签 | app/templates/material.html / out_order_detail.html；标签打印路由 | 核对物料ID/数量、标签模板及预览/浏览器打印入口；未发送标签任务，尺寸、驱动、实物位置未验。 |
| CASE-0966 | `/check/1`：打印 | app/templates/document_table_form.html；app/static/js/app.js 共享打印分派 | 核对页面打印/单据模板入口和保存状态分派；新增页的浏览器打印不等于已保存单据正式输出。未打开系统打印框、未发设备任务，分页和纸面效果待硬件验收。 |

36项静态检查未执行密码、初始化、在线识别、找图下载、微信发送或物理打印。摄像头权限、识码准确率、模型效果、第三方可达性、驱动/纸张/打印定位及消息送达仍待相应真实环境人工验收；不能从代码存在推断这些能力已实测成功。

## 统一验证与交付

| 验证组 | 结果与证据 |
|---|---|
| 修改前基线 | 123个受影响/相邻模块，1891 passed，baseline.log |
| 整批回归 | 1940 passed，regression-final.log；含新增行为和库存真相引用检查 |
| 最终相邻回归 | 387 passed，adjacent-final.log；含导航/快捷键/删除/导入/34个新增用例，覆盖最后的导航提示兼容修改 |
| 打印设置边界补验 | 83 passed，print-final.log；包含39个新增用例及纸张mm/cm/in/pt换算、多工作表独立保存，未改变既有断言 |
| 文档与权限补验 | 68 passed，final-focused.log；含角色拒绝、31条草稿分页、载荷不泄漏和历史台账逐项守恒 |
| R8整批物理回退 | 最终39个用例在基线36 failed/3对照passed，24个产品/引用文件备份后精确恢复；实际文件数以r8-proof.json为准 |
| 隔离冒烟 | 117/117 passed，smoke.log；根据用户要求排除改密，固定5094和专用账号，并限制可写入口；不是默认生产地址脚本运行 |
| 真实Chrome | 原17项对应交互；仓库工作台23个链接、采购6个链接、销售1个列表入口；8个其他入/出库导航；冻结90只读/实盘90可编辑保存；调整完成与反提交；Excel下载属性核对；browser.jsonl、data-download-proof.json |
| 完整AI校验 | 70脚本首次68通过/2失败；台账映射纠正后strict单项通过，大图测试首次MemoryError，关闭本次专用Chrome和5094服务后原8项完整通过。最终远端CI须重新完整通过，不将首次失败抹除 |
| 规则与源码 | verify_wms_bugs通过；full/full-gate无新增违规；UTF-8及乱码检查通过；暂存14条规则、全量A11及JS无原生非GET fetch检查通过；提交钩子仍执行 |

以上用例组存在重叠，不能将1940、387、83、68相加作为独立覆盖数。WARN为SQLAlchemy旧接口警告，未当作失败忽略。首次整批尝试因已出现16项夹具失败而中止，随后修复夹具并重跑完整1940项；新角色测试另补财务全局门禁的浏览器重定向/JSON403双通道断言，历史台账基线不改，只逐项登记新增17条状态。

- 回归中12项失败来自批量函数改名后旧测试提取器未更新，4项来自独立Jinja夹具未提供导航依赖；补齐夹具并保留既有请求、异常、取消及无提示分享断言。出库导入不套用入库专属客供规则，库存查询原有非导出语义保留。
- R8：产品文件物理回退到基线后新用例重新失败，再按哈希精确恢复；日志和路径清单存证，不删除/放宽原有断言。
- 本文纳入唯一修复提交。提交完整SHA、实际push结果及精确目标CI链接在仓库外 `C:/wms_audit/20261103_evidence/final-attestation.json` 记录；该文件未生成或未标记CI成功时，不得据本文宣称已交付。
- 生产需重启 WMS 服务生效。本批只提交推送，未授权上线，生产仍待单独部署验收。
