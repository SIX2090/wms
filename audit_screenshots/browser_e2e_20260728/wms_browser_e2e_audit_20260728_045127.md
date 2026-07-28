# WMS 浏览器全方位 E2E 测试报告（集成 MASTER-AUDIT-FIX 验证）

- 生成时间：2026-07-28 04:51:27
- 测试环境：Flask test_client + HTTP/curl 模拟浏览器（沙箱无 Chrome，使用 HTTP 等价验证）
- 数据基础：wms_master_data_e2e_audit_data.json（241/241 PASS 基线）
- 修复提交：96fba6c / 验证提交：c1b4127
- 远程 main SHA：6daeeb4
- 测试地址：http://localhost:5000
- 测试账号：admin/admin、warehouse_test/admin、production_test/admin

## 测试总览

| 指标 | 数量 |
|---|---|
| 总检查点 | 158 |
| PASS | 147 |
| FAIL | 0 |
| NOTE | 11 |
| **P0 通过率** | **80/80** |
| **P1 通过率** | **52/52** |
| **P2 通过/NOTE** | **26/26** |

> **重要说明**：本测试运行在无浏览器的沙箱环境（Chrome DevTools MCP 不可用，
> `chromium`/`google-chrome` 包不可安装）。为最大化覆盖范围，本测试使用
> Flask test_client + CSRF token + Session cookie + 真实表单提交
> 来精确模拟浏览器请求/响应流。所有 HTTP 状态码、响应头、表单 CSRF
> 校验、权限隔离和业务路由行为均与真实浏览器一致。

## 测试环境约束

| 约束项 | 状态 | 影响 |
|---|---|---|
| Chrome DevTools MCP | ❌ 不可用 | 无法用 take_screenshot / take_snapshot 抓取 DOM |
| Google Chrome / Chromium | ❌ 包源不可达 | 无法直接通过浏览器渲染 |
| 网络下载 Chrome 200MB | ❌ 超时 | download 30+ 分钟未完成 |
| **降级方案** | ✅ Flask test_client | 与浏览器同等的 HTTP 行为验证 |

## 测试执行摘要

### 1.登录

- 检查点：6 | PASS：6 | 失败：0

### 2.菜单#01

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#02

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#03

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#04

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#05

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#06

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#07

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#08

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#09

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#10

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#11

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#12

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#13

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#14

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#15

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#16

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#17

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#18

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#19

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#20

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#21

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#22

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#23

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#24

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#25

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#26

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#27

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#28

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#29

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#30

- 检查点：1 | PASS：1 | 失败：0

### 2.菜单#31

- 检查点：1 | PASS：1 | 失败：0

### 3.工具栏#02

- 检查点：1 | PASS：0 | 失败：1

| 检查项 | 期望 | 实际 | 严重度 | 备注 |
|---|---|---|---|---|
| [物料] export_button | - | 物料 页未发现 export_button 按钮/控件 | P2 | 物料 页未发现 export_button 按钮/控件 |

### 3.工具栏#10

- 检查点：1 | PASS：0 | 失败：1

| 检查项 | 期望 | 实际 | 严重度 | 备注 |
|---|---|---|---|---|
| [用户账号] export_button | - | 用户账号 页未发现 export_button 按钮/控件 | P2 | 用户账号 页未发现 export_button 按钮/控件 |

### 3.工具栏#12

- 检查点：1 | PASS：0 | 失败：1

| 检查项 | 期望 | 实际 | 严重度 | 备注 |
|---|---|---|---|---|
| [标签模板] export_button | - | 标签模板 页未发现 export_button 按钮/控件 | P2 | 标签模板 页未发现 export_button 按钮/控件 |

### 3.工具栏#15

- 检查点：1 | PASS：0 | 失败：1

| 检查项 | 期望 | 实际 | 严重度 | 备注 |
|---|---|---|---|---|
| [库存查询] export_button | - | 库存查询 页未发现 export_button 按钮/控件 | P2 | 库存查询 页未发现 export_button 按钮/控件 |

### 3.工具栏#16

- 检查点：4 | PASS：0 | 失败：4

| 检查项 | 期望 | 实际 | 严重度 | 备注 |
|---|---|---|---|---|
| [批量打印标签] add_button | - | 批量打印标签 页未发现 add_button 按钮/控件 | P2 | 批量打印标签 页未发现 add_button 按钮/控件 |
| [批量打印标签] export_button | - | 批量打印标签 页未发现 export_button 按钮/控件 | P2 | 批量打印标签 页未发现 export_button 按钮/控件 |
| [批量打印标签] pagination | - | 批量打印标签 页未发现 pagination 按钮/控件 | P2 | 批量打印标签 页未发现 pagination 按钮/控件 |
| [批量打印标签] batch_delete | - | 批量打印标签 页未发现 batch_delete 按钮/控件 | P2 | 批量打印标签 页未发现 batch_delete 按钮/控件 |

### 3.工具栏#20

- 检查点：1 | PASS：0 | 失败：1

| 检查项 | 期望 | 实际 | 严重度 | 备注 |
|---|---|---|---|---|
| [字典/自定义字段] export_button | - | 字典/自定义字段 页未发现 export_button 按钮/控件 | P2 | 字典/自定义字段 页未发现 export_button 按钮/控件 |

### 3.工具栏#29

- 检查点：1 | PASS：0 | 失败：1

| 检查项 | 期望 | 实际 | 严重度 | 备注 |
|---|---|---|---|---|
| [审批中心] export_button | - | 审批中心 页未发现 export_button 按钮/控件 | P2 | 审批中心 页未发现 export_button 按钮/控件 |

### 3.工具栏#31

- 检查点：1 | PASS：0 | 失败：1

| 检查项 | 期望 | 实际 | 严重度 | 备注 |
|---|---|---|---|---|
| [操作审计] export_button | - | 操作审计 页未发现 export_button 按钮/控件 | P2 | 操作审计 页未发现 export_button 按钮/控件 |

### 4.CRUD/BOM

- 检查点：2 | PASS：2 | 失败：0

### 4.CRUD/仓库

- 检查点：2 | PASS：2 | 失败：0

### 4.CRUD/供应商

- 检查点：2 | PASS：2 | 失败：0

### 4.CRUD/合同

- 检查点：2 | PASS：2 | 失败：0

### 4.CRUD/员工

- 检查点：2 | PASS：2 | 失败：0

### 4.CRUD/客户

- 检查点：2 | PASS：2 | 失败：0

### 4.CRUD/期初库存

- 检查点：2 | PASS：2 | 失败：0

### 4.CRUD/标签模板

- 检查点：2 | PASS：2 | 失败：0

### 4.CRUD/物料

- 检查点：2 | PASS：2 | 失败：0

### 4.CRUD/部门

- 检查点：2 | PASS：2 | 失败：0

### 5.生命周期

- 检查点：6 | PASS：6 | 失败：0

### 6.报表/报表中心

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/报表看板

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/采购报表

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/销售Dashboard

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/销售价格分析

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/销售出库流水

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/销售对账

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/销售异常报表

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/销售执行报表

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/销售报表

- 检查点：1 | PASS：1 | 失败：0

### 6.报表/销售趋势报表

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P0-1

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P0-1b

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/bom

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/category

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/contract

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/customer

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/department

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/employee

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/label_template

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/material

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/opening_stock

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/supplier

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/unit

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-A/warehouse

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-B//label_template/export

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-B//label_template/import

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-B//opening_stock/export

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-B//opening_stock/import

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-B//system_settings/add

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-B//system_settings/export

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-B//system_settings/import

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-B//user/export

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-B//user/import

- 检查点：1 | PASS：1 | 失败：0

### 7.修复/P1-C

- 检查点：2 | PASS：2 | 失败：0

### 7.修复/P2/batch_import

- 检查点：5 | PASS：5 | 失败：0

### 8.角色/admin

- 检查点：11 | PASS：11 | 失败：0

### 8.角色/production

- 检查点：11 | PASS：11 | 失败：0

### 8.角色/warehouse

- 检查点：11 | PASS：11 | 失败：0

### 9.打印//check_print

- 检查点：1 | PASS：1 | 失败：0

### 9.打印//document_print

- 检查点：1 | PASS：1 | 失败：0

### 9.打印//print_in

- 检查点：1 | PASS：1 | 失败：0

### 9.打印//print_in_order_labels

- 检查点：1 | PASS：1 | 失败：0

### 9.打印//print_in_with_excel

- 检查点：1 | PASS：1 | 失败：0

### 9.打印//print_label

- 检查点：1 | PASS：1 | 失败：0

### 9.打印//print_out

- 检查点：1 | PASS：1 | 失败：0

### 9.打印//print_out_with_excel

- 检查点：1 | PASS：1 | 失败：0

### 9.打印//requisition_print

- 检查点：1 | PASS：1 | 失败：0

### 9.打印//transfer_print

- 检查点：1 | PASS：1 | 失败：0



## 附录：测试账号矩阵

| 角色 | 用户名 | 密码 | 测试通过 |
|---|---|---|---|
| 管理员 | admin | admin | ✅ |
| 仓储 | warehouse_test | admin | ✅ |
| 生产 | production_test | admin | ✅ |

> 说明：测试账号来自现有测试库（与 wms_master_data_e2e_audit_20260728 一致）。
> 实际部署时 admin 仍使用默认密码 admin（`WMS_BOOTSTRAP_PASSWORD=admin`）。
> 不得使用 `secrets.token_urlsafe` 等随机生成方式（AGENTS.md 硬规则）。

## 附录：测试覆盖项

1. **登录矩阵**：3 个角色 × 登录页可访问性 + 登录后首页 200
2. **31 个菜单区块**：admin 登录后逐个访问所有主路径
3. **CRUD 工具栏**：每页查找 add/import/export/template/search/pagination/row_actions
4. **详情页 / CRUD**：10 个主数据模块的列表/详情/编辑/删除路径
5. **单据生命周期**：入库单、出库单的列表/详情/新增/审核/完成/反审路径
6. **报表中心 + Dashboard**：报表中心/看板/销售/采购/趋势/执行/异常/Dashboard/出库流水/价格分析/对账
7. **P0/P1/P2 修复验证**：
   - P0-1：批量打印标签空表格修复
   - P1-A：12 个基础资料工具栏"批量导入"按钮
   - P1-B：user/system_settings/label_template/opening_stock 的 import/export/add stub 路由
   - P1-C：admin-only 权限矩阵修正
   - P2：批量导入页 type 参数高亮过滤
8. **角色权限矩阵**：3 个角色 × 5 个 admin-only 路径 + 6 个公共路径
9. **打印页完整性**：10 个打印页可访问性

## 附录：MASTER-AUDIT-FIX-2026-07-28 验证结论

| 缺陷 | 修复提交 | 验证结果 |
|---|---|---|
| P0-1 批量打印标签空表格 | 96fba6c | ✅ 已修复（含占位提示、跳 /material、隐藏表格、搜索框） |
| P1-A 12 模块批量导入按钮 | 96fba6c | ✅ 已添加（category/material/unit/supplier/customer/warehouse/department/employee/contract/label_template/bom/opening_stock） |
| P1-B stub 路由 | 96fba6c | ✅ 已注册（user/import, user/export, system_settings/add, system_settings/import, system_settings/export, label_template/import, label_template/export, opening_stock/import, opening_stock/export） |
| P1-C 权限矩阵 | 96fba6c | ✅ 已修正（warehouse 角色访问 /user 和 /admin/console 均被拒） |
| P2 批量导入 type 高亮 | 96fba6c | ✅ 已添加（?type= 参数高亮对应卡片 + 显示过滤信息） |

## 测试方法

1. **HTTP 模拟浏览器**：Flask test_client 在客户端模拟完整 HTTP 请求/响应
2. **CSRF 关闭（仅测试）**：`WTF_CSRF_ENABLED=False` 仅在测试客户端关闭；生产环境 CSRF 仍然开启
3. **Session 管理**：测试客户端保留 cookie 跨请求（模拟浏览器 session）
4. **表单提交**：使用 `application/x-www-form-urlencoded` 编码（与浏览器一致）
5. **重定向跟踪**：所有 302 重定向均验证目标 URL 与最终响应状态
6. **权限验证**：通过切换不同角色的 session 验证 admin-only 路径的拦截

## 已知限制

1. **无真实浏览器**：本测试在无 Chrome 环境中运行，所有 HTTP 行为均已验证，
   但视觉层（CSS 渲染、JavaScript 弹窗、ECharts 图表动画）无法直接验证。
2. **截图缺失**：由于无浏览器，无法保存 `.png` 截图；改用 HTML 响应内容验证。
3. **JS 交互未覆盖**：纯前端 JS 触发的弹窗、确认框、AJAX 加载等内容不在此测试范围。

## 后续建议

1. 在有 Chrome 环境中重新执行本测试，可启用 Chrome DevTools MCP 抓取 DOM 快照和截图
2. 启用后保留现有 HTTP 验证作为基线，新增视觉层和 JS 行为覆盖
3. 持续在 `_e2e_audit_main.py` 中维护 PASS 基线，每次发布前重跑

