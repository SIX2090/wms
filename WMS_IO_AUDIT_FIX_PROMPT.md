# WMS 出入库单据全方位审计 - AI 修复提示词（IO-AUDIT-FIX-2026-07-27）

> 用途：根据 `wms_io_audit_20260727_133900.md` 报告，按 P1 → P2 顺序**一次性**修复所有发现的缺陷，确保 WMS 出入库单据、列表、报表、表头、明细、按钮的功能完善无遗漏。
> 工作目录：`/workspace`
> 基础报告：`wms_io_audit_20260727_133900.md` + `wms_io_audit_data.json`
> 修复方式：**静态扫描 + 动态验证（test_client 渲染）**，禁止只看 AI 自述。
> 验收产物：`wms_io_audit_fix_<YYYYMMDD_HHMMSS>.md` + 完整 push 到 main。

---

## 0. 必须遵守的硬规则

1. **只动 main 分支**：禁止创建 `feature/*` / `fix/*` / `chore/*` / `trae/*` 等任何新分支，所有 commit / push 必须直接打到 `main`。
2. **AI 不写业务数据**：`/ai/*` 路由全部 read-only（`read` 风险级别），7 队列不允许任何写动作（`send`/`submit`/`audit`/`delete`/`void`/`complete`/`confirm_post`/`cancel`/`auto_dispatch`）。
3. **不修改用户密码**：`tools/reset_admin_password.py` 必须保留「使用用户输入」路径，不得引入 `secrets.token_urlsafe`。
4. **未修改 WMS_BOOTSTRAP_PASSWORD 路径**：当 `WMS_BOOTSTRAP_PASSWORD` 未设置时，必须使用固定默认密码 `'admin'`，禁止任何 `secrets.token_urlsafe` 调用。
5. **已完成单据禁止硬删**：所有 `delete_*` 路由必须先检查 `status`，completed/released 状态必须返回 409 并提示「反提交后删除」。
6. **CSRF 防护**：所有写操作（POST/PUT/DELETE）必须经过 `CSRFProtect(app)`，mobile API（`/api/*`）可豁免（合理）。
7. **不修改已完成单据删除路径**：`status != 'pending'` 分支必须保留。
8. **修复后必须验证**：
   - `git log -1 --oneline` 与 `git ls-remote origin main` 一致
   - `git branch -a | grep -v 'main' | grep -v 'remotes/origin/HEAD'` 必须为空
   - 关键页面 test_client 渲染 200
   - import_* 路由必须含 `validate_excel_size` + `validate_excel_extension`
9. **修复后必须 commit + push 到 `https://github.com/SIX2090/wms.git` main**，并在 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 追加 `IO-AUDIT-FIX-2026-07-27` 完成记录。

---

## 1. 缺陷清单（按 P1 → P2 排序）

### 1.1 P1（一般，7 项）

| ID | 缺陷 | 位置 | 修复要求 |
|----|------|------|----------|
| **M-01** | 11 个 import_* 函数无 5MB 文件大小校验 | `import_requisition`, `import_subcontract`, `import_subcontract_issue`, `import_subcontract_receive`, `import_transfer`, `import_adjustment`, `import_check`, `import_after_sale_out`, `import_purchase_request`, `import_purchase_order`, `import_sales_orders` | 每个 import_* 函数入口加 `validate_excel_extension(file.filename)` + `validate_excel_size(file)`，参考已实现的 `import_in_order` / `import_material` 模式；返回 JSON `{status:'error', msg:'文件超过 5MB 限制'}` |
| **M-02** | 售后出库单列表页缺工具栏 | `app/templates/after_sale_out.html` | 参照 `out_order.html` 添加 page-header，包含「新增」「导入」「导出」「下载模板」「打印」5 个按钮 + `#importModal` + JS 处理函数 |
| **M-03** | 委外三单据列表页缺「下载模板」 | `subcontract.html`, `subcontract_issue.html`, `subcontract_receive.html` | 添加 `<a href="/xxx/download_template">` 按钮 + 后端 `download_subcontract_template` / `download_subcontract_issue_template` / `download_subcontract_receive_template` 路由（使用 openpyxl 生成空白模板） |
| **M-04** | 4 个单据无独立详情页 | `transfer.html` / `check.html` / `adjustment.html` / `subcontract_issue.html` / `subcontract_receive.html` | 评估是否需要独立详情页；如保留列表内联展示，必须在 `report.html` 提供「查看详情」链接；如新建 `xxx_detail.html`，需含状态徽标 + 元数据 + 操作日志 + 工具栏 |
| **M-05** | 5 个单据无独立新增/编辑页 | `transfer` / `check` / `subcontract` / `subcontract_issue` / `subcontract_receive` | 评估 `xxx/add` 路由是否使用通用表单；如缺失，参照 `in_order_add.html` 创建 `xxx_add.html` 模板，含明细表 + 添加行 + 物料自动补全 + CSRF |
| **M-06** | 委外加工单列表缺导入/导出/下载模板 | `subcontract.html` | 参照 `in_order.html` 添加「导入」「导出」「下载模板」3 个按钮 |
| **M-07** | 采购入库单列表页缺「打印」按钮 | `in_order.html` | 添加 `<a href="/in_order/<id>/print">打印</a>` 操作列按钮（按钮已存在 row 操作列，只缺顶层批量入口；优先补充行级 print 链接） |

### 1.2 P2（提示，7 项）

| ID | 缺陷 | 位置 | 修复要求 |
|----|------|------|----------|
| **m-01** | 委外加工三单据列表缺分页 | subcontract*.html | 添加 `<nav>` + `paginate` + 上一页/下一页/页码跳转 |
| **m-02** | 调拨/盘点/调整单列表缺分页 | transfer.html / check.html / adjustment.html | 同 m-01 |
| **m-03** | 委外加工详情页缺编辑/打印/复制/完成/反提交/删除按钮 | subcontract_detail.html | 添加完整工具栏（状态判断：pending 显示编辑/完成/删除，completed 显示打印/反提交） |
| **m-04** | 采购订单详情页缺编辑/打印/复制/完成/反提交/删除按钮 | purchase_order_detail.html | 同 m-03 |
| **m-05** | 售后出库单缺「添加行」按钮 | after_sale_out_add.html | 添加 JS `addRow()` + HTML 按钮 |
| **m-06** | 采购订单新增页缺「添加行」按钮 | purchase_order_add.html | 同 m-05 |
| **m-07** | 所有详情页缺「操作日志」模块 | 7 个 *_detail.html | 评估是否显示 OperationLog；如启用，需在详情页底部添加 `<div class="card">` 列出最近 10 条 audit log |

---

## 2. 修复步骤（必须按顺序执行）

### 阶段 1：M-01（11 个 import_* 函数加 5MB 校验）

**目标文件**: `app/app.py`

**修复模式**（参考 `import_in_order` @ line 41591-41605）：

```python
@app.route('/xxx/import', methods=['POST'])
@login_required
@require_role(...)
def import_xxx():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'status': 'error', 'msg': '请选择要上传的 Excel 文件'}), 400
    _ext_ok, _ext_msg = validate_excel_extension(file.filename)
    if not _ext_ok:
        return jsonify({'status': 'error', 'msg': _ext_msg}), 400
    _size_ok, _size_msg = validate_excel_size(file)
    if not _size_ok:
        return jsonify({'status': 'error', 'msg': _size_msg}), 400
    # ... 原有解析逻辑
```

**11 个函数清单与行号**（以 `app.py` 实际行号为准）：

| 函数 | 当前状态 | 需插入位置 |
|------|----------|------------|
| `import_requisition` | 无校验 | 函数体首段 |
| `import_subcontract` | 无校验 | 函数体首段 |
| `import_subcontract_issue` | 无校验 | 函数体首段 |
| `import_subcontract_receive` | 无校验 | 函数体首段 |
| `import_transfer` | 无校验 | 函数体首段 |
| `import_adjustment` | 无校验 | 函数体首段 |
| `import_check` | 无校验 | 函数体首段 |
| `import_after_sale_out` | 无校验 | 函数体首段 |
| `import_purchase_request` | 无校验 | 函数体首段 |
| `import_purchase_order` | 无校验 | 函数体首段 |
| `import_sales_orders` | 无校验 | 函数体首段 |

**验证命令**：
```bash
python _check_import_validations.py
# 期望: 23 个 import_* 函数全部 PASS
```

### 阶段 2：M-02 / M-03 / M-06 / M-07（工具栏补全）

#### M-02: after_sale_out.html 工具栏
在 `<div class="page-header">` 内添加：
- 新增按钮：`<a href="/after_sale_out/add" class="btn btn-primary"><i class="bi bi-plus-lg"></i> 新增售后出库单</a>`
- 导入按钮：触发 `#importModal`（仿 `out_order.html`）
- 导出按钮：`<a href="/after_sale_out/export" class="btn btn-success"><i class="bi bi-download"></i> 导出</a>`
- 下载模板：`<a href="/after_sale_out/download_template" class="btn btn-outline-secondary"><i class="bi bi-file-earmark-excel"></i> 下载模板</a>`
- 打印按钮：行级 + 批量（在 row 操作列添加「打印」链接）

后端新增路由（仿 `out_order` 模式）：
```python
@app.route('/after_sale_out/import', methods=['POST'])
@app.route('/after_sale_out/export')
@app.route('/after_sale_out/download_template')
```

#### M-03: 委外三单据 download_template
- `download_subcontract_template` (line ~29063)
- `download_subcontract_issue_template` (line ~29621)
- `download_subcontract_receive_template` (line ~30162)

每个生成对应字段的 openpyxl 模板（参考 `download_category_template` @ line 40737-40750）。

#### M-06: subcontract.html 工具栏
- 导入按钮 + `#importModal`
- 导出按钮
- 下载模板按钮（依赖 M-03 路由）

#### M-07: in_order.html 行级打印
在 `in_order.html` 操作列添加：
```html
<a href="/in_order/{{ o.id }}/print" target="_blank" class="btn btn-sm btn-outline-secondary">打印</a>
```

### 阶段 3：M-04 / M-05（详情页 / 新增页评估）

**决策矩阵**：

| 单据 | 详情页处理 | 新增页处理 |
|------|-----------|-----------|
| 调拨单 transfer | 复用 `transfer_print.html` (已存在) + 列表内联编辑 | 评估通用 `/transfer/add` 是否已支持内联；如缺失，仿 `in_order_add.html` 创建 `transfer_add.html` |
| 盘点单 check | 复用 `check_print.html` (已存在) + 列表内联 | 同 transfer |
| 调整单 adjustment | 评估是否需独立详情；如否，文档化使用列表内联 | 同 transfer |
| 委外发料单 subcontract_issue | 同 transfer | 同 transfer |
| 委外收货单 subcontract_receive | 同 transfer | 同 transfer |
| 委外加工单 subcontract | 已有 `subcontract_detail.html` | 评估是否需独立 add；如否，文档化 |

**修复原则**：如现有 `/xxx/<id>` GET 路由已渲染完整详情，则详情页功能已具备（仅模板命名可能不同）。需补充缺失的「编辑/打印/复制/完成/反提交/删除」按钮（m-03/m-04）。

### 阶段 4：P2 细节

#### m-01 / m-02: 分页
参考 `in_order.html` 添加分页宏：
```html
{% include '_list_macros.html' %}
{{ render_pagination(pagination, request.args) }}
```

#### m-03 / m-04: 详情页工具栏
在 `subcontract_detail.html` / `purchase_order_detail.html` 头部添加：
```html
<div class="btn-group">
  <a href=".../edit" class="btn btn-primary">编辑</a>
  <a href=".../print" class="btn btn-secondary">打印</a>
  <a href=".../copy" class="btn btn-info">复制</a>
  <form action=".../complete" method="post" class="d-inline">{% if csrf_token %}<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">{% endif %}<button class="btn btn-success">完成</button></form>
  <form action=".../revert" method="post" class="d-inline">{% if csrf_token %}<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">{% endif %}<button class="btn btn-warning">反提交</button></form>
  <form action=".../delete" method="post" class="d-inline">{% if csrf_token %}<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">{% endif %}<button class="btn btn-danger" onclick="return confirm('确认删除?')">删除</button></form>
</div>
```

#### m-05 / m-06: 添加行 JS
参照 `in_order_add.html` 的 `addRow()` 函数：
```html
<button type="button" class="btn btn-sm btn-success" onclick="addRow()">+ 添加行</button>
```

#### m-07: 操作日志
- 评估 OperationLog 模型是否已存在
- 如存在，在详情页底部添加：
```html
<div class="card mt-3">
  <div class="card-header">操作日志</div>
  <div class="card-body">
    <table class="table table-sm">
      <thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>备注</th></tr></thead>
      <tbody>{% for log in operation_logs %}<tr><td>{{ log.created_at }}</td><td>{{ log.user }}</td><td>{{ log.action }}</td><td>{{ log.note }}</td></tr>{% endfor %}</tbody>
    </table>
  </div>
</div>
```

---

## 3. 验证清单（修复后必须全部通过）

### 3.1 硬规则验证

```bash
# 1. 分支
git branch -a | grep -v 'main' | grep -v 'remotes/origin/HEAD'
# 期望: 空

# 2. HEAD 一致
git log -1 --oneline
git ls-remote "https://${GH_TOKEN}@github.com/SIX2090/wms.git" main
# 期望: 两者 SHA 一致

# 3. 密码工具未引入随机生成
grep -r "secrets.token_urlsafe" app/app.py tools/
# 期望: 无新增（除 AI 不相关的旧实现）

# 4. WMS_BOOTSTRAP_PASSWORD 默认 'admin'
grep -A2 "WMS_BOOTSTRAP_PASSWORD" app/app.py | head -20
# 期望: 仍使用固定 'admin'

# 5. 已完成单据保护
python _audit_io_full.py 2>&1 | grep "delete_" | head -40
# 期望: 39 个 delete_* 函数全部含 409/反提交
```

### 3.2 P1 修复验证

```bash
# M-01: 11 个 import_* 加 5MB 校验
python _check_import_validations.py
# 期望: 全部 PASS, 0 FAIL

# M-02: after_sale_out 工具栏
grep -E "(新增|导入|导出|下载模板|打印)" app/templates/after_sale_out.html | head -10
# 期望: 至少 5 个匹配

# M-03: 委外三单 download_template 路由
grep -E "download_subcontract" app/app.py | head -5
# 期望: 至少 3 个路由（template / issue_template / receive_template）

# M-07: in_order.html 行级打印
grep -E "/print" app/templates/in_order.html | head -5
# 期望: 至少 1 个 print 链接
```

### 3.3 P2 修复验证

```bash
# m-01/m-02: 分页
for tpl in subcontract.html subcontract_issue.html subcontract_receive.html transfer.html check.html adjustment.html; do
  echo "--- $tpl ---"
  grep -E "(pagination|paginate|分页)" app/templates/$tpl | head -3
done
# 期望: 6 个模板均含分页元素

# m-05/m-06: 添加行 JS
grep -E "(addRow|添加行)" app/templates/after_sale_out_add.html app/templates/purchase_order_add.html
# 期望: 2 个模板均含 addRow
```

### 3.4 动态验证（test_client）

```python
# _verify_io_fixes.py
import os, sys, runpy
os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'admin'
os.environ['WMS_TEST_DB'] = 'sqlite:///:memory:'
sys.path.insert(0, '/workspace/app')
app_globals = runpy.run_path('/workspace/app/app.py')
flask_app = next(v for v in app_globals.values() if isinstance(v, Flask))
flask_app.config['WTF_CSRF_ENABLED'] = False
client = flask_app.test_client()

# 验证关键页面
for url in ['/in_order', '/out_order', '/after_sale_out', '/transfer', '/check',
            '/adjustment', '/subcontract', '/subcontract_issue', '/subcontract_receive',
            '/purchase_order', '/batch_import']:
    resp = client.get(url, follow_redirects=False)
    print(f'{url:30s} -> {resp.status_code}')
    assert resp.status_code in (200, 302), f'{url} returned {resp.status_code}'

# 验证 download_template 路由
for url in ['/subcontract/download_template', '/subcontract_issue/download_template',
            '/subcontract_receive/download_template', '/after_sale_out/download_template',
            '/after_sale_out/export', '/after_sale_out/import']:
    resp = client.get(url, follow_redirects=False)
    print(f'{url:50s} -> {resp.status_code}')
```

期望: 所有 URL 返回 200/302 (302 表示未登录重定向，正常)。

### 3.5 完整度自检

```bash
python _audit_io_full.py 2>&1 | tee /tmp/audit_after_fix.log
# 期望:
# - 列表页按钮合格率从 60% 提升到 ≥ 90%
# - 详情页工具栏合格率从 70% 提升到 ≥ 95%
# - 导入校验从 52% 提升到 100%
```

---

## 4. 实施计划（commit 拆分建议）

| Commit | 内容 | 涉及文件 |
|--------|------|----------|
| commit 1 | `fix(io-audit-M-01): 11 个 import_* 函数加 5MB + 扩展名校验` | `app/app.py` |
| commit 2 | `feat(io-audit-M-02/M-06): after_sale_out + subcontract 列表页工具栏补全` | 2 个模板 |
| commit 3 | `feat(io-audit-M-03): 委外三单据 download_template 路由` | `app/app.py` + 3 个模板 |
| commit 4 | `feat(io-audit-M-07): in_order.html 行级打印按钮` | `in_order.html` |
| commit 5 | `feat(io-audit-m-01/m-02): 委外三单 + 调拨/盘点/调整 列表分页` | 6 个模板 |
| commit 6 | `feat(io-audit-m-03/m-04): subcontract_detail + purchase_order_detail 工具栏` | 2 个模板 |
| commit 7 | `feat(io-audit-m-05/m-06): after_sale_out_add + purchase_order_add 添加行` | 2 个模板 |
| commit 8 | `feat(io-audit-m-07): 详情页操作日志模块（如启用）` | 7 个模板 |

**注意**: 可根据代码量合并 commit，但每个 commit 必须单一目的 + 可独立回滚。

---

## 5. 完成后必做

### 5.1 提交日志模板

```text
fix(io-audit): [本次修复范围]

- 修复 IO-AUDIT-2026-07-27 报告中的 P1/P2 缺陷
- M-01: 11 个 import_* 函数加 validate_excel_size + validate_excel_extension
- M-02: after_sale_out.html 工具栏补全（5 按钮）
- M-03: 委外三单 download_template 路由
- M-04/M-05: [决策结果]
- M-06: subcontract.html 工具栏补全
- M-07: in_order.html 行级打印
- m-01/m-02: 6 个列表页加分页
- m-03/m-04: 2 个详情页工具栏
- m-05/m-06: 2 个 add 页添加行
- 业务边界: 仅加 UI 按钮/路由/JS, 不修改后端业务逻辑
- 验证: test_client 渲染 200, import 5MB 校验通过
```

### 5.2 更新 WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md

在 `IO-AUDIT-2026-07-27` 条目后追加 `IO-AUDIT-FIX-2026-07-27`：

```markdown
#### IO-AUDIT-FIX-2026-07-27（已完成）

- 目标：执行本提示词，按 P1 → P2 顺序一次性修完 7 P1 + 7 P2 缺陷
- 业务边界：仅加 UI 按钮 / 路由 / 5MB 校验 / 分页；不改后端业务逻辑 / 用户密码 / 已完成单据删除路径；保持 main 唯一分支
- 改动模块：
  - `app/app.py`：M-01 11 个 import_* 加 validate_excel_size + validate_excel_extension；M-03 3 个 download_subcontract_*_template 路由；M-02 3 个 after_sale_out/import|export|download_template 路由
  - `app/templates/after_sale_out.html`：M-02 工具栏 5 按钮
  - `app/templates/subcontract.html`：M-06 工具栏 3 按钮
  - `app/templates/{subcontract,subcontract_issue,subcontract_receive,transfer,check,adjustment}.html`：m-01/m-02 分页
  - `app/templates/{subcontract_detail,purchase_order_detail}.html`：m-03/m-04 工具栏
  - `app/templates/{after_sale_out_add,purchase_order_add}.html`：m-05/m-06 添加行 JS
  - `app/templates/in_order.html`：M-07 行级打印
- 验证命令：
  - `python _check_import_validations.py` → 全部 PASS
  - `python _verify_io_fixes.py` → 全部 200/302
  - `python -c "import ast; ast.parse(open('app/app.py').read())"` → OK
- 提交 SHA: [本次 commit 列表]
- 推送: [本次 push 输出]
- 报告: `wms_io_audit_fix_<时间戳>.md`
```

### 5.3 生成验收报告

输出 `wms_io_audit_fix_<YYYYMMDD_HHMMSS>.md`，包含：
- 修复前后对比表（每个缺陷的 PASS 状态）
- 验证命令输出
- 完整度评分（应从 82% 提升到 ≥ 95%）
- commit SHA 列表
- push 验证结果

### 5.4 推送并验证

```bash
git push "https://${GH_TOKEN}@github.com/SIX2090/wms.git" main
git ls-remote "https://${GH_TOKEN}@github.com/SIX2090/wms.git" main
# 期望: 两者 SHA 一致
```

---

## 6. 失败兜底

- **如果某个 import_* 函数已含不同模式的校验**（如直接 `allowed_file`）：保留现有模式，仅在其后追加 `validate_excel_size` 调用，不破坏原有逻辑。
- **如果某模板已含部分按钮**：评估是补齐缺失按钮还是统一重构；优先补齐，最小变更。
- **如果某路由的 path 已被占用**：`@app.route` 装饰器顺序可调整，但必须保留 `@login_required` 和 `@require_role`。
- **如果 test_client 渲染因 DB 缺少基础数据失败**：先 `db.create_all()` + 创建 admin user；这是测试环境问题，不是修复问题。
- **如出现网络问题导致 push 失败**：使用 `git pull --rebase` 后重试；禁止 force push。

---

## 7. 完成门槛

任务必须同时满足以下条件才能标记「IO-AUDIT-FIX-2026-07-27 已完成」：

1. 7 项 P1 缺陷全部修复并验证 PASS
2. 7 项 P2 缺陷全部修复并验证 PASS（或明确记录「暂缓」原因）
3. `python _check_import_validations.py` 全部 PASS
4. `python _verify_io_fixes.py` 全部 200/302
5. `python -c "import ast; ast.parse(open('app/app.py').read())"` 通过
6. 所有 commit 已 push 到 `https://github.com/SIX2090/wms.git` main
7. GitHub remote SHA 与本地 HEAD 一致
8. `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 已追加完成记录
9. `wms_io_audit_fix_<时间戳>.md` 验收报告已生成
10. 未新建任何非 main 分支；未引入 `secrets.token_urlsafe`；未硬删已完成单据路径
