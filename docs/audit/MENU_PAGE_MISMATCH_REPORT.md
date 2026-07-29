# WMS 菜单 vs 实际页面 错配报告

扫描范围：`app/templates/base.html` 中所有 `class="flyout-link"` 和 `class="nav-link"` 菜单项

共扫描 **74** 条菜单链接，发现 **9** 条菜单文字与实际页面不一致。

## 1. 全部菜单访问结果

| # | 菜单 | URL | HTTP | 实际 title | h1/h2 |
| --- | --- | --- | --- | --- | --- |
| 1 | 采购申请 | `/purchase_request/add` | 200 | 新增采购申请单 | - |
| 2 | 采购订单 | `/purchase_order/add` | 200 | 新增采购单 | - |
| 3 | 采购入库 | `/in_order/add` | 200 | 新增入库单 | - |
| 4 | 采购申请列表 | `/purchase_request` | 200 | 采购申请管理 | - |
| 5 | 采购订单列表 | `/purchase_order?view=list` | 200 | 采购单管理 | - |
| 6 | 采购入库明细 | `/in_order?type=purchase_in` | 200 | 采购入库单 | - |
| 7 | 供应商管理 | `/supplier` | 200 | 供应商管理 | - |
| 8 | 采购报表 | `/purchase_report` | 200 | 采购报表 | - |
| 9 | AI补货建议 | `/ai/replenishment` | 200 | AI补货建议 | h1:AI补货建议 |
| 10 | 采购订单执行统计表 | `/report/view/purchase_order_execution` | 200 | 采购订单执行统计表 | - |
| 11 | 供应商采购汇总表 | `/report/view/supplier_purchase_summary` | 200 | 供应商采购汇总表 | - |
| 12 | 物料采购汇总表 | `/report/view/material_purchase_summary` | 200 | 物料采购汇总表 | - |
| 13 | 采购价格分析表 | `/report/view/purchase_price_analysis` | 200 | 采购价格分析表 | - |
| 14 | 采购入库明细报表 | `/report/view/in_detail` | 200 | 入库明细报表 | - |
| 15 | 销售工作台 | `/sales/dashboard` | 200 | 销售工作台 | - |
| 16 | 销售异常工作台 | `/sales/exceptions` | 200 | 销售异常工作台 | - |
| 17 | 新建销售订单 | `/sales/add` | 200 | 新建销售订单 | - |
| 18 | 销售订单列表 | `/sales` | 200 | 销售订单管理 | - |
| 19 | 销售出库选单 | `/sales/outbound_selection` | 200 | 销售出库选单 | - |
| 20 | 销售出库列表 | `/sales/outbound` | 200 | 销售出库列表 | - |
| 21 | 直接销售出库 | `/out_order/add?type=sale` | 200 | 新增销售出库单 | - |
| 22 | 售后出库 | `/after_sale_out/add` | 200 | 新增售后出库单 | - |
| 23 | 客户管理 | `/customer` | 200 | 客户管理 | - |
| 24 | 销售报表 | `/sales/report` | 200 | 销售报表 | - |
| 25 | 销售订单执行 | `/sales/execution_report` | 200 | 销售订单执行 | - |
| 26 | 销售价格分析 | `/sales/price_analysis` | 200 | 销售价格分析 | - |
| 27 | 销售对账 | `/sales/reconciliation` | 200 | 销售对账 | - |
| 28 | 产品入库 | `/in_order/add?type=product` | 200 | 新增入库单 | - |
| 29 | 领料单 | `/out_order/add` | 200 | 新增领料单 | - |
| 30 | 其他入库单 | `/other_in_order/add` | 200 | 新增入库单 | - |
| 31 | 其他出库单 | `/other_out_order/add` | 200 | 新增其他出库单 | - |
| 32 | 库存调拨 | `/transfer` | 200 | 库存调拨 | - |
| 33 | 库存调整 | `/adjustment` | 200 | 库存调整 | - |
| 34 | 库存盘点 | `/check` | 200 | 库存盘点 | - |
| 35 | 入库明细 | `/in_order` | 200 | 入库单 | - |
| 36 | 领料明细 | `/out_order` | 200 | 领料明细 | - |
| 37 | 其他入库明细 | `/other_in_order` | 200 | 其他入库单 | - |
| 38 | 其他出库明细 | `/other_out_order` | 200 | 其他出库明细 | - |
| 39 | BOM管理 | `/bom` | 200 | BOM清单管理 | h1:BOM清单管理 |
| 40 | 工单领料 | `/requisition` | 200 | 工单领料管理 | - |
| 41 | 委外管理 | `/subcontract` | 200 | 委外加工单 | h1:委外加工单 |
| 42 | 数据仪表盘 | `/report/dashboard` | 200 | 数据仪表盘 | - |
| 43 | 智能补货建议 | `/ai/replenishment_smart` | 200 | 智能补货建议 | h1:智能补货建议 |
| 44 | 库存健康度 | `/ai/inventory_health` | 200 | AI库存健康度 | h1:AI库存健康度 |
| 45 | 单据OCR识别 | `/ai/document_ocr` | 200 | 单据OCR识别 | - |
| 46 | 供应商智能评估 | `/ai/supplier_evaluation` | 200 | 供应商智能评估 | - |
| 47 | 智能库位推荐 | `/ai/location_recommendation` | 200 | 智能库位推荐 | - |
| 48 | 需求预测 | `/ai/demand_forecast` | 200 | 需求预测 | - |
| 49 | 库存报表 | `/report/view/inventory` | 200 | 库存报表 | - |
| 50 | 领料明细报表 | `/report/view/out_detail` | 200 | 领料明细报表 | - |
| 51 | 出入库汇总报表 | `/report/view/summary` | 200 | 出入库汇总报表 | - |
| 52 | 盘点报表 | `/report/view/check` | 200 | 盘点报表 | - |
| 53 | 库存台账 | `/report/view/ledger` | 200 | 库存台账 | - |
| 54 | 仓库月报表 | `/report/view/warehouse_monthly` | 200 | 仓库月报表 | - |
| 55 | 工单领料报表 | `/report/view/requisition` | 200 | 工单领料报表 | - |
| 56 | 委外加工报表 | `/report/view/subcontract` | 200 | 委外加工报表 | - |
| 57 | 物料管理 | `/material` | 200 | 物料档案 | - |
| 58 | 合同/工程档案 | `/contract` | 200 | 合同/工程档案 | - |
| 59 | 期初库存 | `/opening_stock` | 200 | 期初库存台账 | - |
| 60 | 物料分类 | `/category` | 200 | 物料分类 | - |
| 61 | 计量单位 | `/unit` | 200 | 计量单位 | - |
| 62 | 仓库档案 | `/warehouse` | 200 | 仓库档案 | h2:仓库档案 |
| 63 | 部门档案 | `/department` | 200 | 部门档案 | h2:部门档案 |
| 64 | 员工管理 | `/employee` | 200 | 员工管理 | - |
| 65 | 系统设置 | `/system_settings` | 200 | 系统参数 | - |
| 66 | AI运维看板 | `/ai/ops` | 200 | AI运维看板 | h1:AI运维看板 |
| 67 | AI质量运营 | `/ai/business_quality` | 200 | AI业务质量运营看板 | h1:AI业务质量运营看板 |
| 68 | AI上线预检 | `/ai/prelaunch` | 200 | AI上线预检 | h1:AI上线预检 |
| 69 | AI七日验收 | `/ai/acceptance` | 200 | AI七日验收 | h1:AI七日验收 |
| 70 | 用户管理 | `/user` | 200 | 用户管理 | - |
| 71 | 审批中心 | `/approval` | 200 | 审批中心 | h2:0<br>h2:0 |
| 72 | 操作审计 | `/operation_audit` | 200 | 操作审计 | - |
| 73 | 微信分享 | `/wechat_share` | 200 | 微信分享 | - |
| 74 | 数据备份 | `/backup` | 200 | 数据备份 | - |

## 2. 菜单与实际页面不符清单（按严重程度排序）

| # | 菜单 | URL | HTTP | 实际 title | h1/h2 | 原因 |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | **采购订单** | `/purchase_order/add` | 200 | 新增采购单 | - | 菜单含业务词 '采购订单' 但实际 title 不含 |
| 3 | **采购入库** | `/in_order/add` | 200 | 新增入库单 | - | 菜单含业务词 '采购入库' 但实际 title 不含 |
| 5 | **采购订单列表** | `/purchase_order?view=list` | 200 | 采购单管理 | - | 菜单含业务词 '采购订单' 但实际 title 不含 |
| 14 | **采购入库明细报表** | `/report/view/in_detail` | 200 | 入库明细报表 | - | 菜单含业务词 '采购入库' 但实际 title 不含 |
| 28 | **产品入库** | `/in_order/add?type=product` | 200 | 新增入库单 | - | 菜单含业务词 '产品入库' 但实际 title 不含 |
| 30 | **其他入库单** | `/other_in_order/add` | 200 | 新增入库单 | - | 菜单含业务词 '其他入库' 但实际 title 不含 |
| 35 | **入库明细** | `/in_order` | 200 | 入库单 | - | 菜单含业务词 '入库明细' 但实际 title 不含 |
| 65 | **系统设置** | `/system_settings` | 200 | 系统参数 | - | 菜单含业务词 '系统设置' 但实际 title 不含 |
| 67 | **AI质量运营** | `/ai/business_quality` | 200 | AI业务质量运营看板 | h1:AI业务质量运营看板 | title 不含 'AI质量' |

报告生成时间：Wed Jul 29 04:30:21 UTC 2026
