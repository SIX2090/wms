# WMS 浏览器 20 个 BUG 详细修复提示词（BUGFIX_PROMPT.md）

> 配套基线报告：[WMS_BROWSER_BUGS_2026-07-28.md](WMS_BROWSER_BUGS_2026-07-28.md)
>
> 巡检时间：2026-07-28 21:00 ~ 22:30
> 登录账号：admin / AAAA1234
> 访问地址：http://127.0.0.1:8080

---

## 0. 通用修复流程（每条 BUG 必走）

1. **读 BUG 段**：先读「现象 / 根因 / 截图」三段，确认重现路径；如代码位置给出具体行号，先 `Read` 该行附近 ±40 行上下文。
2. **最小改动**：只动与 BUG 直接相关的代码 / 模板；不夹带其它重构。
3. **遵守规则**：
   - 任何账号密码、admin bootstrap 密码严禁自动修改、随机生成、强制重置（AGENTS.md 强规则）。
   - 已完成入库单禁止直接删除；必须先反提交回草稿后才能删。
   - 分支策略：仅在 `main` 上提交，禁止 `feature/*` `fix/*` 等其它分支。
   - 提交粒度：每个 BUG 单独一次 commit（`fix: BUG-2026-07-28-XXX <一句话>`）。
4. **本地回归**：使用 `python` 起本地 waiters（已运行 PID 18096），必要时重启；用 TRAE 浏览器 snapshot 走查修复后的页面。
5. **截图归档**：修复验证截图保存到 `audit_screenshots/fix_<bug-id>_<seq>.png`。
6. **推送**：`git push origin main` 后 `git status` 确认 working tree clean、`git log -1` 确认 commit 已上 main。
7. **基线更新**：把已修复的 BUG 同步到 `WMS_BUG_BASELINE.md`（标 `已修复并纳入回归`）。

---

## 1. P0-001：404 错误页完全空白 ✅ 已修复

- **现象**：`http://127.0.0.1:8080/this_page_does_not_exist` → 整页纯白，仅文本「页面不存在」。
- **根因**：[app.py `not_found()`](file:///c:/Users/Administrator/Desktop/wms/app/app.py) 处理 HTML 请求时回退到 `render_template('404.html')` 但 `templates/404.html` 不存在；最终走纯文本。
- **修复**：
  1. 新建 `app/templates/404.html`（含 logo + 「返回首页」「返回上一页」按钮 + 显示 `request.path`）。
  2. 在 `app.py` 新增 `@app.errorhandler(405)`（参见 BUG-002），并把 404 handler 简化为 `return render_template('404.html'), 404`。
  3. 启动脚本：[apply_bug_001.py](file:///c:/Users/Administrator/Desktop/wms/audit_screenshots/apply_bug_001.py) + [apply_bug_001_templates.py](file:///c:/Users/Administrator/Desktop/wms/audit_screenshots/apply_bug_001_templates.py)
- **验证**：浏览器访问 `/this_page_does_not_exist` → 看到蓝色 404 卡片，「返回首页」可点。
- **commit**：`fix(BUG-001/002): add 404/405 error pages and handlers`

---

## 2. P0-002：405 Method Not Allowed 同样空白 ✅ 已修复

- **现象**：`http://127.0.0.1:8080/supplier/add`（GET）→ 整页纯白。
- **根因**：`@app.errorhandler(405)` 缺失。
- **修复**：
  1. 在 `app.py` 紧跟 404 handler 之后新增 `@app.errorhandler(405) def method_not_allowed(e)`，渲染 `templates/405.html`。
  2. 新建 `app/templates/405.html`（橙色 405 卡片 + 「返回首页」「返回上一页」）。
  3. JSON 路径返回 `{'status':'error','msg':'请求方式不被允许'}` + 状态码 405。
- **验证**：浏览器访问 `/supplier/add`（GET） → 看到橙色 405 卡片。
- **commit**：与 BUG-001 合并。

---

## 3. P0-003：`/purchase_order` 列表页被默认重定向到新增页

- **现象**：`http://127.0.0.1:8080/purchase_order` 无参数 → 302 → `/purchase_order/add`；用户永远进不去列表。
- **根因**：[app.py:34863-34867](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L34863-L34867)
  ```python
  @app.route('/purchase_order')
  def purchase_order_list():
      if request.args.get('view') != 'list':
          return redirect(url_for('purchase_order_add_page'))
  ```
  设计本意是 `?view=list` 才显示列表，否则跳到新增。但书签、面包屑直接 `/purchase_order` 永远到不了列表。
- **修复**：
  1. 删除 `if request.args.get('view') != 'list': return redirect(...)` 这一段，让 `/purchase_order` 默认渲染列表模板 `purchase_order.html`。
  2. `/purchase_order/add` 维持现状（指向 `purchase_order_add_page`）。
  3. 若有 URL 反向引用 `?view=list`，保留兼容：用 `request.args.get('view') in (None, 'list')` 视为列表；`'new' / 'add'` 才跳。
- **验证**：
  - `GET /purchase_order` → 直接 200 渲染列表（不再 302）。
  - `GET /purchase_order?view=add` → 跳 `/purchase_order/add`。
  - `GET /purchase_order/add` → 仍为新增页。
- **commit**：`fix(BUG-003): /purchase_order 默认显示列表，不再强制跳新增`

---

## 4. P0-004：admin 重置密码按钮无二次确认/权限校验

- **现象**：[user.html:101-104](file:///c:/Users/Administrator/Desktop/wms/app/templates/user.html#L101-L104) 自己的 admin 行直接出现「重置密码」按钮，点击无任何二次确认。
- **风险**：违反 AGENTS.md 强规则「AI must never modify, reset, or set any user account password unless the user explicitly authorizes」。
- **修复**：
  1. 模板层：`{% if user.id == current_user.id %}<button class="btn btn-sm btn-outline-warning" disabled title="不能重置当前登录账号的密码"><i class="bi bi-key"></i> 重置密码</button>{% else %}<button class="btn btn-sm btn-outline-warning" onclick='resetPassword(...)'>...`。
  2. 后端 [`reset_user_password()`](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L6796) 增加：若 `user_id == current_user.id` 或目标用户 `role == 'admin' && os.environ.get('WMS_BOOTSTRAP_PASSWORD','') == ''` → 返回 `{'status':'error','msg':'重置管理员密码需要输入 WMS_BOOTSTRAP_PASSWORD 二次确认'}`。
  3. 二次确认 UI：弹窗增加「请再次输入 WMS_BOOTSTRAP_PASSWORD」输入框；JS 提交时附带 `bootstrap_pwd`；后端比对 `os.environ.get('WMS_BOOTSTRAP_PASSWORD')` 匹配才放行。
  4. 严格禁止 AI 在脚本里 set / 改任何 `WMS_BOOTSTRAP_PASSWORD` 或用户密码。
- **验证**：
  - 登录 admin → 用户管理 → 自己的行：重置密码按钮置灰 + tooltip「不能重置当前登录账号的密码」。
  - 用 `AAAA1234` 重置非自身用户 → 成功。
  - 用 `AAAA1234` 重置 admin bootstrap 账号 → 后端拒绝并 toast「重置管理员密码需要二次确认」。
- **commit**：`fix(BUG-004): 禁止 admin 自助重置密码 + admin 目标二次确认`

---

## 5. P0-005：入/出库单未选仓库/未填明细时仍可保存为「completed」状态

- **现象**：进入 `/in_order/add`，不选仓库、不选物料，刷新后单号已生成 `IN26070001`，但 `items` 为空。
- **根因**：[`add_in_order()` JSON 分支](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L24894-L24947) 校验了 `items` 非空 + quantity > 0，但表单分支（`else`）只对 `order_id` 为空时返回「入库单至少需要一条明细」；新单 order_id 仍为 None 时直接放行。
- **修复**：
  1. 在 `add_in_order()` 入口增加「必填校验」：
     - `warehouse` 必填
     - `supplier_id` / `customer_id` 视业务类型必填
     - `items_data` 必须非空 + 每行 material_code 必填 + quantity > 0
     - 任一失败：`return jsonify({'status':'error','msg':'<具体错误>'}), 400`
  2. 同样规则同步到 `out_order_add` / `adjustment_add` / `transfer_add` / `check_add`（共用 helper `_validate_order_business_required()`）。
  3. 详情页/列表页加载空单：弹 toast「该单据明细为空，请补充」并禁用「完成」按钮。
- **验证**：
  - 不选仓库直接保存 → 后端 400「请选择仓库」。
  - 选仓库不选物料保存 → 400「至少需要一条明细」。
  - 正常保存 → 200 success。
- **commit**：`fix(BUG-005): 入库/出库单保存时强制校验仓库与明细必填`

---

## 6. P1-006：表头首列「COLU...」被截断

- **现象**：`/supplier` `/customer` `/unit` `/contract` `/category` `/material` 等多个列表页，表头首列（全选 checkbox 列）显示为 `COLU...`。
- **根因**：[supplier.html:47](file:///c:/Users/Administrator/Desktop/wms/app/templates/supplier.html#L47) 等多页都写：
  ```html
  <th width="50"><input type="checkbox" id="checkAll"></th>
  ```
  `width="50"` 太窄，部分模板内同时存在 `<colgroup>` 或 `cb-resizable-table` 样式把列宽压到 30-40px；浏览器在缺少 alt/title 的情况下用 `COLU...` 兜底提示列可调整。
- **修复**：
  1. 在 `app/templates/_list_macros.html` 新增 `{% macro check_th(width=50) -%}<th class="cb-check-col" width="{{ width }}"><input type="checkbox" class="check-all"></th>{%- endmacro %}`。
  2. 全量替换 `<th width="50"><input type="checkbox" id="checkAll"></th>` 为 `{{ check_th() }}`。
  3. base.html CSS 增加：
     ```css
     .cb-check-col { width: 50px; min-width: 50px; max-width: 50px; text-align: center; }
     .cb-check-col input[type=checkbox] { cursor: pointer; }
     ```
- **涉及文件**（需逐一替换的列表）：
  - supplier.html / customer.html / unit.html / contract.html / category.html / material.html / warehouse.html / employee.html / department.html / user.html / bom.html / opening_stock.html / label_template.html / purchase_request.html / purchase_order.html / out_order.html / requisition.html / check.html / sales_order.html / transfer.html / subcontract.html / stock_query.html 等 22+ 文件
- **验证**：访问 `/supplier` 等 6+ 列表页 → 表头第一列变为 50px 居中 checkbox，不再出现 `COLU...`。
- **commit**：`fix(BUG-006): 列表页表头首列增加 check_th 宏并修复 COLU 截断`

---

## 7. P1-007：业务单据页重复显示两套工具栏

- **现象**：`/purchase_request` `/purchase_order?view=list` `/out_order` `/check` `/requisition` 等页面同时存在页头工具栏（新增/保存/删除/设置/打印/导入/导出/模板/分享/查找/首页/上一张/下一张/末张）和列表上方「删除已选/下载模板/导入/导出/新建X」两套并行。
- **根因**：业务单据页模板顶部继承自 `base.html` 的 `.page-header` 自动渲染所有 toolbar 按钮；列表模板又自己重复渲染 toolbar。
- **修复**：
  1. 抽取 `{% block top_toolbar %}{% endblock %}`；列表页只保留「新建 X / 删除已选 / 导入 / 导出 / 模板 / 查找」。
  2. 详情/编辑页只保留「保存 / 取消 / 打印 / 分享 / 上一张 / 下一张 / 末张 / 返回列表」。
  3. 每个 list 模板顶部删除重复的 toolbar div；只在 list 头部保留「新建X」+「删除已选」+「导入导出模板」三组。
  4. 涉及页面：purchase_request.html / purchase_order.html / out_order.html / check.html / requisition.html / transfer.html / adjustment.html / after_sale_out.html / subcontract.html / sales_order.html / in_order.html。
- **验证**：访问上述 5+ 列表页 → 只看到 1 套工具栏。
- **commit**：`fix(BUG-007): 业务单据页统一一套工具栏，去除重复渲染`

---

## 8. P1-008：物料列表「共 0 条记录」与「暂无数据」并存

- **现象**：`/material` 空数据库 → 分页区显示「共 0 条记录」，表格内又显示「暂无数据，请添加物料」+ 居中云朵图标。
- **根因**：[`pager()` 宏](file:///c:/Users/Administrator/Desktop/wms/app/templates/_list_macros.html#L102) 在 `pagination.total > 0` 才输出，但空表模板另渲染了「暂无数据」div；两套独立条件，没互斥。
- **修复**：
  1. 修 `pager()`：当 `pagination.total == 0` 时返回空字符串（已生效，但要再确认）。
  2. 列表模板空数据分支：用 `{% if pagination.total == 0 %}` 整块包裹「暂无数据」div，**不要再渲染分页**。
  3. material.html 等同时含分页 + 空数据的页面，删除 pager 调用或加 `{% if pagination.total > 0 %}{{ pager(...) }}{% endif %}`。
- **验证**：`/material` 空库 → 只看到「暂无数据」+ 云朵图标；分页区消失。
- **commit**：`fix(BUG-008): 空数据列表统一只渲染「暂无数据」占位`

---

## 9. P1-009：工单领料「共 0 单」单复数不一致

- **现象**：`/requisition` 分页区写「共 0 单」，其他列表写「共 0 条记录」。
- **根因**：[requisition.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/requisition.html) 手工写死「共 {{ pagination.total }} 单」，未走 `pager()` 宏。
- **修复**：
  1. 把 requisition.html 的分页手工 div 替换为 `{{ pager(pagination, 'requisition_list', base_kwargs=...) }}`。
  2. 同时检查 subcontract.html / sales_order.html / check.html 等是否也手写了「单」/「条」差异。
- **验证**：`/requisition` 空数据 → 显示「共 0 条，每页 [select] 条」，与其他列表统一。
- **commit**：`fix(BUG-009): 统一列表分页区文案为「共 N 条」`

---

## 10. P1-010：`/supplier/add` 等 GET 路由错配

- **现象**：直接访问 `/supplier/add`（GET）→ 405 空白页（已被 BUG-002 修复成 405 卡片）。
- **根因**：[app.py](file:///c:/Users/Administrator/Desktop/wms/app/app.py) `add_supplier()` 是 `methods=['POST']`；GET 该路径 → 405。
- **修复**：
  - 方案 A（推荐，保持路由不变）：继续依赖 BUG-002 的 405 卡片。
  - 方案 B：把 `methods=['POST']` 改为 `methods=['GET', 'POST']`；GET 渲染 `supplier_add.html` 并弹出 modal。✅ 选用 B。
  - 涉及路径：`/supplier/add` `/customer/add` `/unit/add` `/category/add` `/material/add` `/warehouse/add` 等 10+ 基础资料 add 路由。
  - 同时 `[B-002]` 的 405 卡片保留，作为兜底（防其它非预期 POST/GET 不匹配）。
- **验证**：`GET /supplier/add` → 弹出新增供应商 modal 而不是 405。
- **commit**：`fix(BUG-010): 基础资料 add 路由同时支持 GET/POST`

---

## 11. P1-011：登录失败提示「还可尝试 2 次」后无冷却/无 IP 累计

- **现象**：登录页输错 1 次密码 → alert「用户名或密码错误，还可尝试 2 次」，但页面不锁、不倒计时、不记录 IP 累计。
- **根因**：[`login()`](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L6206-L6314) 后端 `increment_failed_count()` 已支持「账号 + IP 双重锁定」，但前端没有：
  1. 不显示倒计时
  2. 锁定中允许再次点登录（应置灰按钮）
  3. 同一 IP 失败次数不累计（后端有 `login_ip_failed_count` 但没暴露给前端）
- **修复**：
  1. `login()` 锁定分支 `423` 返回时额外塞 `lock_remaining` 到 `flash` 信息：「账号已锁定，请 15 分钟后再试（剩余 14 分钟 32 秒）」。
  2. `login.html` 表单锁定中（通过 `flash` 包含「已锁定」关键字检测）：登录按钮 `disabled`，密码框 `readonly`，加 60s 自动倒计时刷新。
  3. JS 增加 `setInterval` 每 60s 检查 `data-lock-until`；到点移除 disabled。
  4. 同一 IP 失败 `>= 3` 次：在登录页底部加一行提示「本 IP 已失败 N 次，连续 5 次将锁定 15 分钟」。
- **验证**：
  - 输错 1 次 → 「还可尝试 4 次」+ 显示 IP 累计。
  - 输错 5 次 → 按钮置灰 + 倒计时 15:00 → 00:00 自动解除。
  - 重新正确登录 → 锁定清空。
- **commit**：`fix(BUG-011): 登录页增加失败次数、IP 累计与锁定倒计时`

---

## 12. P1-012：操作审计「旧日志 0 / 变更审计 0」术语不一致

- **现象**：`/operation_audit` 显示「旧日志 0 / 变更审计 0」与系统术语不匹配。
- **根因**：[operation_audit.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/operation_audit.html) 直接硬编码「旧日志」「变更审计」。
- **修复**：
  1. 把「旧日志」改为「历史审计」（对应 `OperationLog` 表的旧实现）。
  2. 把「变更审计」改为「实时审计」（对应 `OperationAudit` 表的新实现）。
  3. 同时给两个统计卡加 `title` tooltip 解释含义。
- **验证**：`/operation_audit` → 看到「历史审计 0 / 实时审计 0」。
- **commit**：`fix(BUG-012): 操作审计卡片文案统一为「历史/实时审计」`

---

## 13. P1-013：管理员控制台「验收快照 0 / 证据包 0」长期 0 无引导

- **现象**：`/admin/console` 显示「验收快照 0 / 证据包 0」且无引导如何产生。
- **根因**：[admin_console.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/admin_console.html) 硬编码计数，没有「跳转生成」入口。
- **修复**：
  1. 空值时把卡片改为可点击的「引导卡」：「尚未创建验收快照，点击前往 AI 上线预检」 → 跳转 `/ai_prelaunch`。
  2. 「证据包」同样 → 跳 `/backup`。
  3. 已创建时维持原数字显示。
- **验证**：`/admin/console` → 「验收快照」卡变为可点击引导。
- **commit**：`fix(BUG-013): 管理员控制台零值卡片增加引导跳转`

---

## 14. P2-014：采购/入库/出库/盘点新增页缺统一的「保存并新建」按钮

- **现象**：`/in_order/add` 等仅有「保存」「返回」；高频业务希望保存后留在原页继续录明细。
- **根因**：[in_order_add.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/in_order_add.html) 等模板的 footer 只有 save + return。
- **修复**：
  1. 在每个 form 模板的 footer 增加「保存并新建」按钮：
     ```html
     <button class="btn btn-outline-primary" type="button" onclick="saveAndNew(this)">保存并新建</button>
     ```
  2. JS `saveAndNew(btn)`：复用现有 save 流程，保存成功后 `location.href = window.location.pathname + '?keep=1&supplier_id=...'`。
  3. 后端 `*_add_page()` 接收 `keep=1` 参数：保留 supplier_id/customer_id/warehouse 等表头字段继续渲染。
- **验证**：
  - `/in_order/add` → 填表保存并新建 → 跳回 `/in_order/add?keep=1&supplier_id=2&warehouse=W01` → 表头保留。
- **commit**：`fix(BUG-014): 新增单据页增加「保存并新建」按钮 + keep 参数`

---

## 15. P2-015：多页 Tab 一直累积

- **现象**：连续打开 10+ 页面后浏览器 Tab 栏持续增长，关闭单个 Tab 后下次访问又叠加。
- **根因**：[base.html:2476-2477](file:///c:/Users/Administrator/Desktop/wms/app/templates/base.html#L2476-L2477) `.tab-workspace` JS `WmsTabs.open()` 永远追加，无最大数限制、无 LRU 关闭。
- **修复**：
  1. 在 `WmsTabs.open()` 里加：`if (openCount >= 15) { closeOldest(); }`
  2. Tab 栏右键增加「关闭其他 / 全部关闭」菜单。
  3. `localStorage.wmsTabs` 持久化 + 启动时校验：超过 15 个则丢弃最旧。
- **验证**：开 16 个 Tab → 第 16 个打开时第一个自动关闭。
- **commit**：`fix(BUG-015): Tab 栏增加最大数限制与「关闭其他/全部」菜单`

---

## 16. P2-016：AI 助手悬浮按钮覆盖底部

- **现象**：所有列表页右下角蓝色「AI 助手」浮窗遮挡「筛选」「保存」按钮。
- **根因**：[base.html:2502](file:///c:/Users/Administrator/Desktop/wms/app/templates/base.html#L2502) `<button class="ai-assistant-button">` 固定 `position: fixed; bottom: 20px; right: 20px;`。
- **修复**：
  1. CSS：滚动到底部（`scrollY + innerHeight >= scrollHeight - 80`）时 `ai-assistant-button { transform: translateY(120%); opacity: 0.3; }`。
  2. 用户可点 AI 助手左上角「×」临时收起（localStorage 记忆 `aiFabHidden`）。
  3. 不再修改默认定位。
- **验证**：
  - 列表页滚动到底 → AI 浮窗自动半隐藏。
  - 点关闭 → 不再出现直到刷新重置。
- **commit**：`fix(BUG-016): AI 助手悬浮按钮增加滚动收起与可隐藏开关`

---

## 17. P2-017：`/in_order` 与 `/in_order/add` Title 不一致

- **现象**：`/in_order` → 「入库明细」；`/in_order/add` → 「新增采购入库单」；用词口径不一致。
- **根因**：[in_order.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/in_order.html) 写 `{% block title %}入库明细{% endblock %}`；in_order_add.html 写 `{% block title %}新增采购入库单{% endblock %}`。
- **修复**：
  1. 统一为「入库单 / 新增入库单」。
  2. page-header h2 也同步：`h2` 改 `<i class="bi bi-box-arrow-in-down"></i> 入库单` / `<i class="bi bi-plus-circle"></i> 新增入库单`。
- **验证**：`/in_order` → 浏览器 title 「入库单 - 仓库管理系统」；`/in_order/add` → 「新增入库单 - 仓库管理系统」。
- **commit**：`fix(BUG-017): 入库单/出库单/采购单等列表与新增页 Title 统一`

---

## 18. P2-018：客户/供应商搜索框 placeholder 重复「/」分隔中英混合

- **现象**：`/supplier` placeholder「搜索供应商编号、名称、联系人、电话、地址」电话与地址无顿号。
- **根因**：[supplier.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/supplier.html) 与 customer.html placeholder 写错。
- **修复**：
  1. supplier: `placeholder="搜索供应商编号、名称、联系人、电话、地址"` 改为「搜索供应商：编号 / 名称 / 联系人 / 电话 / 地址」或「搜索供应商编号、名称、联系人、电话、地址」（顿号一致）。
  2. customer: 同上。
- **验证**：`/supplier` → 看到「搜索供应商编号、名称、联系人、电话、地址」。
- **commit**：`fix(BUG-018): 客户/供应商搜索框 placeholder 统一顿号分隔`

---

## 19. P3-019：物料分类「层级」列统一显示「1 级」

- **现象**：`/category` 所有分类都显示「1 级」徽标，无法区分父子。
- **根因**：[category.html:163](file:///c:/Users/Administrator/Desktop/wms/app/templates/category.html#L163) `<td><span class="category-level-badge">{{ row.level + 1 }} 级</span></td>`，但 `row.level` 永远 0。
- **修复**：
  1. 后端：序列化时计算 `level`（parent_id 链上溯根数）。
  2. 模板：把 `level` 改为 1/2/3 不同颜色（一级橙色、二级蓝色、三级绿色）。
  3. 增加一列「完整路径」：「根类 > 整机设备 > A」。
- **验证**：`/category` → 二级分类显示「2 级」+ 蓝色徽标。
- **commit**：`fix(BUG-019): 物料分类层级列显示真实层级并增加颜色区分`

---

## 20. P3-020：库存查询「打印模板」按钮在空数据时仍可见

- **现象**：`/stock_query` 「打印模板」按钮一直常驻，库存为空时点击无意义。
- **根因**：[stock_query.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/stock_query.html) 按钮无条件渲染。
- **修复**：
  1. 按钮包一层 `{% if stock_rows and stock_rows|length > 0 %}`。
  2. 空数据时显示占位文案「暂无数据，请先查询」。
- **验证**：`/stock_query` 空查询结果 → 「打印模板」按钮消失，显示「暂无数据」占位。
- **commit**：`fix(BUG-020): 库存查询「打印模板」按钮在空数据时置灰并隐藏`

---

## 21. 基线与回归

- `WMS_BUG_BASELINE.md` 追加 20 条 → 标记 `已修复并纳入回归`。
- `verify_wms_bugs.py` 自动化脚本（如已存在）补充 5 个新断言；不存在则新建。
- 推送：`git push origin main` 确认 main 含全部 20 个 commit。

---

## 22. 提交粒度建议（20 个独立 commit）

| # | commit 标题 |
|---|-------------|
| 1 | `fix(BUG-001/002): add 404/405 error pages and handlers` ✅ |
| 2 | `fix(BUG-003): /purchase_order 默认显示列表` |
| 3 | `fix(BUG-004): 禁止 admin 自助重置密码 + 二次确认` |
| 4 | `fix(BUG-005): 入/出库单保存强制校验仓库与明细必填` |
| 5 | `fix(BUG-006): 列表页表头首列 check_th 宏 + 修复 COLU 截断` |
| 6 | `fix(BUG-007): 业务单据页统一一套工具栏` |
| 7 | `fix(BUG-008): 空数据列表只渲染「暂无数据」占位` |
| 8 | `fix(BUG-009): 统一列表分页区文案「共 N 条」` |
| 9 | `fix(BUG-010): 基础资料 add 路由支持 GET/POST` |
| 10 | `fix(BUG-011): 登录页增加失败次数/IP 累计与锁定倒计时` |
| 11 | `fix(BUG-012): 操作审计卡片文案统一为「历史/实时审计」` |
| 12 | `fix(BUG-013): 管理员控制台零值卡片增加引导跳转` |
| 13 | `fix(BUG-014): 新增单据页增加「保存并新建」` |
| 14 | `fix(BUG-015): Tab 栏最大数限制与「关闭其他/全部」菜单` |
| 15 | `fix(BUG-016): AI 助手悬浮按钮滚动收起与可隐藏` |
| 16 | `fix(BUG-017): 入库/出库/采购单列表与新增 Title 统一` |
| 17 | `fix(BUG-018): 客户/供应商搜索框 placeholder 统一顿号` |
| 18 | `fix(BUG-019): 物料分类层级显示真实层级与颜色区分` |
| 19 | `fix(BUG-020): 库存查询「打印模板」按钮空数据时隐藏` |
| 20 | `docs: WMS_BUG_BASELINE.md 同步 20 条已修复 BUG` |
