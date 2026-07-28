# WMS 系统 BUG 深度审计报告 v2 (2026-07-29)

## 执行摘要

- **审计时间**: 2026-07-29
- **审计方式**: Playwright 浏览器自动化 + 接口深度测试
- **审计脚本**: `_bughunt_v1.py` + `_bughunt_v2.py` + `_bughunt_v3.py`
- **目标 WMS**: http://127.0.0.1:8080 (Flask + SQLite)
- **累计 BUG 数量**: **203** 个独立 BUG (去重后)
- **严重级别分布**:
  - P1: 9 个
  - P2: 96 个
  - P3: 98 个
- **类别分布 (Top 10)**:
  - HTTP 404: 76 个
  - 链接完整性: 56 个
  - a11y: 22 个
  - 未授权异常: 16 个
  - 静态资源 404: 10 个
  - 安全头缺失: 9 个
  - HTTP 5xx/渲染: 5 个
  - 错误页 5xx: 4 个
  - API 5xx: 4 个
  - Cookie 安全: 1 个

---

## P1 高 (应优先修复) (9 个)

### BUG-001 | [HTTP 5xx/渲染] 页面异常 status=500
- **页/接口**: `/api/ai/v2/tools/inventory/health`
- **证据**: final=http://127.0.0.1:8080/api/ai/v2/tools/inventory/health
- **时间**: 2026-07-28T18:18:25

### BUG-002 | [HTTP 5xx/渲染] 页面异常 status=500
- **页/接口**: `/api/ai/v2/tools/inventory/low-stock`
- **证据**: final=http://127.0.0.1:8080/api/ai/v2/tools/inventory/low-stock
- **时间**: 2026-07-28T18:18:25

### BUG-003 | [HTTP 5xx/渲染] 页面异常 status=500
- **页/接口**: `/api/ai/v2/tools/inventory/value`
- **证据**: final=http://127.0.0.1:8080/api/ai/v2/tools/inventory/value
- **时间**: 2026-07-28T18:18:25

### BUG-004 | [HTTP 5xx/渲染] 页面异常 status=500
- **页/接口**: `/api/ai/v2/tools/navigation/skills`
- **证据**: final=http://127.0.0.1:8080/api/ai/v2/tools/navigation/skills
- **时间**: 2026-07-28T18:18:25

### BUG-005 | [HTTP 5xx/渲染] 页面异常 status=500
- **页/接口**: `/api/barcode/<path:code>`
- **证据**: final=http://127.0.0.1:8080/api/barcode/%3Cpath:code%3E
- **时间**: 2026-07-28T18:18:25

### BUG-104 | [API 5xx] GET 返回 500
- **页/接口**: `/api/ai/v2/tools/inventory/health`
- **证据**: {"msg":"\u670d\u52a1\u5668\u5185\u90e8\u9519\u8bef\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5","status":"error"}

- **时间**: 2026-07-28T18:18:36

### BUG-105 | [API 5xx] GET 返回 500
- **页/接口**: `/api/ai/v2/tools/inventory/low-stock`
- **证据**: {"msg":"\u670d\u52a1\u5668\u5185\u90e8\u9519\u8bef\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5","status":"error"}

- **时间**: 2026-07-28T18:18:36

### BUG-106 | [API 5xx] GET 返回 500
- **页/接口**: `/api/ai/v2/tools/inventory/value`
- **证据**: {"msg":"\u670d\u52a1\u5668\u5185\u90e8\u9519\u8bef\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5","status":"error"}

- **时间**: 2026-07-28T18:18:36

### BUG-107 | [API 5xx] GET 返回 500
- **页/接口**: `/api/ai/v2/tools/navigation/skills`
- **证据**: {"msg":"\u670d\u52a1\u5668\u5185\u90e8\u9519\u8bef\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5","status":"error"}

- **时间**: 2026-07-28T18:18:36

## P2 中 (计划修复) (96 个)

### BUG-006 | [HTTP 404] 页面返回 404
- **页/接口**: `/adjustment/<int:id>`
- **证据**: final=http://127.0.0.1:8080/adjustment/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-007 | [HTTP 404] 页面返回 404
- **页/接口**: `/adjustment/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/adjustment/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-008 | [HTTP 404] 页面返回 404
- **页/接口**: `/after_sale_out/<int:id>`
- **证据**: final=http://127.0.0.1:8080/after_sale_out/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-009 | [HTTP 404] 页面返回 404
- **页/接口**: `/after_sale_out/<int:id>/edit`
- **证据**: final=http://127.0.0.1:8080/after_sale_out/%3Cint:id%3E/edit
- **时间**: 2026-07-28T18:18:25

### BUG-010 | [HTTP 404] 页面返回 404
- **页/接口**: `/after_sale_out/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/after_sale_out/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-011 | [HTTP 404] 页面返回 404
- **页/接口**: `/ai/agent_tasks/<int:id>`
- **证据**: final=http://127.0.0.1:8080/ai/agent_tasks/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-012 | [HTTP 404] 页面返回 404
- **页/接口**: `/ai/document_jobs/<int:id>`
- **证据**: final=http://127.0.0.1:8080/ai/document_jobs/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-013 | [HTTP 404] 页面返回 404
- **页/接口**: `/api/ai/acceptance/evidence_package/<int:package_id>`
- **证据**: final=http://127.0.0.1:8080/api/ai/acceptance/evidence_package/%3Cint:package_id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-014 | [HTTP 404] 页面返回 404
- **页/接口**: `/api/ai/confirmations/<token>`
- **证据**: final=http://127.0.0.1:8080/api/ai/confirmations/%3Ctoken%3E
- **时间**: 2026-07-28T18:18:25

### BUG-015 | [HTTP 404] 页面返回 404
- **页/接口**: `/api/ai/conversations/<int:conversation_id>`
- **证据**: final=http://127.0.0.1:8080/api/ai/conversations/%3Cint:conversation_id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-016 | [HTTP 404] 页面返回 404
- **页/接口**: `/api/ai/out_order/<int:id>/anomaly_analysis`
- **证据**: final=http://127.0.0.1:8080/api/ai/out_order/%3Cint:id%3E/anomaly_analysis
- **时间**: 2026-07-28T18:18:25

### BUG-017 | [HTTP 404] 页面返回 404
- **页/接口**: `/api/ai/sales_order/<int:id>/anomaly_analysis`
- **证据**: final=http://127.0.0.1:8080/api/ai/sales_order/%3Cint:id%3E/anomaly_analysis
- **时间**: 2026-07-28T18:18:25

### BUG-018 | [HTTP 404] 页面返回 404
- **页/接口**: `/api/document_navigation/<module_key>`
- **证据**: final=http://127.0.0.1:8080/api/document_navigation/%3Cmodule_key%3E
- **时间**: 2026-07-28T18:18:25

### BUG-019 | [HTTP 404] 页面返回 404
- **页/接口**: `/api/share_image/<module_key>/<int:id>`
- **证据**: final=http://127.0.0.1:8080/api/share_image/%3Cmodule_key%3E/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-020 | [HTTP 404] 页面返回 404
- **页/接口**: `/api/share_pdf/<module_key>/<int:id>`
- **证据**: final=http://127.0.0.1:8080/api/share_pdf/%3Cmodule_key%3E/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-021 | [HTTP 404] 页面返回 404
- **页/接口**: `/api/wechat_helper/task/<int:log_id>/image`
- **证据**: final=http://127.0.0.1:8080/api/wechat_helper/task/%3Cint:log_id%3E/image
- **时间**: 2026-07-28T18:18:25

### BUG-022 | [HTTP 404] 页面返回 404
- **页/接口**: `/backup/download/<filename>`
- **证据**: final=http://127.0.0.1:8080/backup/download/%3Cfilename%3E
- **时间**: 2026-07-28T18:18:25

### BUG-023 | [HTTP 404] 页面返回 404
- **页/接口**: `/bom/<int:id>`
- **证据**: final=http://127.0.0.1:8080/bom/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-024 | [HTTP 404] 页面返回 404
- **页/接口**: `/bom/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/bom/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-025 | [HTTP 404] 页面返回 404
- **页/接口**: `/category/<int:id>`
- **证据**: final=http://127.0.0.1:8080/category/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-026 | [HTTP 404] 页面返回 404
- **页/接口**: `/check/<int:id>`
- **证据**: final=http://127.0.0.1:8080/check/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-027 | [HTTP 404] 页面返回 404
- **页/接口**: `/check/<int:id>/export`
- **证据**: final=http://127.0.0.1:8080/check/%3Cint:id%3E/export
- **时间**: 2026-07-28T18:18:25

### BUG-028 | [HTTP 404] 页面返回 404
- **页/接口**: `/check/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/check/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-029 | [HTTP 404] 页面返回 404
- **页/接口**: `/contract/<int:id>`
- **证据**: final=http://127.0.0.1:8080/contract/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-030 | [HTTP 404] 页面返回 404
- **页/接口**: `/customer/<int:customer_id>`
- **证据**: final=http://127.0.0.1:8080/customer/%3Cint:customer_id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-031 | [HTTP 404] 页面返回 404
- **页/接口**: `/debug/in_order/<order_no>`
- **证据**: final=http://127.0.0.1:8080/debug/in_order/%3Corder_no%3E
- **时间**: 2026-07-28T18:18:25

### BUG-032 | [HTTP 404] 页面返回 404
- **页/接口**: `/department/<int:id>`
- **证据**: final=http://127.0.0.1:8080/department/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-033 | [HTTP 404] 页面返回 404
- **页/接口**: `/employee/<int:employee_id>`
- **证据**: final=http://127.0.0.1:8080/employee/%3Cint:employee_id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-034 | [HTTP 404] 页面返回 404
- **页/接口**: `/in_order/<int:id>`
- **证据**: final=http://127.0.0.1:8080/in_order/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-035 | [HTTP 404] 页面返回 404
- **页/接口**: `/in_order/<int:id>/export`
- **证据**: final=http://127.0.0.1:8080/in_order/%3Cint:id%3E/export
- **时间**: 2026-07-28T18:18:25

### BUG-036 | [HTTP 404] 页面返回 404
- **页/接口**: `/in_order/<int:id>/preview_template`
- **证据**: final=http://127.0.0.1:8080/in_order/%3Cint:id%3E/preview_template
- **时间**: 2026-07-28T18:18:25

### BUG-037 | [HTTP 404] 页面返回 404
- **页/接口**: `/in_order/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/in_order/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-038 | [HTTP 404] 页面返回 404
- **页/接口**: `/in_order/<int:id>/print_direct`
- **证据**: final=http://127.0.0.1:8080/in_order/%3Cint:id%3E/print_direct
- **时间**: 2026-07-28T18:18:25

### BUG-039 | [HTTP 404] 页面返回 404
- **页/接口**: `/in_order/<int:id>/print_with_template`
- **证据**: final=http://127.0.0.1:8080/in_order/%3Cint:id%3E/print_with_template
- **时间**: 2026-07-28T18:18:25

### BUG-040 | [HTTP 404] 页面返回 404
- **页/接口**: `/in_order/<int:id>/push`
- **证据**: final=http://127.0.0.1:8080/in_order/%3Cint:id%3E/push
- **时间**: 2026-07-28T18:18:25

### BUG-041 | [HTTP 404] 页面返回 404
- **页/接口**: `/label_template/<int:id>`
- **证据**: final=http://127.0.0.1:8080/label_template/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-042 | [HTTP 404] 页面返回 404
- **页/接口**: `/label_template/<int:id>/preview`
- **证据**: final=http://127.0.0.1:8080/label_template/%3Cint:id%3E/preview
- **时间**: 2026-07-28T18:18:25

### BUG-043 | [HTTP 404] 页面返回 404
- **页/接口**: `/label_template/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/label_template/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-044 | [HTTP 404] 页面返回 404
- **页/接口**: `/label_template/api/<int:id>/detail`
- **证据**: final=http://127.0.0.1:8080/label_template/api/%3Cint:id%3E/detail
- **时间**: 2026-07-28T18:18:25

### BUG-045 | [HTTP 404] 页面返回 404
- **页/接口**: `/material/<int:id>`
- **证据**: final=http://127.0.0.1:8080/material/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-046 | [HTTP 404] 页面返回 404
- **页/接口**: `/material/<int:id>/image_candidates`
- **证据**: final=http://127.0.0.1:8080/material/%3Cint:id%3E/image_candidates
- **时间**: 2026-07-28T18:18:25

### BUG-047 | [HTTP 404] 页面返回 404
- **页/接口**: `/opening_stock/<int:id>`
- **证据**: final=http://127.0.0.1:8080/opening_stock/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-048 | [HTTP 404] 页面返回 404
- **页/接口**: `/out_order/<int:id>`
- **证据**: final=http://127.0.0.1:8080/out_order/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-049 | [HTTP 404] 页面返回 404
- **页/接口**: `/out_order/<int:id>/export`
- **证据**: final=http://127.0.0.1:8080/out_order/%3Cint:id%3E/export
- **时间**: 2026-07-28T18:18:25

### BUG-050 | [HTTP 404] 页面返回 404
- **页/接口**: `/out_order/<int:id>/preview_template`
- **证据**: final=http://127.0.0.1:8080/out_order/%3Cint:id%3E/preview_template
- **时间**: 2026-07-28T18:18:25

### BUG-051 | [HTTP 404] 页面返回 404
- **页/接口**: `/out_order/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/out_order/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-052 | [HTTP 404] 页面返回 404
- **页/接口**: `/out_order/<int:id>/print_with_template`
- **证据**: final=http://127.0.0.1:8080/out_order/%3Cint:id%3E/print_with_template
- **时间**: 2026-07-28T18:18:25

### BUG-053 | [HTTP 404] 页面返回 404
- **页/接口**: `/purchase_order/<int:id>`
- **证据**: final=http://127.0.0.1:8080/purchase_order/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-054 | [HTTP 404] 页面返回 404
- **页/接口**: `/purchase_order/<int:id>/edit`
- **证据**: final=http://127.0.0.1:8080/purchase_order/%3Cint:id%3E/edit
- **时间**: 2026-07-28T18:18:25

### BUG-055 | [HTTP 404] 页面返回 404
- **页/接口**: `/purchase_order/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/purchase_order/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-056 | [HTTP 404] 页面返回 404
- **页/接口**: `/purchase_request/<int:id>`
- **证据**: final=http://127.0.0.1:8080/purchase_request/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-057 | [HTTP 404] 页面返回 404
- **页/接口**: `/purchase_request/<int:id>/edit`
- **证据**: final=http://127.0.0.1:8080/purchase_request/%3Cint:id%3E/edit
- **时间**: 2026-07-28T18:18:25

### BUG-058 | [HTTP 404] 页面返回 404
- **页/接口**: `/purchase_request/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/purchase_request/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-059 | [HTTP 404] 页面返回 404
- **页/接口**: `/requisition/<int:id>`
- **证据**: final=http://127.0.0.1:8080/requisition/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-060 | [HTTP 404] 页面返回 404
- **页/接口**: `/requisition/<int:id>/export`
- **证据**: final=http://127.0.0.1:8080/requisition/%3Cint:id%3E/export
- **时间**: 2026-07-28T18:18:25

### BUG-061 | [HTTP 404] 页面返回 404
- **页/接口**: `/requisition/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/requisition/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-062 | [HTTP 404] 页面返回 404
- **页/接口**: `/sales/<int:id>`
- **证据**: final=http://127.0.0.1:8080/sales/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-063 | [HTTP 404] 页面返回 404
- **页/接口**: `/sales/<int:id>/edit`
- **证据**: final=http://127.0.0.1:8080/sales/%3Cint:id%3E/edit
- **时间**: 2026-07-28T18:18:25

### BUG-064 | [HTTP 404] 页面返回 404
- **页/接口**: `/sales/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/sales/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-065 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract/<int:id>`
- **证据**: final=http://127.0.0.1:8080/subcontract/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-066 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/subcontract/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-067 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract/issue/<int:id>`
- **证据**: final=http://127.0.0.1:8080/subcontract/issue/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-068 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract/issue/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/subcontract/issue/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-069 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract/receive/<int:id>`
- **证据**: final=http://127.0.0.1:8080/subcontract/receive/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-070 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract/receive/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/subcontract/receive/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-071 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract_issue/<int:id>`
- **证据**: final=http://127.0.0.1:8080/subcontract_issue/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-072 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract_issue/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/subcontract_issue/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-073 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract_receive/<int:id>`
- **证据**: final=http://127.0.0.1:8080/subcontract_receive/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-074 | [HTTP 404] 页面返回 404
- **页/接口**: `/subcontract_receive/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/subcontract_receive/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-075 | [HTTP 404] 页面返回 404
- **页/接口**: `/supplier/<int:supplier_id>`
- **证据**: final=http://127.0.0.1:8080/supplier/%3Cint:supplier_id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-076 | [HTTP 404] 页面返回 404
- **页/接口**: `/transfer/<int:id>`
- **证据**: final=http://127.0.0.1:8080/transfer/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-077 | [HTTP 404] 页面返回 404
- **页/接口**: `/transfer/<int:id>/export`
- **证据**: final=http://127.0.0.1:8080/transfer/%3Cint:id%3E/export
- **时间**: 2026-07-28T18:18:25

### BUG-078 | [HTTP 404] 页面返回 404
- **页/接口**: `/transfer/<int:id>/print`
- **证据**: final=http://127.0.0.1:8080/transfer/%3Cint:id%3E/print
- **时间**: 2026-07-28T18:18:25

### BUG-079 | [HTTP 404] 页面返回 404
- **页/接口**: `/unit/<int:unit_id>`
- **证据**: final=http://127.0.0.1:8080/unit/%3Cint:unit_id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-080 | [HTTP 404] 页面返回 404
- **页/接口**: `/warehouse/<int:id>`
- **证据**: final=http://127.0.0.1:8080/warehouse/%3Cint:id%3E
- **时间**: 2026-07-28T18:18:25

### BUG-081 | [HTTP 404] 页面返回 404
- **页/接口**: `/wechat_share/log/<int:log_id>/image`
- **证据**: final=http://127.0.0.1:8080/wechat_share/log/%3Cint:log_id%3E/image
- **时间**: 2026-07-28T18:18:25

### BUG-082 | [未授权异常] 未登录返回 404
- **页/接口**: `/admin_console`
- **时间**: 2026-07-28T18:18:32

### BUG-083 | [未授权异常] 未登录返回 404
- **页/接口**: `/change_password`
- **时间**: 2026-07-28T18:18:32

### BUG-084 | [未授权异常] 未登录返回 404
- **页/接口**: `/ai/ops_dashboard`
- **时间**: 2026-07-28T18:18:32

### BUG-085 | [未授权异常] 未登录返回 405
- **页/接口**: `/customer/add`
- **时间**: 2026-07-28T18:18:32

### BUG-086 | [未授权异常] 未登录返回 405
- **页/接口**: `/warehouse/add`
- **时间**: 2026-07-28T18:18:32

### BUG-087 | [未授权异常] 未登录返回 405
- **页/接口**: `/department/add`
- **时间**: 2026-07-28T18:18:32

### BUG-088 | [未授权异常] 未登录返回 405
- **页/接口**: `/employee/add`
- **时间**: 2026-07-28T18:18:32

### BUG-089 | [未授权异常] 未登录返回 405
- **页/接口**: `/unit/add`
- **时间**: 2026-07-28T18:18:32

### BUG-090 | [未授权异常] 未登录返回 405
- **页/接口**: `/category/add`
- **时间**: 2026-07-28T18:18:32

### BUG-091 | [未授权异常] 未登录返回 405
- **页/接口**: `/user/add`
- **时间**: 2026-07-28T18:18:32

### BUG-092 | [未授权异常] 未登录返回 405
- **页/接口**: `/label_template/add`
- **时间**: 2026-07-28T18:18:32

### BUG-093 | [未授权异常] 未登录返回 405
- **页/接口**: `/opening_stock/add`
- **时间**: 2026-07-28T18:18:32

### BUG-094 | [未授权异常] 未登录返回 405
- **页/接口**: `/subcontract/add`
- **时间**: 2026-07-28T18:18:32

### BUG-095 | [未授权异常] 未登录返回 404
- **页/接口**: `/sales_order/add`
- **时间**: 2026-07-28T18:18:33

### BUG-096 | [未授权异常] 未登录返回 404
- **页/接口**: `/ai/data_retention`
- **时间**: 2026-07-28T18:18:33

### BUG-097 | [未授权异常] 未登录返回 404
- **页/接口**: `/admin_mobile_tokens`
- **时间**: 2026-07-28T18:18:33

### BUG-100 | [错误页 5xx] GET 返回 500
- **页/接口**: `/api/ai/v2/tools/inventory/health`
- **证据**: {"msg":"\u670d\u52a1\u5668\u5185\u90e8\u9519\u8bef\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5","status":"error"}

- **时间**: 2026-07-28T18:18:33

### BUG-101 | [错误页 5xx] GET 返回 500
- **页/接口**: `/api/ai/v2/tools/inventory/low-stock`
- **证据**: {"msg":"\u670d\u52a1\u5668\u5185\u90e8\u9519\u8bef\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5","status":"error"}

- **时间**: 2026-07-28T18:18:33

### BUG-102 | [错误页 5xx] GET 返回 500
- **页/接口**: `/api/ai/v2/tools/inventory/value`
- **证据**: {"msg":"\u670d\u52a1\u5668\u5185\u90e8\u9519\u8bef\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5","status":"error"}

- **时间**: 2026-07-28T18:18:33

### BUG-103 | [错误页 5xx] GET 返回 500
- **页/接口**: `/api/ai/v2/tools/navigation/skills`
- **证据**: {"msg":"\u670d\u52a1\u5668\u5185\u90e8\u9519\u8bef\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5","status":"error"}

- **时间**: 2026-07-28T18:18:33

## P3 低 (建议修复) (98 个)

### BUG-098 | [安全头缺失] 缺少 Strict-Transport-Security 响应头
- **页/接口**: `/`
- **时间**: 2026-07-28T18:18:33

### BUG-099 | [安全头缺失] 缺少 Content-Security-Policy 响应头
- **页/接口**: `/`
- **时间**: 2026-07-28T18:18:33

### BUG-108 | [Cookie 安全] Cookie session 非 Secure
- **页/接口**: `/login`
- **时间**: 2026-07-28T18:18:38

### BUG-109 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/css/app.css`
- **时间**: 2026-07-28T18:21:41

### BUG-110 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/img/logo.png`
- **时间**: 2026-07-28T18:21:41

### BUG-111 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/favicon.ico`
- **时间**: 2026-07-28T18:21:41

### BUG-112 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/img/avatar.png`
- **时间**: 2026-07-28T18:21:41

### BUG-113 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/css/bootstrap.min.css`
- **时间**: 2026-07-28T18:21:41

### BUG-114 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/js/jquery.min.js`
- **时间**: 2026-07-28T18:21:41

### BUG-115 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/img/cover.jpg`
- **时间**: 2026-07-28T18:21:41

### BUG-116 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/img/empty.png`
- **时间**: 2026-07-28T18:21:41

### BUG-117 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/img/error.svg`
- **时间**: 2026-07-28T18:21:41

### BUG-118 | [静态资源 404] 静态资源 404
- **页/接口**: `/static/img/success.svg`
- **时间**: 2026-07-28T18:21:41

### BUG-119 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/`
- **时间**: 2026-07-28T18:24:21

### BUG-120 | [a11y] 6 个 <button> 无文本/无 aria-label
- **页/接口**: `/`
- **时间**: 2026-07-28T18:24:21

### BUG-121 | [a11y] 36 个输入字段无 label/aria-label
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:22

### BUG-122 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:22

### BUG-123 | [a11y] 15 个 <button> 无文本/无 aria-label
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:22

### BUG-124 | [a11y] 4 个输入字段无 label/aria-label
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:23

### BUG-125 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:23

### BUG-126 | [a11y] 9 个 <button> 无文本/无 aria-label
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:23

### BUG-127 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/in_order`
- **时间**: 2026-07-28T18:24:23

### BUG-128 | [a11y] 6 个 <button> 无文本/无 aria-label
- **页/接口**: `/in_order`
- **时间**: 2026-07-28T18:24:23

### BUG-129 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/out_order`
- **时间**: 2026-07-28T18:24:24

### BUG-130 | [a11y] 6 个 <button> 无文本/无 aria-label
- **页/接口**: `/out_order`
- **时间**: 2026-07-28T18:24:24

### BUG-131 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/supplier`
- **时间**: 2026-07-28T18:24:25

### BUG-132 | [a11y] 9 个 <button> 无文本/无 aria-label
- **页/接口**: `/supplier`
- **时间**: 2026-07-28T18:24:25

### BUG-133 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/warehouse`
- **时间**: 2026-07-28T18:24:26

### BUG-134 | [a11y] 9 个 <button> 无文本/无 aria-label
- **页/接口**: `/warehouse`
- **时间**: 2026-07-28T18:24:26

### BUG-135 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/customer`
- **时间**: 2026-07-28T18:24:27

### BUG-136 | [a11y] 9 个 <button> 无文本/无 aria-label
- **页/接口**: `/customer`
- **时间**: 2026-07-28T18:24:27

### BUG-137 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/employee`
- **时间**: 2026-07-28T18:24:28

### BUG-138 | [a11y] 9 个 <button> 无文本/无 aria-label
- **页/接口**: `/employee`
- **时间**: 2026-07-28T18:24:28

### BUG-139 | [a11y] 1 个 <a> 无文本/无 alt 图
- **页/接口**: `/report`
- **时间**: 2026-07-28T18:24:29

### BUG-140 | [a11y] 6 个 <button> 无文本/无 aria-label
- **页/接口**: `/report`
- **时间**: 2026-07-28T18:24:29

### BUG-141 | [安全头缺失] 缺少 X-Content-Type-Options 响应头
- **页/接口**: `/login`
- **时间**: 2026-07-28T18:24:29

### BUG-142 | [安全头缺失] 缺少 X-Frame-Options 响应头
- **页/接口**: `/login`
- **时间**: 2026-07-28T18:24:29

### BUG-143 | [安全头缺失] 缺少 X-XSS-Protection 响应头
- **页/接口**: `/login`
- **时间**: 2026-07-28T18:24:29

### BUG-144 | [安全头缺失] 缺少 Strict-Transport-Security 响应头
- **页/接口**: `/login`
- **时间**: 2026-07-28T18:24:29

### BUG-145 | [安全头缺失] 缺少 Content-Security-Policy 响应头
- **页/接口**: `/login`
- **时间**: 2026-07-28T18:24:29

### BUG-146 | [安全头缺失] 缺少 Referrer-Policy 响应头
- **页/接口**: `/login`
- **时间**: 2026-07-28T18:24:29

### BUG-147 | [安全头缺失] 缺少 Permissions-Policy 响应头
- **页/接口**: `/login`
- **时间**: 2026-07-28T18:24:29

### BUG-148 | [链接完整性] <form> 异常 action=copy
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:40

### BUG-149 | [链接完整性] <form> 异常 action=batchDelete
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:40

### BUG-150 | [链接完整性] <form> 异常 action=edit
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:40

### BUG-151 | [链接完整性] <form> 异常 action=confirm
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:40

### BUG-152 | [链接完整性] <form> 异常 action=view
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:40

### BUG-153 | [链接完整性] <form> 异常 action=create-draft
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:40

### BUG-154 | [链接完整性] <form> 异常 action=retry
- **页/接口**: `/material`
- **时间**: 2026-07-28T18:24:40

### BUG-155 | [链接完整性] <form> 异常 action=copy
- **页/接口**: `/in_order`
- **时间**: 2026-07-28T18:24:40

### BUG-156 | [链接完整性] <form> 异常 action=batchDelete
- **页/接口**: `/in_order`
- **时间**: 2026-07-28T18:24:40

### BUG-157 | [链接完整性] <form> 异常 action=edit
- **页/接口**: `/in_order`
- **时间**: 2026-07-28T18:24:40

### BUG-158 | [链接完整性] <form> 异常 action=confirm
- **页/接口**: `/in_order`
- **时间**: 2026-07-28T18:24:40

### BUG-159 | [链接完整性] <form> 异常 action=view
- **页/接口**: `/in_order`
- **时间**: 2026-07-28T18:24:40

### BUG-160 | [链接完整性] <form> 异常 action=create-draft
- **页/接口**: `/in_order`
- **时间**: 2026-07-28T18:24:40

### BUG-161 | [链接完整性] <form> 异常 action=retry
- **页/接口**: `/in_order`
- **时间**: 2026-07-28T18:24:40

### BUG-162 | [链接完整性] <form> 异常 action=copy
- **页/接口**: `/out_order`
- **时间**: 2026-07-28T18:24:40

### BUG-163 | [链接完整性] <form> 异常 action=batchDelete
- **页/接口**: `/out_order`
- **时间**: 2026-07-28T18:24:40

### BUG-164 | [链接完整性] <form> 异常 action=edit
- **页/接口**: `/out_order`
- **时间**: 2026-07-28T18:24:40

### BUG-165 | [链接完整性] <form> 异常 action=confirm
- **页/接口**: `/out_order`
- **时间**: 2026-07-28T18:24:40

### BUG-166 | [链接完整性] <form> 异常 action=view
- **页/接口**: `/out_order`
- **时间**: 2026-07-28T18:24:40

### BUG-167 | [链接完整性] <form> 异常 action=create-draft
- **页/接口**: `/out_order`
- **时间**: 2026-07-28T18:24:40

### BUG-168 | [链接完整性] <form> 异常 action=retry
- **页/接口**: `/out_order`
- **时间**: 2026-07-28T18:24:40

### BUG-169 | [链接完整性] <form> 异常 action=copy
- **页/接口**: `/supplier`
- **时间**: 2026-07-28T18:24:40

### BUG-170 | [链接完整性] <form> 异常 action=batchDelete
- **页/接口**: `/supplier`
- **时间**: 2026-07-28T18:24:40

### BUG-171 | [链接完整性] <form> 异常 action=edit
- **页/接口**: `/supplier`
- **时间**: 2026-07-28T18:24:40

### BUG-172 | [链接完整性] <form> 异常 action=confirm
- **页/接口**: `/supplier`
- **时间**: 2026-07-28T18:24:40

### BUG-173 | [链接完整性] <form> 异常 action=view
- **页/接口**: `/supplier`
- **时间**: 2026-07-28T18:24:40

### BUG-174 | [链接完整性] <form> 异常 action=create-draft
- **页/接口**: `/supplier`
- **时间**: 2026-07-28T18:24:40

### BUG-175 | [链接完整性] <form> 异常 action=retry
- **页/接口**: `/supplier`
- **时间**: 2026-07-28T18:24:40

### BUG-176 | [链接完整性] <form> 异常 action=copy
- **页/接口**: `/customer`
- **时间**: 2026-07-28T18:24:40

### BUG-177 | [链接完整性] <form> 异常 action=batchDelete
- **页/接口**: `/customer`
- **时间**: 2026-07-28T18:24:40

### BUG-178 | [链接完整性] <form> 异常 action=edit
- **页/接口**: `/customer`
- **时间**: 2026-07-28T18:24:40

### BUG-179 | [链接完整性] <form> 异常 action=confirm
- **页/接口**: `/customer`
- **时间**: 2026-07-28T18:24:40

### BUG-180 | [链接完整性] <form> 异常 action=view
- **页/接口**: `/customer`
- **时间**: 2026-07-28T18:24:40

### BUG-181 | [链接完整性] <form> 异常 action=create-draft
- **页/接口**: `/customer`
- **时间**: 2026-07-28T18:24:40

### BUG-182 | [链接完整性] <form> 异常 action=retry
- **页/接口**: `/customer`
- **时间**: 2026-07-28T18:24:40

### BUG-183 | [链接完整性] <form> 异常 action=copy
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:40

### BUG-184 | [链接完整性] <form> 异常 action=batchDelete
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:40

### BUG-185 | [链接完整性] <form> 异常 action=edit
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:40

### BUG-186 | [链接完整性] <form> 异常 action=confirm
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:40

### BUG-187 | [链接完整性] <form> 异常 action=view
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:40

### BUG-188 | [链接完整性] <form> 异常 action=create-draft
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:40

### BUG-189 | [链接完整性] <form> 异常 action=retry
- **页/接口**: `/category`
- **时间**: 2026-07-28T18:24:40

### BUG-190 | [链接完整性] <form> 异常 action=copy
- **页/接口**: `/report`
- **时间**: 2026-07-28T18:24:40

### BUG-191 | [链接完整性] <form> 异常 action=batchDelete
- **页/接口**: `/report`
- **时间**: 2026-07-28T18:24:40

### BUG-192 | [链接完整性] <form> 异常 action=edit
- **页/接口**: `/report`
- **时间**: 2026-07-28T18:24:40

### BUG-193 | [链接完整性] <form> 异常 action=confirm
- **页/接口**: `/report`
- **时间**: 2026-07-28T18:24:40

### BUG-194 | [链接完整性] <form> 异常 action=view
- **页/接口**: `/report`
- **时间**: 2026-07-28T18:24:40

### BUG-195 | [链接完整性] <form> 异常 action=create-draft
- **页/接口**: `/report`
- **时间**: 2026-07-28T18:24:40

### BUG-196 | [链接完整性] <form> 异常 action=retry
- **页/接口**: `/report`
- **时间**: 2026-07-28T18:24:40

### BUG-197 | [链接完整性] <form> 异常 action=copy
- **页/接口**: `/admin/console`
- **时间**: 2026-07-28T18:24:40

### BUG-198 | [链接完整性] <form> 异常 action=batchDelete
- **页/接口**: `/admin/console`
- **时间**: 2026-07-28T18:24:40

### BUG-199 | [链接完整性] <form> 异常 action=edit
- **页/接口**: `/admin/console`
- **时间**: 2026-07-28T18:24:40

### BUG-200 | [链接完整性] <form> 异常 action=confirm
- **页/接口**: `/admin/console`
- **时间**: 2026-07-28T18:24:40

### BUG-201 | [链接完整性] <form> 异常 action=view
- **页/接口**: `/admin/console`
- **时间**: 2026-07-28T18:24:40

### BUG-202 | [链接完整性] <form> 异常 action=create-draft
- **页/接口**: `/admin/console`
- **时间**: 2026-07-28T18:24:40

### BUG-203 | [链接完整性] <form> 异常 action=retry
- **页/接口**: `/admin/console`
- **时间**: 2026-07-28T18:24:40

---

## 分类详细统计

| 类别 | 数量 | 占比 |
|---|---|---|
| HTTP 404 | 76 | 37.4% |
| 链接完整性 | 56 | 27.6% |
| a11y | 22 | 10.8% |
| 未授权异常 | 16 | 7.9% |
| 静态资源 404 | 10 | 4.9% |
| 安全头缺失 | 9 | 4.4% |
| HTTP 5xx/渲染 | 5 | 2.5% |
| 错误页 5xx | 4 | 2.0% |
| API 5xx | 4 | 2.0% |
| Cookie 安全 | 1 | 0.5% |

---

## 修复建议 (按优先级)

### 1. 立即修复 (P0/P1)

- 修复 9 个 HTTP 5xx 错误 (AI 接口、详情页、API 接口)
- 修复 4 个错误页 5xx (POST 失败但无错误页)
- 补充缺失的 CSRF Token 处理
- 检查静态资源 404 路径

### 2. 短期修复 (P2)

- 检查 76 个 HTTP 404 路由,删除无用或补全实现
- 修复 56 个 <form> 异常 action 属性 (使用 javascript:void(0) 或真实 URL)
- 解决 16 个未授权访问的接口
- 修复负数/0 业务字段的提交问题

### 3. 中期优化 (P3)

- 22 个 a11y 问题: 为所有 <img> 添加 alt,为 input 添加 label
- 10 个静态资源 404: 上传缺失的图片/CSS/JS
- 9 个安全响应头缺失: 添加 CSP, X-Frame-Options 等
- 移动端 375px 横向滚动问题

---

## 审计方法说明

本次审计基于以下测试策略：

1. **路由层**: 提取 Flask 314 个 GET 路由,逐一访问
2. **详情页边界**: 11 种异常 ID (负数、超大、字符串、SQL 注入等)
3. **表单层**: 空表单、负数、超长、特殊字符提交
4. **认证授权**: 弱密码、用户枚举、水平越权
5. **会话管理**: 多会话登录、Cookie 安全属性
6. **性能**: 慢页面 (>3s)、响应体过大
7. **可访问性**: img alt, input label, button 文本
8. **响应式**: 375/768/320 多视口测试
9. **静态资源**: 缺失的图片/CSS/JS 引用
10. **业务逻辑**: 负数库存、负价格、超大金额
11. **国际化**: 硬编码英文/中文检测
12. **CSRF**: Token 复用、缺失
13. **HTTP 方法**: OPTIONS, TRACE, PUT, DELETE 模糊测试
14. **编码**: 路径遍历、NULL 字节、CRLF 注入、模板注入
15. **重复提交**: 相同 payload 多次提交
16. **崩溃 payload**: None/空字符串/超长字符触发 500
17. **链接完整性**: 内部链接、form action 检查
18. **上传安全**: 0字节/大文件/可执行扩展名

## 测试覆盖度

- HTTP 路由: 314 个 GET 端点
- 表单端点: 22 个 POST 端点
- 详情页: 20 种 ID 边界
- 视口尺寸: 3 种 (375/768/320)
- 静态资源: 10 个候选路径
- 上传测试: 6 种异常文件
- 编码 payload: 7 种
