# WMS 浏览器端到端测试 + MASTER-AUDIT-FIX 验证报告

**生成时间**：2026-07-28 06:45:51

**测试环境**：http://127.0.0.1:8080 + Chrome 147 + Playwright

**通过率**：67 / 96 = 69.8%

**截图数量**：95 张（保存于 `audit_screenshots/real_e2e/`）

## 检查项明细

| 等级 | 编号 | 名称 | 期望 | 实际 | 结果 | 备注 |
|------|------|------|------|------|------|------|
| INFO | S1-1 | Login page reachable | 200 + title含'登录' | 登录 - 仓库管理系统 | ✅ |  |
| AUTH | S1-2 | Admin login | URL不含/login + 含 admin 元素 | url=http://127.0.0.1:8080/ | ✅ |  |
| INFO | S1-3 | Navigation links present | >0 | 127 | ✅ |  |
| MENU | M-物料 | 访问 /material | 200 + 含 '物料管理' | status=200 title=物料档案 | ✅ |  |
| MENU | M-分类 | 访问 /category | 200 + 含 '分类管理' | status=200 title=物料分类 | ✅ |  |
| MENU | M-单位 | 访问 /unit | 200 + 含 '单位管理' | status=200 title=计量单位 | ✅ |  |
| MENU | M-供应商 | 访问 /supplier | 200 + 含 '供应商管理' | status=200 title=供应商管理 | ✅ |  |
| MENU | M-客户 | 访问 /customer | 200 + 含 '客户管理' | status=200 title=客户管理 | ✅ |  |
| MENU | M-仓库 | 访问 /warehouse | 200 + 含 '仓库管理' | status=200 title=仓库档案 | ✅ |  |
| MENU | M-部门 | 访问 /department | 200 + 含 '部门管理' | status=200 title=部门档案 | ❌ |  |
| MENU | M-员工 | 访问 /employee | 200 + 含 '员工管理' | status=200 title=员工管理 | ✅ |  |
| MENU | M-合同 | 访问 /contract | 200 + 含 '合同管理' | status=200 title=合同/工程档案 | ❌ |  |
| MENU | M-BOM | 访问 /bom | 200 + 含 'BOM管理' | status=200 title=BOM清单管理 | ✅ |  |
| MENU | M-标签 | 访问 /label_template | 200 + 含 '标签模板' | status=200 title=标签模板管理 | ✅ |  |
| MENU | M-期初 | 访问 /opening_stock | 200 + 含 '期初库存' | status=200 title=期初库存单据 | ✅ |  |
| MENU | I-入库 | 访问 /in_order | 200 | status=200 title=入库明细 | ✅ |  |
| MENU | I-出库 | 访问 /out_order | 200 | status=200 title=领料明细 | ✅ |  |
| MENU | I-采购申请 | 访问 /purchase_request | 200 | status=200 title=采购申请管理 | ✅ |  |
| MENU | I-采购订单 | 访问 /purchase_order | 200 | status=200 title=新增采购单 | ✅ |  |
| MENU | I-销售 | 访问 /sales_order | 200 | status=404 title= | ❌ |  |
| MENU | I-调拨 | 访问 /transfer | 200 | status=200 title=库存查询 | ✅ |  |
| MENU | I-盘点 | 访问 /check | 200 | status=200 title=库存盘点 | ✅ |  |
| MENU | I-调整 | 访问 /adjustment | 200 | status=200 title=库存查询 | ✅ |  |
| MENU | I-委外 | 访问 /subcontract | 200 | status=200 title=委外加工单 | ✅ |  |
| MENU | I-售后 | 访问 /after_sale_out | 200 | status=200 title=售后出库管理 | ✅ |  |
| MENU | I-领用 | 访问 /requisition | 200 | status=200 title=工单领料管理 | ✅ |  |
| MENU | R-报表 | 访问 /report | 200 | status=200 title=报表中心 | ✅ |  |
| MENU | R-看板 | 访问 /report_dashboard | 200 | status=404 title= | ❌ |  |
| MENU | R-库存 | 访问 /stock_query | 200 | status=200 title=库存查询 | ✅ |  |
| MENU | R-采购 | 访问 /purchase_report | 200 | status=200 title=采购报表 | ✅ |  |
| MENU | R-销售 | 访问 /sales_report | 200 | status=404 title= | ❌ |  |
| MENU | R-销看 | 访问 /sales_dashboard | 200 | status=404 title= | ❌ |  |
| MENU | R-AI | 访问 /ai_ops_dashboard | 200 | status=404 title= | ❌ |  |
| MENU | S-用户 | 访问 /user | 200 | status=200 title=用户管理 | ✅ |  |
| MENU | S-设置 | 访问 /system_settings | 200 | status=200 title=系统参数 | ✅ |  |
| MENU | S-备份 | 访问 /backup | 200 | status=200 title=数据备份 | ✅ |  |
| MENU | S-审计 | 访问 /operation_audit | 200 | status=200 title=操作审计 | ✅ |  |
| MENU | S-审批 | 访问 /approval | 200 | status=200 title=审批中心 | ✅ |  |
| MENU | S-控制台 | 访问 /admin_console | 200 | status=404 title= | ❌ |  |
| FIX | P0-1a | 空状态 (无 ids) | 显示'未选择物料'占位 | placeholder_present=True | ✅ |  |
| FIX | P0-1b | 有效 ids (1,2) | 占位消失 + 含材料数据 | empty_gone=False has_materials=True | ❌ |  |
| FIX | P1-imp-material | /batch_import?type=material | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-category | /batch_import?type=category | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-unit | /batch_import?type=unit | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-supplier | /batch_import?type=supplier | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-customer | /batch_import?type=customer | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-warehouse | /batch_import?type=warehouse | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-department | /batch_import?type=department | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-employee | /batch_import?type=employee | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-contract | /batch_import?type=contract | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-label_template | /batch_import?type=label_template | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-bom | /batch_import?type=bom | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-opening_stock | /batch_import?type=opening_stock | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-imp-user | /batch_import?type=user | 200 + 含导入页元素 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |  |
| FIX | P1-stub-material-import | /material/import | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/material/import | ❌ |  |
| FIX | P1-stub-material-export | /material/export | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/material/import | ❌ |  |
| FIX | P1-stub-supplier-import | /supplier/import | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/supplier/import | ❌ |  |
| FIX | P1-stub-supplier-export | /supplier/export | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/supplier/import | ❌ |  |
| FIX | P1-stub-customer-import | /customer/import | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/customer/import | ❌ |  |
| FIX | P1-stub-customer-export | /customer/export | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/customer/import | ❌ |  |
| FIX | P1-stub-category-import | /category/import | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/category/import | ❌ |  |
| FIX | P1-stub-category-export | /category/export | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/category/import | ❌ |  |
| FIX | P1-stub-unit-import | /unit/import | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/unit/import | ❌ |  |
| FIX | P1-stub-unit-export | /unit/export | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/unit/import | ❌ |  |
| FIX | P1-stub-warehouse-import | /warehouse/import | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/warehouse/import | ❌ |  |
| FIX | P1-stub-warehouse-export | /warehouse/export | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/warehouse/import | ❌ |  |
| FIX | P1-stub-bom-import | /bom/import | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/bom/import | ❌ |  |
| FIX | P1-stub-bom-export | /bom/export | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/bom/import | ❌ |  |
| FIX | P1-stub-label_template-import | /label_template/import | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/label_template/import | ❌ |  |
| FIX | P1-stub-label_template-export | /label_template/export | 重定向到 /batch_import?type=... | url=http://127.0.0.1:8080/batch_import?type=label_template | ✅ |  |
| FIX | P1-toolbar | 物料列表批量打印入口 | 含'批量打印'按钮/链接 | has=True | ✅ |  |
| TOOL | add-in_order | /in_order 工具栏 | 含'新建入库单'按钮 | has=True | ✅ |  |
| TOOL | add-out_order | /out_order 工具栏 | 含'新建出库单'按钮 | has=True | ✅ |  |
| TOOL | add-purchase_request | /purchase_request 工具栏 | 含'新建采购申请'按钮 | has=True | ✅ |  |
| TOOL | add-sales_order | /sales_order 工具栏 | 含'新建销售订单'按钮 | has=False | ❌ |  |
| TOOL | add-transfer | /transfer 工具栏 | 含'新建调拨单'按钮 | has=True | ✅ |  |
| AUTH | S11-1 | CSRF token in login form | 有 csrf_token 隐藏域 | has=True | ✅ |  |
| AUTH | S11-2 | Wrong password rejected | 留在 /login | url=http://127.0.0.1:8080/login | ✅ |  |
| AUTH | S11-3 | Correct password accepted | 离开 /login | url=http://127.0.0.1:8080/ | ✅ |  |
| PERM | perm-user | Admin→/user | 200 | status=200 | ✅ |  |
| PERM | perm-system_settings | Admin→/system_settings | 200 | status=200 | ✅ |  |
| PERM | perm-backup | Admin→/backup | 200 | status=200 | ✅ |  |
| PERM | perm-operation_audit | Admin→/operation_audit | 200 | status=200 | ✅ |  |
| PERM | perm-approval | Admin→/approval | 200 | status=200 | ✅ |  |
| PERM | perm-admin_console | Admin→/admin_console | 200 | status=404 | ❌ |  |
| PERM | perm-ai_ops_dashboar | Admin→/ai_ops_dashboard | 200 | status=404 | ❌ |  |
| FORM | form-material_add | /material/add 字段 | 含 name='name' | has=True | ✅ |  |
| FORM | form-in_order_add | /in_order/add 字段 | 含 name='warehouse_id' | has=False | ❌ |  |
| FORM | form-out_order_add | /out_order/add 字段 | 含 name='warehouse_id' | has=False | ❌ |  |
| FORM | modal-category | /category 模态字段 | 含 name='name' | has=True | ✅ |  |
| FORM | modal-unit | /unit 模态字段 | 含 name='name' | has=True | ✅ |  |
| FORM | modal-supplier | /supplier 模态字段 | 含 name='name' | has=True | ✅ |  |
| FORM | modal-customer | /customer 模态字段 | 含 name='name' | has=True | ✅ |  |
| FORM | modal-warehouse | /warehouse 模态字段 | 含 name='name' | has=True | ✅ |  |
| FORM | modal-department | /department 模态字段 | 含 name='name' | has=True | ✅ |  |
| FORM | modal-employee | /employee 模态字段 | 含 name='name' | has=True | ✅ |  |

## 失败项

- **M-部门** 访问 /department | expect=200 + 含 '部门管理' | actual=status=200 title=部门档案 | note=
- **M-合同** 访问 /contract | expect=200 + 含 '合同管理' | actual=status=200 title=合同/工程档案 | note=
- **I-销售** 访问 /sales_order | expect=200 | actual=status=404 title= | note=
- **R-看板** 访问 /report_dashboard | expect=200 | actual=status=404 title= | note=
- **R-销售** 访问 /sales_report | expect=200 | actual=status=404 title= | note=
- **R-销看** 访问 /sales_dashboard | expect=200 | actual=status=404 title= | note=
- **R-AI** 访问 /ai_ops_dashboard | expect=200 | actual=status=404 title= | note=
- **S-控制台** 访问 /admin_console | expect=200 | actual=status=404 title= | note=
- **P0-1b** 有效 ids (1,2) | expect=占位消失 + 含材料数据 | actual=empty_gone=False has_materials=True | note=
- **P1-stub-material-import** /material/import | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/material/import | note=
- **P1-stub-material-export** /material/export | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/material/import | note=
- **P1-stub-supplier-import** /supplier/import | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/supplier/import | note=
- **P1-stub-supplier-export** /supplier/export | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/supplier/import | note=
- **P1-stub-customer-import** /customer/import | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/customer/import | note=
- **P1-stub-customer-export** /customer/export | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/customer/import | note=
- **P1-stub-category-import** /category/import | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/category/import | note=
- **P1-stub-category-export** /category/export | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/category/import | note=
- **P1-stub-unit-import** /unit/import | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/unit/import | note=
- **P1-stub-unit-export** /unit/export | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/unit/import | note=
- **P1-stub-warehouse-import** /warehouse/import | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/warehouse/import | note=
- **P1-stub-warehouse-export** /warehouse/export | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/warehouse/import | note=
- **P1-stub-bom-import** /bom/import | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/bom/import | note=
- **P1-stub-bom-export** /bom/export | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/bom/import | note=
- **P1-stub-label_template-import** /label_template/import | expect=重定向到 /batch_import?type=... | actual=url=http://127.0.0.1:8080/label_template/import | note=
- **add-sales_order** /sales_order 工具栏 | expect=含'新建销售订单'按钮 | actual=has=False | note=
- **perm-admin_console** Admin→/admin_console | expect=200 | actual=status=404 | note=
- **perm-ai_ops_dashboar** Admin→/ai_ops_dashboard | expect=200 | actual=status=404 | note=
- **form-in_order_add** /in_order/add 字段 | expect=含 name='warehouse_id' | actual=has=False | note=
- **form-out_order_add** /out_order/add 字段 | expect=含 name='warehouse_id' | actual=has=False | note=

## 截图清单

- `/workspace/audit_screenshots/real_e2e/01_login_page.png`
- `/workspace/audit_screenshots/real_e2e/01_login_filled.png`
- `/workspace/audit_screenshots/real_e2e/02_after_login.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_物料.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_分类.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_单位.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_供应商.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_客户.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_仓库.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_部门.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_员工.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_合同.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_BOM.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_标签.png`
- `/workspace/audit_screenshots/real_e2e/menu_M_期初.png`
- `/workspace/audit_screenshots/real_e2e/io_I_入库.png`
- `/workspace/audit_screenshots/real_e2e/io_I_出库.png`
- `/workspace/audit_screenshots/real_e2e/io_I_采购申请.png`
- `/workspace/audit_screenshots/real_e2e/io_I_采购订单.png`
- `/workspace/audit_screenshots/real_e2e/io_I_销售.png`
- `/workspace/audit_screenshots/real_e2e/io_I_调拨.png`
- `/workspace/audit_screenshots/real_e2e/io_I_盘点.png`
- `/workspace/audit_screenshots/real_e2e/io_I_调整.png`
- `/workspace/audit_screenshots/real_e2e/io_I_委外.png`
- `/workspace/audit_screenshots/real_e2e/io_I_售后.png`
- `/workspace/audit_screenshots/real_e2e/io_I_领用.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_报表.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_看板.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_库存.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_采购.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_销售.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_销看.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_AI.png`
- `/workspace/audit_screenshots/real_e2e/sys_S_用户.png`
- `/workspace/audit_screenshots/real_e2e/sys_S_设置.png`
- `/workspace/audit_screenshots/real_e2e/sys_S_备份.png`
- `/workspace/audit_screenshots/real_e2e/sys_S_审计.png`
- `/workspace/audit_screenshots/real_e2e/sys_S_审批.png`
- `/workspace/audit_screenshots/real_e2e/sys_S_控制台.png`
- `/workspace/audit_screenshots/real_e2e/fix_p0_1a_empty.png`
- `/workspace/audit_screenshots/real_e2e/fix_p0_1b_with_ids.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_material.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_category.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_unit.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_supplier.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_customer.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_warehouse.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_department.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_employee.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_contract.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_label_template.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_bom.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_opening_stock.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_imp_user.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_material_import.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_material_export.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_supplier_import.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_supplier_export.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_customer_import.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_customer_export.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_category_import.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_category_export.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_unit_import.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_unit_export.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_warehouse_import.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_warehouse_export.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_bom_import.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_bom_export.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_label_template_import.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_stub_label_template_export.png`
- `/workspace/audit_screenshots/real_e2e/fix_p1_toolbar_material.png`
- `/workspace/audit_screenshots/real_e2e/tool_in_order.png`
- `/workspace/audit_screenshots/real_e2e/tool_out_order.png`
- `/workspace/audit_screenshots/real_e2e/tool_purchase_request.png`
- `/workspace/audit_screenshots/real_e2e/tool_sales_order.png`
- `/workspace/audit_screenshots/real_e2e/tool_transfer.png`
- `/workspace/audit_screenshots/real_e2e/fix_login_wrong.png`
- `/workspace/audit_screenshots/real_e2e/fix_login_ok.png`
- `/workspace/audit_screenshots/real_e2e/perm_user.png`
- `/workspace/audit_screenshots/real_e2e/perm_system_settings.png`
- `/workspace/audit_screenshots/real_e2e/perm_backup.png`
- `/workspace/audit_screenshots/real_e2e/perm_operation_audit.png`
- `/workspace/audit_screenshots/real_e2e/perm_approval.png`
- `/workspace/audit_screenshots/real_e2e/perm_admin_console.png`
- `/workspace/audit_screenshots/real_e2e/perm_ai_ops_dashboar.png`
- `/workspace/audit_screenshots/real_e2e/form_material_add.png`
- `/workspace/audit_screenshots/real_e2e/form_in_order_add.png`
- `/workspace/audit_screenshots/real_e2e/form_out_order_add.png`
- `/workspace/audit_screenshots/real_e2e/modal_category.png`
- `/workspace/audit_screenshots/real_e2e/modal_unit.png`
- `/workspace/audit_screenshots/real_e2e/modal_supplier.png`
- `/workspace/audit_screenshots/real_e2e/modal_customer.png`
- `/workspace/audit_screenshots/real_e2e/modal_warehouse.png`
- `/workspace/audit_screenshots/real_e2e/modal_department.png`
- `/workspace/audit_screenshots/real_e2e/modal_employee.png`
