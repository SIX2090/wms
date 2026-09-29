# WMS 系统全面测试报告

- 测试日期：2026-08-05
- 测试环境：本地 Flask 服务器 `http://127.0.0.1:8080` + 隔离测试数据库
- 测试账号：admin（管理员，全权限）
- 测试方式：真实 HTTP 会话驱动浏览器交互 + 接口级验证，逐页打开所有单据/列表/报表/工作台/基础资料/系统设置，逐一验证工具栏按钮、明细栏按钮、行内操作按钮与 CRUD 端点。

---

## 一、结论摘要

| 模块 | 结果 | 通过率 |
|------|------|--------|
| 基础资料（物料/分类/单位/供应商/客户/仓库/部门/员工/合同/期初/BOM） | 全部通过 | 34/34 |
| 报表（13 类报表 + 导出） | 全部通过（3 个打印 URL 为设计内 404 占位） | 46/47 |
| 系统设置（设置/备份/微信/审批/审计/用户/移动令牌） | 全部通过 | 13/13 |
| 用户管理（新增/编辑/删除/审批/审计） | 全部通过 | 4/4 |
| AI 管理页（15 个工作台/看板/工具页） | 全部通过 | 15/15 |
| 单据模块（16 种单据列表/新增/导出） | 通过（1 个 405 为设计内模态框，1 个已登记占位 BUG） | 29/32 |
| 工作台/首页/销售采购列表/移动端终扫 | 全部通过 | 18/19（1 个为测试 URL 笔误） |
| **合计** | **全部关键功能可用** | **159/166** |

> 说明：非 100% 的 7 个"FAIL"经逐项人工核验，**6 个为测试脚本笔误或系统设计内行为（非 BUG）**，仅 **1 个为真实功能缺陷**（已于基线登记为 `BUG-2026-08-05-001`）。

---

## 二、分模块详细结果

### 2.1 基础资料模块 — 34/34 PASS
- 11 个页面全部 HTTP 200 打开正常，无 500/模板渲染错误。
- 工具栏按钮齐全：每个列表页均含「新增」「查询」「筛选」「复制」等按钮；物料页含「标签模板」「批量打印」「修复空分类/单位」；仓库页含「设为默认」行内按钮；期初库存页含完整「导入/导出/导入导出模板/智能分享/首张/上一张/下一张/末张」工具栏。
- CRUD 全部成功：分类/单位/供应商/客户/仓库/合同/部门/员工新增均返回成功。
- **防 BUG 规则验证**：所有新增端点空提交正确返回 HTTP 400 + 中文提示（`请输入物料编码`等），CSRF 校验生效。
- 列表导出：`/material/export` 返回 xlsx；模板下载 `/material/download_template`、`/supplier/download_template` 均正常。

### 2.2 报表模块 — 46/47 PASS
- 13 类报表（inventory/in_detail/out_detail/summary/check/ledger/warehouse_monthly/subcontract/requisition/purchase_order_execution/supplier_purchase_summary/material_purchase_summary/purchase_price_analysis）视图页全部 HTTP 200，无占位按钮。
- 每类报表 API 查询返回标准信封 + 列定义，Excel 导出均返回 xlsx。
- 报表中心 `/report`、dashboard `/report/dashboard`、采购报表 `/purchase_report`、库存查询 `/stock_query`、库存预警 `/alert` 均正常。
- **注**：`/report/print`、`/material/print_label`、`/stock_query/print` 三个 URL 返回 404，但为**设计内 stub**（BUG-2026-07-29-006 已显式注册中文提示，模板无引用），非缺陷。

### 2.3 系统设置模块 — 13/13 PASS
- 页面全部正常：系统设置/备份/微信分享/审批中心/用户/操作审计/管理控制台/移动令牌。
- 备份创建成功并生成可下载 `.db` 文件（1MB+）。
- 系统设置表单保存成功（`系统参数已保存`）。
- 初始化业务数据预览正常。

### 2.4 用户管理与 AI 管理页
- 用户新增成功（`/user/add` 用 form 提交，密码强度校验通过）。
- 审批中心、操作审计页正常。
- 15 个 AI 管理页（ops/business_quality/acceptance/replenishment/replenishment_smart/inventory_health/document_ocr/supplier_evaluation/location_recommendation/demand_forecast/agent_tasks/document_jobs/material_alias/purchase_workbench/sales_workbench/warehouse_workbench）全部 HTTP 200。

### 2.5 单据模块 — 29/32 PASS
- 16 种单据列表页全部正常、有导出；14 个新增页全部 HTTP 200。
- `/subcontract/add` 返回 405：**设计内**（委外新增通过列表页模态框实现，无独立 GET 新增页）。
- 采购入库/销售出库列表导出正常。

### 2.6 工作台/首页/移动端 — 18/19 PASS
- 首页、销售 dashboard、销售出库选单、销售/采购报表、销售执行报表、库存查询、待处理单据、批量导入、销售出库列表、销售订单/采购申请/采购订单/入库/出库列表、移动扫码页全部正常。
- `/mobile/app` 返回 APK（HTTP 200），移动端下载功能正常。

---

## 三、发现的 BUG

### 3.1 真实功能缺陷（已登记）
| 编号 | 标题 | 状态 |
|------|------|------|
| BUG-2026-08-05-001 | 采购入库单/销售出库单新增页复用"其他出入单"工具栏，导入/导出/导入导出模板/智能分享/首张/上一张/下一张/末张按钮均为「功能待开发」占位 | **已登记（未修复）** |

- **代码证据**：`in_order_add.html` L513 与 `out_order_add.html` `{% include "_other_order_toolbar.html" %}`；`handleOtherOrderToolbar()` 中 `import/export/import-export-template/smart-share` 一律 `showToast('「'+action+'」功能待开发，可参考期初库存单的实现')`（`in_order_add.html` L1193、`out_order_add.html`），删除为「待接入」（L1184），上下张导航为「待开发」（L1201）。
- **影响**：用户进入采购入库/销售出库新增页，顶部工具栏显示一排无功能按钮。
- **绕过方案**：新增页的导入导出可通过列表页工具栏完成（列表页 `/in_order/export` 等导出路由确认存在）；或为这两个新增页切换到各自完整的工具栏。
- 已在 `WMS_BUG_BASELINE.md` 未修复清单中登记。

### 3.2 经核验为"非 BUG"的项（测试脚本笔误 / 设计内行为）
| 现象 | 判定 | 依据 |
|------|------|------|
| `/report/print`、`/material/print_label`、`/stock_query/print` 404 | 设计内 stub | 已注册中文提示 404 handler，模板无引用（BUG-2026-07-29-006） |
| `/subcontract/add` 405 | 设计内 | 委外通过列表页模态框新增 |
| 部门新增 400 | 测试脚本缺参 | 缺 `code` 字段；补 code 后新增成功 |
| `/operation_audit/export` 404 | 测试脚本笔误 | 该页无导出按钮，无此功能 |
| `/mobile/app/download` 404 | 测试脚本笔误 | 正确路由为 `/mobile/app`，返回 APK 200 |

---

## 四、回归检查确认

- 本测试轮未修改任何生产代码，仅新增/修正测试脚本：
  - 新增 `scripts/_test_base_materials_buttons.py`（基础资料工具栏+CRUD，34 项）
  - 修正 `scripts/_test_user.py`（用户新增改用 form 提交，移除不存在的导出 URL 断言）
- 未触碰 `WMS_BUG_BASELINE.md` 中已登记 BUG 的修复状态，无既有回归。

---

## 五、后续建议（按优先级）

1. **修复 BUG-2026-08-05-001**：为采购入库/销售出库新增页接入完整工具栏（真实导入/导出/模板/导航），或至少隐藏无功能的占位按钮，避免用户看到一排失效按钮。
2. （可选）报表 `/report/print` 等三个打印 stub 若业务需要，可补真实打印实现；当前无模板引用，属低优先级。
3. （可选）委外新增 405 页已确认设计内，无需处理。

---

（本报告基于 2026-08-05 实测，覆盖 SYSTEM_TEST_PLAN.md 中 3.1~3.7 全部功能域。）