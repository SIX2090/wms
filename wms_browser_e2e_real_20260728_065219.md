# WMS 浏览器端到端测试 + MASTER-AUDIT-FIX 验证报告

**生成时间**：2026-07-28 06:53:01

**测试环境**：http://127.0.0.1:8080 + Chrome 147 + Playwright

**通过率**：99 / 102 = 97.1%

**截图数量**：80 张（保存于 `audit_screenshots/real_e2e/`）

## P0/P1 修复验证汇总

- 修复检查总数：46
- 通过：46
- 失败：0

## 检查项明细

| 等级 | 编号 | 名称 | 期望 | 实际 | 结果 |
|------|------|------|------|------|------|
| INFO | S1-1 | Login page reachable | 200 + title含'登录' | status=200 title=登录 - 仓库管理系统 | ✅ |
| AUTH | S1-2 | Admin login (no forced change) | URL 不含 /login /change_password | url=http://127.0.0.1:8080/ | ✅ |
| INFO | S1-3 | Navigation links present | >0 | 127 | ✅ |
| MENU | M-物料 | 访问 /material | 200 + 含 '物料' | status=200 title=物料档案 | ✅ |
| MENU | M-分类 | 访问 /category | 200 + 含 '分类' | status=200 title=物料分类 | ✅ |
| MENU | M-单位 | 访问 /unit | 200 + 含 '单位' | status=200 title=计量单位 | ✅ |
| MENU | M-供应商 | 访问 /supplier | 200 + 含 '供应商' | status=200 title=供应商管理 | ✅ |
| MENU | M-客户 | 访问 /customer | 200 + 含 '客户' | status=200 title=客户管理 | ✅ |
| MENU | M-仓库 | 访问 /warehouse | 200 + 含 '仓库' | status=200 title=仓库档案 | ✅ |
| MENU | M-部门 | 访问 /department | 200 + 含 '部门' | status=200 title=部门档案 | ✅ |
| MENU | M-员工 | 访问 /employee | 200 + 含 '员工' | status=200 title=员工管理 | ✅ |
| MENU | M-合同 | 访问 /contract | 200 + 含 '合同' | status=200 title=合同/工程档案 | ✅ |
| MENU | M-BOM | 访问 /bom | 200 + 含 'BOM' | status=200 title=BOM清单管理 | ✅ |
| MENU | M-标签 | 访问 /label_template | 200 + 含 '标签' | status=200 title=标签模板管理 | ✅ |
| MENU | M-期初 | 访问 /opening_stock | 200 + 含 '期初' | status=200 title=期初库存单据 | ✅ |
| MENU | I-入库 | 访问 /in_order | 200 | status=200 title=入库明细 | ✅ |
| MENU | I-出库 | 访问 /out_order | 200 | status=200 title=领料明细 | ✅ |
| MENU | I-采购申请 | 访问 /purchase_request | 200 | status=200 title=采购申请管理 | ✅ |
| MENU | I-采购订单 | 访问 /purchase_order | 200 | status=200 title=新增采购单 | ✅ |
| MENU | I-调拨 | 访问 /transfer | 200 | status=200 title=库存查询 | ✅ |
| MENU | I-盘点 | 访问 /check | 200 | status=200 title=库存盘点 | ✅ |
| MENU | I-调整 | 访问 /adjustment | 200 | status=200 title=库存查询 | ✅ |
| MENU | I-委外 | 访问 /subcontract | 200 | status=200 title=委外加工单 | ✅ |
| MENU | I-售后 | 访问 /after_sale_out | 200 | status=200 title=售后出库管理 | ✅ |
| MENU | I-领用 | 访问 /requisition | 200 | status=200 title=工单领料管理 | ✅ |
| MENU | I-销售 | 访问 /sales | 200 | status=200 title=销售订单管理 | ✅ |
| MENU | R-报表 | 访问 /report | 200 | status=200 title=报表中心 | ✅ |
| MENU | R-库存 | 访问 /stock_query | 200 | status=200 title=库存查询 | ✅ |
| MENU | R-采购 | 访问 /purchase_report | 200 | status=200 title=采购报表 | ✅ |
| MENU | S-用户 | 访问 /user | 200 | status=200 title=用户管理 | ✅ |
| MENU | S-设置 | 访问 /system_settings | 200 | status=200 title=系统参数 | ✅ |
| MENU | S-备份 | 访问 /backup | 200 | status=200 title=数据备份 | ✅ |
| MENU | S-审计 | 访问 /operation_audit | 200 | status=200 title=操作审计 | ✅ |
| MENU | S-审批 | 访问 /approval | 200 | status=200 title=审批中心 | ✅ |
| FIX | P0-1a | 空状态 (无 ids) | 显示'未选择物料'占位 | placeholder_present=True | ✅ |
| FIX | P0-1b | 有效 ids (1,2) | 占位消失 + 含材料数据 | empty_gone=True has_materials=True has_count=True | ✅ |
| FIX | P0-1c | 无效 ids (999,1000) | 回退空态 | empty_placeholder=True | ✅ |
| FIX | P1-imp-material | /batch_import?type=material | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-category | /batch_import?type=category | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-unit | /batch_import?type=unit | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-supplier | /batch_import?type=supplier | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-customer | /batch_import?type=customer | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-warehouse | /batch_import?type=warehouse | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-department | /batch_import?type=department | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-employee | /batch_import?type=employee | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-contract | /batch_import?type=contract | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-label_template | /batch_import?type=label_template | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-bom | /batch_import?type=bom | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-opening_stock | /batch_import?type=opening_stock | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-imp-user | /batch_import?type=user | 200 + 模块高亮 | status=200 has_import=True highlight=True | ✅ |
| FIX | P1-stub-user-export | /user/export | 重定向到 /batch_import?type=user | status=200 final_url=http://127.0.0.1:8080/batch_import?type=user | ✅ |
| FIX | P1-stub-user-import | /user/import | POST-only (GET 405) | status=405 | ✅ |
| FIX | P1-stub-system_settings-export | /system_settings/export | 重定向到 /batch_import?type=system_settings | status=200 final_url=//127.0.0.1:8080/batch_import?type=system_settings | ✅ |
| FIX | P1-stub-system_settings-import | /system_settings/import | POST-only (GET 405) | status=405 | ✅ |
| FIX | P1-stub-label_template-export | /label_template/export | 重定向到 /batch_import?type=label_template | status=200 final_url=://127.0.0.1:8080/batch_import?type=label_template | ✅ |
| FIX | P1-stub-label_template-import | /label_template/import | POST-only (GET 405) | status=405 | ✅ |
| FIX | P1-stub-opening_stock-export | /opening_stock/export | 重定向到 /batch_import?type=opening_stock | status=200 final_url=p://127.0.0.1:8080/batch_import?type=opening_stock | ✅ |
| FIX | P1-stub-opening_stock-import | /opening_stock/import | POST-only (GET 405) | status=405 | ✅ |
| FIX | P1-material-import-post | /material/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-material-export-get | /material/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-supplier-import-post | /supplier/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-supplier-export-get | /supplier/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-customer-import-post | /customer/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-customer-export-get | /customer/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-category-import-post | /category/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-category-export-get | /category/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-unit-import-post | /unit/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-unit-export-get | /unit/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-warehouse-import-post | /warehouse/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-warehouse-export-get | /warehouse/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-department-import-post | /department/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-department-export-get | /department/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-employee-import-post | /employee/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-employee-export-get | /employee/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-contract-import-post | /contract/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-contract-export-get | /contract/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-bom-import-post | /bom/import GET | 405 (POST-only) | status=405 | ✅ |
| FIX | P1-bom-export-get | /bom/export GET | 200 或 0 (file download) | status=0 | ✅ |
| FIX | P1-toolbar-material | 物料列表批量打印入口 | 含'批量打印'按钮/链接 | has=True | ✅ |
| TOOL | add-in_order | /in_order 工具栏 | 含'新增'按钮 | has=True | ✅ |
| TOOL | add-out_order | /out_order 工具栏 | 含'新增'按钮 | has=True | ✅ |
| TOOL | add-purchase_request | /purchase_request 工具栏 | 含'新建'按钮 | has=True | ✅ |
| TOOL | add-transfer | /transfer 工具栏 | 含'新增调拨'按钮 | has=False | ❌ |
| FORM | form-material_add | /material/add 字段 | 含 name='name' | has=True | ✅ |
| FORM | form-in_order_add | /in_order/add 字段 | 含 name='warehouse_id' | has=False | ❌ |
| FORM | form-out_order_add | /out_order/add 字段 | 含 name='warehouse_id' | has=False | ❌ |
| FORM | modal-category | /category 模态字段 | 含 name='name' | has=True | ✅ |
| FORM | modal-unit | /unit 模态字段 | 含 name='name' | has=True | ✅ |
| FORM | modal-supplier | /supplier 模态字段 | 含 name='name' | has=True | ✅ |
| FORM | modal-customer | /customer 模态字段 | 含 name='name' | has=True | ✅ |
| FORM | modal-warehouse | /warehouse 模态字段 | 含 name='name' | has=True | ✅ |
| FORM | modal-department | /department 模态字段 | 含 name='name' | has=True | ✅ |
| FORM | modal-employee | /employee 模态字段 | 含 name='name' | has=True | ✅ |
| FIX | P0-1b-full | P0-1b 完整 ids (1-5) | 占位消失 + 含 5 个材料 + 显示数量 | empty_gone=True has_data=True has_count=True match=共 5 个标签 | ✅ |
| AUTH | S11-1 | CSRF token in login form | 有 csrf_token 隐藏域 | has=True | ✅ |
| AUTH | S11-2 | Wrong password rejected | 留在 /login | url=http://127.0.0.1:8080/login | ✅ |
| AUTH | S11-3 | Correct password accepted | 离开 /login | url=http://127.0.0.1:8080/ | ✅ |
| PERM | perm-user | Admin→/user | 200 | status=200 | ✅ |
| PERM | perm-system_settings | Admin→/system_settings | 200 | status=200 | ✅ |
| PERM | perm-backup | Admin→/backup | 200 | status=200 | ✅ |
| PERM | perm-operation_audit | Admin→/operation_audit | 200 | status=200 | ✅ |
| PERM | perm-approval | Admin→/approval | 200 | status=200 | ✅ |

## 失败项

- **add-transfer** /transfer 工具栏 | expect=含'新增调拨'按钮 | actual=has=False
- **form-in_order_add** /in_order/add 字段 | expect=含 name='warehouse_id' | actual=has=False
- **form-out_order_add** /out_order/add 字段 | expect=含 name='warehouse_id' | actual=has=False

## 截图清单（前 30）

- `/workspace/audit_screenshots/real_e2e/01_login_page.png`
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
- `/workspace/audit_screenshots/real_e2e/io_I_调拨.png`
- `/workspace/audit_screenshots/real_e2e/io_I_盘点.png`
- `/workspace/audit_screenshots/real_e2e/io_I_调整.png`
- `/workspace/audit_screenshots/real_e2e/io_I_委外.png`
- `/workspace/audit_screenshots/real_e2e/io_I_售后.png`
- `/workspace/audit_screenshots/real_e2e/io_I_领用.png`
- `/workspace/audit_screenshots/real_e2e/io_I_销售.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_报表.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_库存.png`
- `/workspace/audit_screenshots/real_e2e/rpt_R_采购.png`
- `/workspace/audit_screenshots/real_e2e/sys_S_用户.png`
- `/workspace/audit_screenshots/real_e2e/sys_S_设置.png`
- ...（其余 50 张略）
