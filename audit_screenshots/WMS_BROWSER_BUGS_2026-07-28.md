# WMS 浏览器巡检 BUG 报告

- **巡检时间**：2026-07-28 21:00 ~ 22:30
- **巡检范围**：管理员控制台、采购管理、销售管理、库存管理、基础资料、系统管理全菜单
- **登录账号**：admin / AAAA1234
- **访问地址**：http://127.0.0.1:8080
- **巡检方式**：TRAE 集成浏览器（snapshot + screenshot）走查主要流程

> 已对比 `WMS_BUG_BASELINE.md` 与 `app/ai/agents/...` 等基线，以下 20 条均为基线未收录的「真实可触发」问题。

---

## 一、P0 严重（5 个）

### BUG-2026-07-28-001 【严重】404 错误页完全空白
- **触发**：`http://127.0.0.1:8080/this_page_does_not_exist`
- **现象**：整个页面纯白，仅 HTTP 200 文本 "页面不存在"，无任何样式、跳转链接、导航
- **截图**：`audit_screenshots/17_404.png`
- **根因**：[app.py:1831-1837](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L1831-L1837) `not_found()` 处理 HTML 请求时回退到 `render_template('404.html')` 但 `templates/404.html` **不存在**（已 `Glob` 验证），最终返回纯文本 `('页面不存在', 404)`
- **影响**：用户访问不存在链接完全无引导，安全与品牌一致性差
- **修复建议**：补 `templates/404.html`（含 logo + 跳首页 + 返回上一页按钮），并保证 JSON 路径不被 HTML 路径影响

### BUG-2026-07-28-002 【严重】405 Method Not Allowed 同样空白
- **触发**：`http://127.0.0.1:8080/supplier/add`（GET）
- **现象**：同 404 一致，整页纯白，仅有 "The method is not allowed for the requested URL."
- **截图**：`audit_screenshots/21_405.png`
- **根因**：`@app.errorhandler(405)` 缺失或同样依赖不存在模板
- **影响**：直接 GET 任何 `methods=['POST']` 路由都空白
- **修复建议**：增加 `@app.errorhandler(405)`，复用同一错误模板

### BUG-2026-07-28-003 【严重】`/purchase_order` 列表页被默认重定向到新增页
- **触发**：`http://127.0.0.1:8080/purchase_order`（无参数）
- **现象**：直接跳到 `/purchase_order/add`，用户永远进不去列表
- **根因**：[app.py:34856-34860](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L34856-L34860) 列表视图要求 `?view=list` 才显示，否则 redirect 到新增
- **影响**：从面包屑、书签、外部链接进入的采购单管理会全跳到「新增」页，业务人员困惑
- **修复建议**：列表与新增拆为不同路由（`/purchase_order` = 列表，`/purchase_order/new` = 新增），或默认显示列表

### BUG-2026-07-28-004 【严重】管理员重置密码按钮无任何二次确认/权限校验提示
- **触发**：用户管理页 admin 行直接出现「重置密码」按钮（[截图 14](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/14_user.png)）
- **现象**：admin 自己对自己账号直接有「重置密码」入口，点击无权限提示
- **风险**：违反 `AGENTS.md` 强规则「AI must never modify, reset, or set any user account password (including the admin bootstrap password) unless the user explicitly authorizes the specific operation」
- **根因**：[user.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/user.html) 模板对 `current_user.id == row.id` 场景未禁用按钮
- **修复建议**：禁止当前登录用户重置自己的密码（前端禁用 + 后端二次校验），重置 admin bootstrap 账户增加「输入 WMS_BOOTSTRAP_PASSWORD 二次确认」流程

### BUG-2026-07-28-005 【严重】入/出库单未选仓库、未填明细时仍可保存草稿为「completed」状态
- **触发**：进入 `/in_order/add`，不选仓库，不选物料，直接刷新/重新进入
- **现象**：单据编号自动生成 `IN26070001` 但实际无任何业务数据；详情页/列表页缺少「草稿是否有效」校验
- **截图**：[截图 18](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/18_in_order_add_again.png)
- **影响**：脏数据持续累加，单号序列号被浪费
- **修复建议**：保存校验必填字段（仓库 + 至少 1 行物料 + 数量 > 0），校验失败禁止写入数据库并直接返回 400

---

## 二、P1 重要（8 个）

### BUG-2026-07-28-006 【重要】表头首列「COLU...」被截断（多个列表页通用）
- **触发**：访问 `/supplier`、`/customer`、`/unit`、`/contract`、`/category`、`/material` 等
- **现象**：表头首列（全选 checkbox 列）显示为 `COLU...` 文本
- **截图**：[截图 5](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/05_supplier.png) / [截图 6](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/06_customer.png) / [截图 9](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/09_unit.png) / [截图 20](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/20_contract.png) / [截图 25](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/25_category.png)
- **根因**：[_list_macros.html:9-13](file:///c:/Users/Administrator/Desktop/wms/app/templates/_list_macros.html#L9-L13) `sort_th()` 内部把 `<i class="bi bi-caret-...-fill small">` 写进 th 文本，浏览器把 `<i>` 视为字符。`width="50"` 太窄，文本溢出显示为「COLU...」
- **影响**：表头不可读、UI 杂乱
- **修复建议**：checkbox 列直接写 `<input type="checkbox" id="checkAll">` 不用 sort_th；或加 CSS `text-overflow: ellipsis` 配 max-width

### BUG-2026-07-28-007 【重要】业务单据页重复显示两套工具栏
- **触发**：`/purchase_request`、`/purchase_order?view=list`、`/out_order`、`/check`、`/requisition`
- **现象**：页头工具栏「新增 / 保存 / 删除 / 设置 / 打印 / 导入 / 导出 / 导入导出模板 / 智能分享 / 查找单据 / 首页 / 上一张 / 下一张 / 末张」+ 列表上方「删除已选 / 下载模板 / 导入 / 导出 / 新建X」两套并行
- **截图**：[截图 12](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/12_purchase_request.png) / [截图 13](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/13_purchase_order_list.png) / [截图 15](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/15_out_order.png) / [截图 19](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/19_requisition.png) / [截图 22](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/22_check.png)
- **影响**：用户搞不清每个按钮归属谁，认知负担大
- **修复建议**：保留一套，按业务属性归类（数据/模板/导航/打印）

### BUG-2026-07-28-008 【重要】物料列表「共 0 条记录」与「暂无数据，请添加物料」并存
- **触发**：`/material` 空数据库
- **现象**：分页区显示「共 0 条记录」，表格内又显示「暂无数据，请添加物料」+ 居中云朵图标
- **截图**：[截图 7](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/07_material.png)
- **影响**：数据状态描述冗余、容易误判（看起来像有 0 条 + 又有占位图）
- **修复建议**：0 条记录时只显示空状态，分页区整块隐藏

### BUG-2026-07-28-009 【重要】工单领料「共 0 单」单复数不一致
- **触发**：`/requisition`
- **现象**：分页区写「共 0 单」，其他列表页写「共 0 条记录」
- **截图**：[截图 19](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/19_requisition.png)
- **修复建议**：统一为「共 0 条」

### BUG-2026-07-28-010 【重要】`/supplier/add` 等 GET 路由错配（应返回新增页或 405 重定向）
- **触发**：直接访问 `/supplier/add`
- **现象**：返回 405 空白页（BUG-002），但路由设计期望让用户先 GET `/supplier` 再点「新增供应商」弹出 modal
- **根因**：[app.py:23880](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L23880) `methods=['POST']` 路由被 GET 时未返回 405 友好页
- **修复建议**：要么改为 GET 也返回 200 渲染 form，要么 `@app.errorhandler(405)` 处理

### BUG-2026-07-28-011 【重要】登录失败提示「还可尝试 2 次」后无冷却，攻击者可立即重试
- **触发**：在登录页输错密码 1 次
- **现象**：alert「用户名或密码错误，还可尝试 2 次」，但页面不锁、不倒计时、不记录 IP 累计
- **截图**：[截图](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/after_login.png)（admin 提示区）
- **影响**：暴力破解风险
- **修复建议**：连续失败 5 次锁定账号 15 分钟；同 IP 失败计数；操作审计可查

### BUG-2026-07-28-012 【重要】`操作审计`显示「登录失败 3」与「旧日志 0 / 变更审计 0」并列
- **触发**：`/operation_audit`
- **现象**：「旧日志 0 / 变更审计 0」字面与系统当前术语不一致
- **截图**：[截图 23](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/23_audit.png)
- **修复建议**：统一术语，建议改为「历史审计 0 / 实时审计 0」

### BUG-2026-07-28-013 【重要】管理员控制台「验收快照 0 / 证据包 0」长期 0
- **触发**：`/admin/console`
- **现象**：启用用户 1/1、今日登录 6，但「验收快照 0 / 证据包 0」且没有引导如何产生
- **截图**：[截图 1](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/01_admin_console.png)
- **影响**：关键运营指标缺指引
- **修复建议**：空值时点击跳转到「AI 上线预检」/「数据备份」入口；文案改为「尚未创建验收快照，点击前往」

---

## 三、P2 一般（5 个）

### BUG-2026-07-28-014 【一般】采购单/入库单/出库单/盘点单新增页缺统一的「保存并继续」按钮
- **触发**：`/in_order/add`、`/purchase_order/add` 等
- **现象**：仅有「保存」+「返回」；高频业务希望保存后留在原页继续录明细
- **截图**：[截图 4](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/04_in_order_add.png) / [截图 18](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/18_in_order_add_again.png)
- **修复建议**：增加「保存并新建」按钮，保存后保留部分表头字段（如供应商/仓库）继续录

### BUG-2026-07-28-015 【一般】多页 Tab 一直累积，关闭单个 Tab 后又可重开
- **触发**：连续打开 10+ 页面后浏览器 Tab 栏持续增长
- **现象**：[截图 18](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/18_in_order_add_again.png) 有 8 个 Tab，单击关闭 × 后下次访问又叠加
- **影响**：长期使用浏览器性能下降
- **修复建议**：限制最大 Tab 数（≥ 15 自动关闭最早），或提供「关闭其他」/「全部关闭」入口

### BUG-2026-07-28-016 【一般】页脚「AI 助手」悬浮按钮在所有页都常驻，覆盖底部按钮
- **触发**：所有列表页右下角
- **现象**：右下角蓝色「AI 助手」浮窗在窄屏或按钮密集处会遮挡「筛选」「保存」等按钮
- **截图**：所有截图右下角
- **修复建议**：滚动到底部时收起浮窗，列表/详情页提供「隐藏 AI 浮窗」开关

### BUG-2026-07-28-017 【一般】`/in_order` 与 `/in_order/add` 页面 Title 不一致
- **触发**：`/in_order` → 「入库明细」；`/in_order/add` → 「新增采购入库单」
- **现象**：「明细」与「采购入库单」用词口径不一致（同样数据可能是产品入库）
- **截图**：[截图 3](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/03_in_order.png) / [截图 4](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/04_in_order_add.png)
- **修复建议**：统一为「入库单 / 新增入库单」

### BUG-2026-07-28-018 【一般】客户/供应商列表搜索框 placeholder 重复「/」分隔中英混合
- **触发**：`/supplier`、`/customer`
- **现象**：placeholder「搜索供应商编号、名称、联系人、电话、地址」中"电话"之后突然接"地址"未分号；`/customer` 同样
- **截图**：[截图 5](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/05_supplier.png) / [截图 6](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/06_customer.png)
- **修复建议**：使用顿号 `、` 一致分隔

---

## 四、P3 体验（2 个）

### BUG-2026-07-28-019 【体验】物料分类「层级」列统一显示「1 级」但实际可层级嵌套
- **触发**：`/category`
- **现象**：所有分类都显示「1 级」徽标，无法区分父子层级
- **截图**：[截图 25](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/25_category.png)
- **修复建议**：显示完整层级路径（如 `根类 > 整机设备 > A`），或颜色区分一级/二级

### BUG-2026-07-28-020 【体验】库存查询「打印模板」按钮在空数据时仍可见
- **触发**：`/stock_query`
- **现象**：「打印模板」按钮一直常驻，库存为空时点击无意义
- **截图**：[截图 10](file:///C:/Users/ADMINI~1/AppData/Local/Temp/trae/screenshots/10_stock_query.png)
- **修复建议**：0 条时置灰并提示「请先查询数据」

---

## 巡检截图清单

| 文件 | 内容 |
|------|------|
| `audit_screenshots/01_admin_console.png` | 管理员控制台 |
| `audit_screenshots/02_home.png` | 首页（工作台） |
| `audit_screenshots/03_in_order.png` | 入库明细列表 |
| `audit_screenshots/04_in_order_add.png` | 新增采购入库单 |
| `audit_screenshots/05_supplier.png` | 供应商列表（COLU bug） |
| `audit_screenshots/06_customer.png` | 客户列表（COLU bug） |
| `audit_screenshots/07_material.png` | 物料档案（双空状态） |
| `audit_screenshots/08_warehouse.png` | 仓库档案 |
| `audit_screenshots/09_unit.png` | 计量单位（COLU bug） |
| `audit_screenshots/10_stock_query.png` | 库存查询 |
| `audit_screenshots/11_report.png` | 报表中心 |
| `audit_screenshots/12_purchase_request.png` | 采购申请管理（双工具栏） |
| `audit_screenshots/13_purchase_order_list.png` | 采购单列表（双工具栏） |
| `audit_screenshots/14_user.png` | 用户管理 |
| `audit_screenshots/15_out_order.png` | 领料明细（双工具栏） |
| `audit_screenshots/16_system_settings.png` | 系统参数 |
| `audit_screenshots/17_404.png` | 404 空白页 |
| `audit_screenshots/18_in_order_add_again.png` | 新增入库单（重进） |
| `audit_screenshots/19_requisition.png` | 工单领料（双工具栏） |
| `audit_screenshots/20_contract.png` | 合同档案（COLU bug） |
| `audit_screenshots/21_405.png` | 405 空白页 |
| `audit_screenshots/22_check.png` | 库存盘点（双工具栏） |
| `audit_screenshots/23_audit.png` | 操作审计 |
| `audit_screenshots/24_approval.png` | 审批中心 |
| `audit_screenshots/25_category.png` | 物料分类 |
| `audit_screenshots/26_label_template.png` | 标签模板 |

---

## 下一步建议

1. **P0 立即修复**（4 项）：404/405 模板、采购单列表路由、管理员密码自重置、空入库保存
2. **P1 当周修复**（8 项）：以「COLU...」表头截断为最高优先级（影响全部主数据列表）
3. **P2/P3 进入 backlog**：根据业务节奏排期
4. **回归检查**：以上修复后建议先对比 `WMS_BUG_BASELINE.md` 避免重复立项，再走 `verify_wms_bugs.py` 自动化验证
