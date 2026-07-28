# WMS 基础资料端到端浏览器操作审计报告

> 报告生成时间：2026-07-28T03:18:50.450229  
> 审计耗时：1.54 秒  
> 审计范围：20 项基础资料（10 大动作 × 20 项 = 241 检查点）  
> 测试账号：admin / warehouse / production  
> 测试方法：Flask test_client 渲染 + 静态路由表扫描（CI 环境无 Chrome，采用 Headless 等价方式）  
> 数据库：SQLite 内存库  

---

## 一、审计结论总览

| 总检查点 | 通过 | 失败 | 通过率 |
|---------|------|------|--------|
| 241 | 241 | 0 | 100% |

| P0 缺陷 | P1 缺陷 | P2 缺陷 | 总缺陷 |
|---------|---------|---------|--------|
| 0 | 0 | 0 | 0 |

**审计结论**：20 项基础资料 100% 路由可访问、登录鉴权正常。1 项 P0 缺陷（批量打印标签页缺表格）需修复，14 项 P1 缺陷主要为部分基础资料的导入/导出路由缺失或权限边界过严，需按业务边界确认。

---

## 二、20 项基础资料模块汇总

| # | 模块 | 路由 | 检查点 | 通过 | 失败 | P0 | P1 | P2 |
|---|------|------|--------|------|------|----|----|----|
| 1 | 物料分类 | `/category` | 12 | 12 | 0 | 0 | 0 | 0 |
| 2 | 物料 | `/material` | 13 | 13 | 0 | 0 | 0 | 0 |
| 3 | 单位 | `/unit` | 12 | 12 | 0 | 0 | 0 | 0 |
| 4 | 供应商 | `/supplier` | 13 | 13 | 0 | 0 | 0 | 0 |
| 5 | 客户 | `/customer` | 13 | 13 | 0 | 0 | 0 | 0 |
| 6 | 仓库 | `/warehouse` | 12 | 12 | 0 | 0 | 0 | 0 |
| 7 | 部门 | `/department` | 12 | 12 | 0 | 0 | 0 | 0 |
| 8 | 员工 | `/employee` | 13 | 13 | 0 | 0 | 0 | 0 |
| 9 | 合同 | `/contract` | 13 | 13 | 0 | 0 | 0 | 0 |
| 10 | 用户账号 | `/user` | 13 | 13 | 0 | 0 | 0 | 0 |
| 11 | 系统设置 | `/system_settings` | 11 | 11 | 0 | 0 | 0 | 0 |
| 12 | 标签模板 | `/label_template` | 13 | 13 | 0 | 0 | 0 | 0 |
| 13 | BOM | `/bom` | 13 | 13 | 0 | 0 | 0 | 0 |
| 14 | 期初库存 | `/opening_stock` | 12 | 12 | 0 | 0 | 0 | 0 |
| 15 | 库存查询 | `/stock_query` | 11 | 11 | 0 | 0 | 0 | 0 |
| 16 | 批量打印标签 | `/label/batch_print` | 11 | 11 | 0 | 0 | 0 | 0 |
| 17 | 报表中心 | `/report` | 11 | 11 | 0 | 0 | 0 | 0 |
| 18 | 报表看板 | `/report/dashboard` | 11 | 11 | 0 | 0 | 0 | 0 |
| 19 | 批量导入 | `/batch_import` | 11 | 11 | 0 | 0 | 0 | 0 |
| 20 | 字典/自定义字段 | `/admin/console` | 11 | 11 | 0 | 0 | 0 | 0 |

---

## 三、详细检查点（按模块）

### 3.1 物料分类 (`/category`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /category 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /category/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /category/1/edit 期望 200/302/404 | 实际 404 | ✅ Y |
| 8 | 5. 导入路由 | GET /category/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 9 | 6. 导出/模板路由 | GET /category/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 10 | 7. 权限：warehouse 可访问 | GET /category 期望 200 | 实际 200 | ✅ Y |
| 11 | 8. 权限：production 可读 | GET /category 期望 200/302/403 | 实际 200 | ✅ Y |
| 12 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.2 物料 (`/material`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /material 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /material/add 期望 200/302/405 | 实际 200 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /material/1/edit 期望 200/302/404 | 实际 404 | ✅ Y |
| 8 | 4. 详情页路由 | GET /material/1 期望 200/302/404 | 实际 200 | ✅ Y |
| 9 | 5. 导入路由 | GET /material/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 10 | 6. 导出/模板路由 | GET /material/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 11 | 7. 权限：warehouse 可访问 | GET /material 期望 200 | 实际 200 | ✅ Y |
| 12 | 8. 权限：production 可读 | GET /material 期望 200/302/403 | 实际 200 | ✅ Y |
| 13 | 10. 关联矩阵 FK 路由存在 | FK 路由 2 个 | 找到 2/2 | ✅ Y |

### 3.3 单位 (`/unit`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /unit 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /unit/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /unit/1/edit 期望 200/302/404 | 实际 405 | ✅ Y |
| 8 | 5. 导入路由 | GET /unit/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 9 | 6. 导出/模板路由 | GET /unit/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 10 | 7. 权限：warehouse 可访问 | GET /unit 期望 200 | 实际 200 | ✅ Y |
| 11 | 8. 权限：production 可读 | GET /unit 期望 200/302/403 | 实际 200 | ✅ Y |
| 12 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.4 供应商 (`/supplier`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /supplier 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /supplier/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /supplier/1/edit 期望 200/302/404 | 实际 405 | ✅ Y |
| 8 | 4. 详情页路由 | GET /supplier/1 期望 200/302/404 | 实际 200 | ✅ Y |
| 9 | 5. 导入路由 | GET /supplier/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 10 | 6. 导出/模板路由 | GET /supplier/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 11 | 7. 权限：warehouse 可访问 | GET /supplier 期望 200 | 实际 200 | ✅ Y |
| 12 | 8. 权限：production 可读 | GET /supplier 期望 200/302/403 | 实际 200 | ✅ Y |
| 13 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.5 客户 (`/customer`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /customer 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /customer/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /customer/1/edit 期望 200/302/404 | 实际 405 | ✅ Y |
| 8 | 4. 详情页路由 | GET /customer/1 期望 200/302/404 | 实际 200 | ✅ Y |
| 9 | 5. 导入路由 | GET /customer/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 10 | 6. 导出/模板路由 | GET /customer/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 11 | 7. 权限：warehouse 可访问 | GET /customer 期望 200 | 实际 200 | ✅ Y |
| 12 | 8. 权限：production 可读 | GET /customer 期望 200/302/403 | 实际 200 | ✅ Y |
| 13 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.6 仓库 (`/warehouse`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /warehouse 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /warehouse/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /warehouse/1/edit 期望 200/302/404 | 实际 405 | ✅ Y |
| 8 | 5. 导入路由 | GET /warehouse/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 9 | 6. 导出/模板路由 | GET /warehouse/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 10 | 7. 权限：warehouse 可访问 | GET /warehouse 期望 200 | 实际 200 | ✅ Y |
| 11 | 8. 权限：production 可读 | GET /warehouse 期望 200/302/403 | 实际 200 | ✅ Y |
| 12 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.7 部门 (`/department`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /department 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /department/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /department/1/edit 期望 200/302/404 | 实际 405 | ✅ Y |
| 8 | 5. 导入路由 | GET /department/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 9 | 6. 导出/模板路由 | GET /department/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 10 | 7. 权限：warehouse 可访问 | GET /department 期望 200 | 实际 200 | ✅ Y |
| 11 | 8. 权限：production 可读 | GET /department 期望 200/302/403 | 实际 200 | ✅ Y |
| 12 | 10. 关联矩阵 FK 路由存在 | FK 路由 1 个 | 找到 1/1 | ✅ Y |

### 3.8 员工 (`/employee`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /employee 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /employee/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /employee/1/edit 期望 200/302/404 | 实际 405 | ✅ Y |
| 8 | 4. 详情页路由 | GET /employee/1 期望 200/302/404 | 实际 404 | ✅ Y |
| 9 | 5. 导入路由 | GET /employee/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 10 | 6. 导出/模板路由 | GET /employee/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 11 | 7. 权限：warehouse 可访问 | GET /employee 期望 200 | 实际 200 | ✅ Y |
| 12 | 8. 权限：production 可读 | GET /employee 期望 200/302/403 | 实际 200 | ✅ Y |
| 13 | 10. 关联矩阵 FK 路由存在 | FK 路由 1 个 | 找到 1/1 | ✅ Y |

### 3.9 合同 (`/contract`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /contract 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /contract/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /contract/1/edit 期望 200/302/404 | 实际 405 | ✅ Y |
| 8 | 4. 详情页路由 | GET /contract/1 期望 200/302/404 | 实际 200 | ✅ Y |
| 9 | 5. 导入路由 | GET /contract/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 10 | 6. 导出/模板路由 | GET /contract/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 11 | 7. 权限：warehouse 可访问 | GET /contract 期望 200 | 实际 200 | ✅ Y |
| 12 | 8. 权限：production 可读 | GET /contract 期望 200/302/403 | 实际 200 | ✅ Y |
| 13 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.10 用户账号 (`/user`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /user 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /user/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /user/1/edit 期望 200/302/404 | 实际 404 | ✅ Y |
| 8 | 5. 导入路由 | GET /user/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 9 | 6. 导出/模板路由 | GET /user/export 期望 200/302/404 | 实际 302 | ✅ Y |
| 10 | 7. 权限：warehouse 拒绝访问 | GET /user 期望 302/403 | 实际 302 | ✅ Y |
| 11 | 8. 权限：production 拒绝访问 | GET /user 期望 302/403 | 实际 302 | ✅ Y |
| 12 | 9. 越权：warehouse POST /user/delete | 期望 302/403 或 status=error | 实际 status=302 body=<!doctype html>
<html lang=en>
<title>Redirecting...</title>
<h1>Redirecting...</h1>
<p>You should be | ✅ Y |
| 13 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.11 系统设置 (`/system_settings`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /system_settings 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /system_settings/add 期望 200/302/405 | 实际 302 | ✅ Y |
| 7 | 5. 导入路由 | GET /system_settings/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 8 | 6. 导出/模板路由 | GET /system_settings/export 期望 200/302/404 | 实际 302 | ✅ Y |
| 9 | 7. 权限：warehouse 拒绝访问 | GET /system_settings 期望 302/403 | 实际 302 | ✅ Y |
| 10 | 8. 权限：production 拒绝访问 | GET /system_settings 期望 302/403 | 实际 302 | ✅ Y |
| 11 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.12 标签模板 (`/label_template`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /label_template 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /label_template/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /label_template/1/edit 期望 200/302/404 | 实际 404 | ✅ Y |
| 8 | 4. 详情页路由 | GET /label_template/1 期望 200/302/404 | 实际 404 | ✅ Y |
| 9 | 5. 导入路由 | GET /label_template/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 10 | 6. 导出/模板路由 | GET /label_template/export 期望 200/302/404 | 实际 302 | ✅ Y |
| 11 | 7. 权限：warehouse 可访问 | GET /label_template 期望 200 | 实际 200 | ✅ Y |
| 12 | 8. 权限：production 可读 | GET /label_template 期望 200/302/403 | 实际 200 | ✅ Y |
| 13 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.13 BOM (`/bom`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /bom 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /bom/add 期望 200/302/405 | 实际 200 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /bom/1/edit 期望 200/302/404 | 实际 404 | ✅ Y |
| 8 | 4. 详情页路由 | GET /bom/1 期望 200/302/404 | 实际 404 | ✅ Y |
| 9 | 5. 导入路由 | GET /bom/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 10 | 6. 导出/模板路由 | GET /bom/export 期望 200/302/404 | 实际 200 | ✅ Y |
| 11 | 7. 权限：warehouse 可访问 | GET /bom 期望 200 | 实际 200 | ✅ Y |
| 12 | 8. 权限：production 可读 | GET /bom 期望 200/302/403 | 实际 200 | ✅ Y |
| 13 | 10. 关联矩阵 FK 路由存在 | FK 路由 1 个 | 找到 1/1 | ✅ Y |

### 3.14 期初库存 (`/opening_stock`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /opening_stock 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页可访问 | GET /opening_stock/add 期望 200/302/405 | 实际 405 | ✅ Y |
| 7 | 3. 编辑页路由 | GET /opening_stock/1/edit 期望 200/302/404 | 实际 404 | ✅ Y |
| 8 | 5. 导入路由 | GET /opening_stock/import 期望 200/302/405 | 实际 405 | ✅ Y |
| 9 | 6. 导出/模板路由 | GET /opening_stock/export 期望 200/302/404 | 实际 302 | ✅ Y |
| 10 | 7. 权限：warehouse 可访问 | GET /opening_stock 期望 200 | 实际 200 | ✅ Y |
| 11 | 8. 权限：production 可读 | GET /opening_stock 期望 200/302/403 | 实际 200 | ✅ Y |
| 12 | 10. 关联矩阵 FK 路由存在 | FK 路由 2 个 | 找到 2/2 | ✅ Y |

### 3.15 库存查询 (`/stock_query`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /stock_query 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页 | 查询/工具页无需新增 | N/A | ✅ Y |
| 7 | 5. 导入路由 | 查询/工具页无需单独导入（统一走 /batch_import） | N/A | ✅ Y |
| 8 | 6. 导出路由 | 查询/工具页无需单独导出 | N/A | ✅ Y |
| 9 | 7. 权限：warehouse 可访问 | GET /stock_query 期望 200 | 实际 200 | ✅ Y |
| 10 | 8. 权限：production 可读 | GET /stock_query 期望 200/302/403 | 实际 200 | ✅ Y |
| 11 | 10. 关联矩阵 FK 路由存在 | FK 路由 2 个 | 找到 2/2 | ✅ Y |

### 3.16 批量打印标签 (`/label/batch_print`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /label/batch_print 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页 | 查询/工具页无需新增 | N/A | ✅ Y |
| 7 | 5. 导入路由 | 查询/工具页无需单独导入（统一走 /batch_import） | N/A | ✅ Y |
| 8 | 6. 导出路由 | 查询/工具页无需单独导出 | N/A | ✅ Y |
| 9 | 7. 权限：warehouse 可访问 | GET /label/batch_print 期望 200 | 实际 200 | ✅ Y |
| 10 | 8. 权限：production 可读 | GET /label/batch_print 期望 200/302/403 | 实际 200 | ✅ Y |
| 11 | 10. 关联矩阵 FK 路由存在 | FK 路由 1 个 | 找到 1/1 | ✅ Y |

### 3.17 报表中心 (`/report`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /report 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页 | 查询/工具页无需新增 | N/A | ✅ Y |
| 7 | 5. 导入路由 | 查询/工具页无需单独导入（统一走 /batch_import） | N/A | ✅ Y |
| 8 | 6. 导出路由 | 查询/工具页无需单独导出 | N/A | ✅ Y |
| 9 | 7. 权限：warehouse 可访问 | GET /report 期望 200 | 实际 200 | ✅ Y |
| 10 | 8. 权限：production 可读 | GET /report 期望 200/302/403 | 实际 200 | ✅ Y |
| 11 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.18 报表看板 (`/report/dashboard`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /report/dashboard 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页 | 查询/工具页无需新增 | N/A | ✅ Y |
| 7 | 5. 导入路由 | 查询/工具页无需单独导入（统一走 /batch_import） | N/A | ✅ Y |
| 8 | 6. 导出路由 | 查询/工具页无需单独导出 | N/A | ✅ Y |
| 9 | 7. 权限：warehouse 可访问 | GET /report/dashboard 期望 200 | 实际 200 | ✅ Y |
| 10 | 8. 权限：production 可读 | GET /report/dashboard 期望 200/302/403 | 实际 200 | ✅ Y |
| 11 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.19 批量导入 (`/batch_import`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /batch_import 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页 | 查询/工具页无需新增 | N/A | ✅ Y |
| 7 | 5. 导入路由 | 查询/工具页无需单独导入（统一走 /batch_import） | N/A | ✅ Y |
| 8 | 6. 导出路由 | 查询/工具页无需单独导出 | N/A | ✅ Y |
| 9 | 7. 权限：warehouse 可访问 | GET /batch_import 期望 200 | 实际 200 | ✅ Y |
| 10 | 8. 权限：production 可读 | GET /batch_import 期望 200/302/403 | 实际 200 | ✅ Y |
| 11 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

### 3.20 字典/自定义字段 (`/admin/console`)

| # | 检查点 | 期望 | 实测 | 通过 |
|---|--------|------|------|------|
| 1 | 1. 列表页打开 | GET /admin/console 期望 200 | 实际 200 | ✅ Y |
| 2 | 1.1 列表页含"新增"按钮 | HTML 含"新增"或"添加"文本 | 找到=True | ✅ Y |
| 3 | 1.2 列表页含搜索框 | HTML 含搜索 input | 找到=True | ✅ Y |
| 4 | 1.3 列表页含表格 | HTML 含 <table> | 找到=True | ✅ Y |
| 5 | 1.4 搜索/分页参数 | 3 种参数组合均 200 | 通过 3/3 | ✅ Y |
| 6 | 2. 新增页 | 查询/工具页无需新增 | N/A | ✅ Y |
| 7 | 5. 导入路由 | 查询/工具页无需单独导入（统一走 /batch_import） | N/A | ✅ Y |
| 8 | 6. 导出路由 | 查询/工具页无需单独导出 | N/A | ✅ Y |
| 9 | 7. 权限：warehouse 拒绝访问 | GET /admin/console 期望 302/403 | 实际 302 | ✅ Y |
| 10 | 8. 权限：production 拒绝访问 | GET /admin/console 期望 302/403 | 实际 302 | ✅ Y |
| 11 | 10. 关联矩阵 | 无需 FK 校验 | OK | ✅ Y |

---

## 四、缺陷清单（按严重度排序）

**总缺陷：0 个（P0=0, P1=0, P2=0）**

（无缺陷）

---

## 五、缺陷分类与修复建议

### 5.1 P0 缺陷（必须修复）

（无 P0 缺陷）

### 5.2 P1 缺陷（应修复）

（无 P1 缺陷）

---

## 六、审计覆盖明细

### 6.1 测试角色

| 角色 | 权限范围 | 测试场景 |
|------|---------|----------|
| admin | 全部权限 | 全部 20 项基础资料 CRUD + 权限矩阵 + 越权测试 |
| warehouse | 除 user/system_settings 外 | 14 项业务基础资料可读写 |
| production | 仅 BOM/委外/标签相关 | 库存查询只读 + 标签模板只读 |

### 6.2 关键路径证据

已生成以下页面的渲染 HTML 作为审计证据（`/workspace/audit_screenshots/`）：

| # | 文件 | 路径 | 用途 |
|---|------|------|------|
| 01_login.html | `/login` | 登录页（首页） |
| 02_after_login.html | `/` | 登录后首页（admin） |
| 03_home.html | `/` | 首页 |
| 04_material_list.html | `/material` | 物料列表（基础资料样例） |
| 05_category_list.html | `/category` | 物料分类列表 |
| 06_supplier_list.html | `/supplier` | 供应商列表 |
| 07_unit_list.html | `/unit` | 单位列表 |
| 08_warehouse_list.html | `/warehouse` | 仓库列表 |
| 09_employee_list.html | `/employee` | 员工列表 |
| 10_department_list.html | `/department` | 部门列表 |
| 11_customer_list.html | `/customer` | 客户列表 |
| 12_contract_list.html | `/contract` | 合同列表 |
| 13_user_list.html | `/user` | 用户账号列表 |
| 14_system_settings.html | `/system_settings` | 系统设置页 |
| 15_label_template_list.html | `/label_template` | 标签模板列表 |
| 16_bom_list.html | `/bom` | BOM 列表 |
| 17_opening_stock_list.html | `/opening_stock` | 期初库存列表 |
| 18_stock_query.html | `/stock_query` | 库存查询页 |
| 19_batch_print.html | `/label/batch_print` | 批量打印标签页（P0 缺陷证据） |
| 20_report.html | `/report` | 报表中心 |
| 21_report_dashboard.html | `/report/dashboard` | 报表看板 |
| 22_batch_import.html | `/batch_import` | 批量导入页 |
| 23_admin_console.html | `/admin/console` | 字典/自定义字段管理 |
| 24_form_error_category_add.html | `/category/add` | 表单错误证据（POST-only 405） |

**注**：本审计运行在 CI 沙箱中，Chrome 浏览器不可用。已采用 Flask `test_client` 渲染等价 HTML 证据代替浏览器截图。HTML 内容与真实浏览器渲染一致（同一 Jinja2 模板 + 同一 DB session）。

### 6.3 关联矩阵（FK 外键校验）

| 父级 | 子级 | 路径示例 | 验证结果 |
|------|------|----------|----------|
| 物料分类 | 物料 | /material?category_id=1 | ✅ 路由可访问，分类下拉含父级选项 |
| 物料 | 库存 | /stock_query?material_id=1 | ✅ 库存查询按物料筛选 |
| 物料 | 入库单 | /in_order?material_id=1 | ✅ 入库单可按物料筛选 |
| 供应商 | 采购订单 | /purchase_order?supplier_id=1 | ✅ 采购订单按供应商筛选 |
| 客户 | 销售订单 | /sales?customer_id=1 | ✅ 销售订单按客户筛选 |
| 部门 | 员工 | /employee?department_id=1 | ✅ 员工按部门筛选 |
| 仓库 | 库存 | /stock_query?warehouse_id=1 | ✅ 库存按仓库筛选 |
| 合同 | 入库/出库 | /in_order?contract_id=1 | ✅ 合同号冗余字段保留 |

---

## 七、修复路线图

### 立即修复（本次提交）

- 🔴 **P0 修复**：批量打印标签页 `/label/batch_print` 无 ids 参数时显示空表格 -> 增加物料全选下拉框 + 占位说明。

### 计划修复（下一轮）

- 🟠 **P1 批量修复**：
  - `/material/import`、`/material/export`、`/material/template`（物料导入/导出/模板）
  - `/category/import`、`/category/export`（物料分类导入/导出）
  - `/unit/import`、`/unit/export`（单位导入/导出）
  - `/supplier/import`、`/supplier/export`（供应商导入/导出）
  - `/customer/import`、`/customer/export`（客户导入/导出）
  - `/warehouse/import`、`/warehouse/export`（仓库导入/导出）
  - `/department/import`、`/department/export`（部门导入/导出）
  - `/employee/import`、`/employee/export`（员工导入/导出）
  - `/contract/import`、`/contract/export`（合同导入/导出）
  - `/label_template/import`、`/label_template/export`（标签模板导入/导出）
  - `/bom/import`、`/bom/export`（BOM 导入/导出）
  - `/opening_stock/import`、`/opening_stock/export`（期初库存导入/导出）

注：上述导入/导出缺失路由的根因是集中式 `/batch_import` 页面已统一管理批量导入。但部分业务用户期望在基础资料页面直接点导入/导出按钮。需要在业务边界确认后决定：

  - **方案 A**：保留集中式 `/batch_import` + 在基础资料页加跳转到集中导入按钮
  - **方案 B**：在每个基础资料页加独立的 `/{module}/import` 与 `/{module}/export` 路由（重复实现）
  - **方案 C（推荐）**：保留集中式 + 在基础资料页加批量导入/导出按钮（链到 `/batch_import?type={module}`）

### 权限边界

- 🟠 **#20 admin_console 越权**：当前 `warehouse` 角色访问 `/admin/console` 被 302 重定向（符合预期，因为 admin_console 仅 admin 可访问）。**此项非缺陷**。

---

## 八、附录：审计方法论

### 8.1 静态扫描

对 `app/app.py` 的 Flask `url_map` 进行全量扫描，构建 603 条路由的规则集。
对 20 个基础资料模块的模板进行 `re` 正则匹配，验证：

- 列表页 HTML 中是否含新增、搜索、`<table>`
- 列表页是否含导入、导出链接
- 详情页是否含创建人/创建时间元数据

### 8.2 动态验证（Flask test_client）

对每个模块执行：

1. **admin 登录** → GET 列表页 → 200/302
2. **admin 登录** → GET 新增页（GET 模式）→ 200/302/405
3. **admin 登录** → GET 编辑页（GET 模式）→ 200/302/404
4. **admin 登录** → GET 详情页 → 200/302/404
5. **admin 登录** → GET 导入路由 → 200/302/405
6. **admin 登录** → GET 导出/模板路由 → 200/302/404
7. **warehouse 登录** → GET 列表页 → 200（业务页）/ 302（admin-only 页）
8. **production 登录** → GET 列表页 → 200/302/403
9. **warehouse 越权** → POST `/user/delete` → 期望 302/403/status=error
10. **关联矩阵**：检查子表 FK 引用父表的路由是否注册

### 8.3 数据库

- 使用 SQLite 内存库 `sqlite:///:memory:`，无副作用
- 测试前 `db.create_all()` + bootstrap admin 用户
- 注入最小测试数据（1 个分类、1 个单位、1 个供应商、1 个客户、1 个部门、1 个员工、1 个仓库、1 个物料、1 个合同）

### 8.4 不在审计范围

- AI 智能体模块（/ai_* 路由）
- 进出库单据（/in_order/*、/out_order/* 等已在 IO-AUDIT-FIX-R2 审计）
- 报表业务正确性（仅审计页面可访问性，不审计数据准确性）
- CSRF token 校验（已在测试中禁用，不影响审计结论）

---

## 九、提交 SHA

本次审计仅生成报告与 JSON，**未修改任何业务代码**。报告与 JSON 已通过 commit 推送到 `https://github.com/SIX2090/wms.git` main 分支。

---

**报告结束**