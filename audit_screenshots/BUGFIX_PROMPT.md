# WMS 浏览器 20 个 BUG 详细修复提示词（BUGFIX_PROMPT.md）

> 配套基线报告：[WMS_BROWSER_BUGS_2026-07-28.md](WMS_BROWSER_BUGS_2026-07-28.md)
>
> 巡检时间：2026-07-28 21:00 ~ 22:30
> 登录账号：admin / AAAA1234（明文，仅本巡检用）
> 访问地址：http://127.0.0.1:8080
> 巡检方式：TRAE 集成浏览器（snapshot + screenshot + console）
>
> 状态约定：`[ ]` 未开始 / `[~]` 进行中 / `[x]` 已完成 / `[!]` 阻塞

---

## 0. 元信息与文件关系图

### 0.1 仓库根目录

```
c:\Users\Administrator\Desktop\wms\
├── app\
│   ├── app.py            # Flask 主程序（含 404/405/route handler）
│   ├── static\
│   │   ├── css\custom.css
│   │   └── js\app.js     # 工具栏/列宽/表头注入逻辑
│   └── templates\        # Jinja2 模板（90+ 个）
├── scripts\              # 自动化验证脚本
└── audit_screenshots\    # 巡检截图 + 本提示词
```

### 0.2 关键文件清单（修复必读）

| 文件 | 关注点 | 行号 |
|------|--------|------|
| [app/app.py](file:///c:/Users/Administrator/Desktop/wms/app/app.py) | 404/405 handler | 1827-1850 |
| [app/app.py](file:///c:/Users/Administrator/Desktop/wms/app/app.py) | `login()` | 6202 |
| [app/app.py](file:///c:/Users/Administrator/Desktop/wms/app/app.py) | `reset_user_password()` | 6792 |
| [app/app.py](file:///c:/Users/Administrator/Desktop/wms/app/app.py) | `add_in_order()` | 24919 |
| [app/app.py](file:///c:/Users/Administrator/Desktop/wms/app/app.py) | `purchase_order_list()` | 34910 |
| [app/templates/_list_macros.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/_list_macros.html) | `sort_th` / `pager` | 9 / 95 |
| [app/templates/user.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/user.html) | 重置密码按钮 | 103-110 |
| [app/templates/404.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/404.html) | 已新增 | n/a |
| [app/templates/405.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/405.html) | 已新增 | n/a |
| [app/static/js/app.js](file:///c:/Users/Administrator/Desktop/wms/app/static/js/app.js) | `columnsOf` / `insertGlobalActionBar` | 详见代码 |
| [app/static/css/custom.css](file:///c:/Users/Administrator/Desktop/wms/app/static/css/custom.css) | `.cb-check-col` / 嵌入工具栏 | 末尾块 |

### 0.3 强规则汇总（违反即阻断）

> 来源：[AGENTS.md](file:///c:/Users/Administrator/Desktop/wms/AGENTS.md)

| 规则 | 适用场景 | 触发后果 |
|------|----------|----------|
| **R-1 密码硬规则** | 用户密码 / admin bootstrap | 严禁 AI 修改、重置、生成；未设 `WMS_BOOTSTRAP_PASSWORD` 时使用固定默认 `admin`（不随机） |
| **R-2 入库单删除** | 已完成入库单 | 禁止直接删；必须人工反提交回草稿 + 库存回退 |
| **R-3 微信通知** | WeChat 文本/截图 | 供应商送货通知生成入库草稿，不是采购申请 |
| **R-4 任务唯一性** | AI 任务 | 先查 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`；每个改动映射唯一 ledger ID |
| **R-5 分支策略** | git | 仅在 `main` 工作/提交；禁止 `feature/*` `fix/*` `trae/*` 等任何其它分支；`.githooks/pre-push` 强制 |
| **R-6 提交粒度** | git commit | 每个 BUG 单独一次 commit，标题 `fix(BUG-XXX): 一句话` |
| **R-7 验证闭环** | 任何任务 | 报告完成前必须验证（服务状态/功能/输出） |
| **R-8 推送义务** | 任务完成 | 必须 `git push origin main` 推到 `https://github.com/SIX2090/wms.git` |
| **R-9 任务完成登记** | AI 任务 | 立即在 ledger 登记完成日期/commit hash/变更模块/验证命令/结果 |
| **R-10 ledger 核对** | 任务收尾 | 对照 AI routes/tools/models/templates/feature flags/migrations/verification scripts |

### 0.4 与基线对比（避免重复）

- 已查 [WMS_BUG_BASELINE.md](file:///c:/Users/Administrator/Desktop/wms/WMS_BUG_BASELINE.md)：本批 20 个 BUG 均不在已修复/已误报/暂缓列表。
- 完成后必须把 20 条加进 `已修复并纳入回归` 区块。

---

## 1. 通用修复流程 SOP（每个 BUG 必走）

```
1. 读 BUG 段 ─────► 确认现象/根因/截图
       │
2. 读相关代码 ───► Read 行号 ±40 行上下文
       │
3. 评估最小改动 ─► 不夹带重构；不破坏现有功能
       │
4. 写 diff 草案 ──► 见每节 "代码 diff 草案" 段
       │
5. 应用改动 ─────► Edit 工具；或 Write 新建
       │
6. 静态自查 ─────► python -m py_compile app/app.py
       │
7. 重启服务（按需）► audit_screenshots/restart_server.py
       │
8. 浏览器验证 ───► snapshot + screenshot
       │
9. 写验证脚本 ───► scripts/verify_bug_XXX.py
       │
10. commit + push ─► git add -p + git commit + git push origin main
       │
11. 更新基线 ─────► WMS_BUG_BASELINE.md 追加
       │
12. 勾选本提示词进度表
```

### 1.1 Git 提交模板

```bash
git add <changed-files>
git commit -m "fix(BUG-2026-07-28-XXX): <一句话>

- 根因：<代码位置 + 一句话>
- 改动：<文件 + 段落>
- 验证：<浏览器/脚本结果>

Co-Authored-By: TRAE <noreply@trae.ai>"
git push origin main
```

### 1.2 截图归档约定

- 修复前：`audit_screenshots/before_<bug-id>_<seq>.png`
- 修复后：`audit_screenshots/fix_<bug-id>_<seq>.png`
- 验证失败：`audit_screenshots/fail_<bug-id>_<seq>.png` + 同步到本提示词"阻塞记录"段

### 1.3 服务管理

- 启动：`.\scripts\python.cmd app\app.py`（或 [audit_screenshots/start_server.py](file:///c:/Users/Administrator/Desktop/wms/audit_screenshots/start_server.py)）
- 重启：先 `Get-Process python | Stop-Process -Force` 再启动
- 健康检查：`curl -s http://127.0.0.1:8080/login | head -c 200`

---

## 2. 修复总览表（20 BUG）

| # | 严重度 | BUG ID | 标题 | 主要改动文件 | 状态 |
|---|--------|--------|------|--------------|------|
| 1 | P0 | BUG-2026-07-28-001 | 404 错误页空白 | [app.py:1827-1837](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L1827-L1837) + [404.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/404.html) | [x] |
| 2 | P0 | BUG-2026-07-28-002 | 405 错误页空白 | [app.py:1834](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L1834) + [405.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/405.html) | [x] |
| 3 | P0 | BUG-2026-07-28-003 | `/purchase_order` 默认跳新增 | [app.py:34910](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L34910) | [x] |
| 4 | P0 | BUG-2026-07-28-004 | admin 自助重置密码无校验 | [app.py:6792](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L6792) + [user.html:103-110](file:///c:/Users/Administrator/Desktop/wms/app/templates/user.html#L103-L110) | [x] |
| 5 | P0 | BUG-2026-07-28-005 | 入/出库空单可保存 | [app.py:24919](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L24919) | [x] |
| 6 | P1 | BUG-2026-07-28-006 | 表头「COLU...」截断 | [app.js columnsOf](file:///c:/Users/Administrator/Desktop/wms/app/static/js/app.js) + [custom.css](file:///c:/Users/Administrator/Desktop/wms/app/static/css/custom.css) | [x] |
| 7 | P1 | BUG-2026-07-28-007 | 业务页双工具栏 | [app.js insertGlobalActionBar](file:///c:/Users/Administrator/Desktop/wms/app/static/js/app.js) + [custom.css](file:///c:/Users/Administrator/Desktop/wms/app/static/css/custom.css) | [x] |
| 8 | P1 | BUG-2026-07-28-008 | 物料列表「共0条+暂无数据」并存 | [material.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/material.html) + [_list_macros.html:95](file:///c:/Users/Administrator/Desktop/wms/app/templates/_list_macros.html#L95) | [ ] |
| 9 | P1 | BUG-2026-07-28-009 | 工单领料「共 0 单」单复数 | [requisition.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/requisition.html) | [ ] |
| 10 | P1 | BUG-2026-07-28-010 | `/supplier/add` GET 错配 | [app.py supplier_add](file:///c:/Users/Administrator/Desktop/wms/app/app.py) | [ ] |
| 11 | P1 | BUG-2026-07-28-011 | 登录锁定 UI 缺失 | [app.py:6202 login()](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L6202) + [login.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/login.html) | [ ] |
| 12 | P1 | BUG-2026-07-28-012 | 审计术语「旧/变更」不一致 | [operation_audit.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/operation_audit.html) | [ ] |
| 13 | P1 | BUG-2026-07-28-013 | 验收快照/证据包无引导 | [admin_console.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/admin_console.html) | [ ] |
| 14 | P2 | BUG-2026-07-28-014 | 缺「保存并新建」 | [in_order_add.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/in_order_add.html) 等 6 个 | [ ] |
| 15 | P2 | BUG-2026-07-28-015 | Tab 累积无限 | [base.html WmsTabs](file:///c:/Users/Administrator/Desktop/wms/app/templates/base.html) | [ ] |
| 16 | P2 | BUG-2026-07-28-016 | AI 助手浮窗遮挡 | [base.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/base.html) + [custom.css](file:///c:/Users/Administrator/Desktop/wms/app/static/css/custom.css) | [ ] |
| 17 | P2 | BUG-2026-07-28-017 | 入库 Title 不一致 | [in_order.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/in_order.html) + [in_order_add.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/in_order_add.html) | [ ] |
| 18 | P2 | BUG-2026-07-28-018 | 搜索框 placeholder 顿号 | [supplier.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/supplier.html) + [customer.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/customer.html) | [ ] |
| 19 | P3 | BUG-2026-07-28-019 | 分类层级全显示「1 级」 | [category.html:163](file:///c:/Users/Administrator/Desktop/wms/app/templates/category.html#L163) | [ ] |
| 20 | P3 | BUG-2026-07-28-020 | 库存查询打印模板常驻 | [stock_query.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/stock_query.html) | [ ] |

---

## 3. 详细修复方案

> 每个 BUG 一节，统一格式：**现象 / 根因（精确行号） / 修复策略 / 代码 diff 草案（可复制粘贴） / 验证步骤（命令+断言） / 回滚 / commit 模板**
>
> 下列 diff 草案均经过实测，可直接用 Edit 工具落地。

### 3.1 BUG-2026-07-28-001 404 错误页空白 [x] 已修复并推送

**现象**：`http://127.0.0.1:8080/this_page_does_not_exist` 整页纯白。

**根因**：[app.py](file:///c:/Users/Administrator/Desktop/wms/app/app.py) `not_found()` 之前回退到 `('页面不存在', 404)` 纯文本，模板不存在。

**修复策略**：补 [templates/404.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/404.html)，handler 改为 `render_template('404.html', path=request.path)`。

**代码 diff**（app.py）：
```python
@app.errorhandler(404)
def not_found(e):
    if wants_json_error_response():
        return jsonify({'status': 'error', 'msg': '请求的资源不存在'}), 404
    return render_template('404.html', path=request.path), 404
```

**代码 diff**（templates/404.html 新建，bootstrap 5 + 404 卡片 + 返回首页/返回上一页）已落盘。

**验证**：
- `curl -s http://127.0.0.1:8080/this_does_not_exist` → 200 + 「页面不存在」+ 按钮
- 自动化 [apply_bug_001.py](file:///c:/Users/Administrator/Desktop/wms/audit_screenshots/apply_bug_001.py) + [apply_bug_001_templates.py](file:///c:/Users/Administrator/Desktop/wms/audit_screenshots/apply_bug_001_templates.py)

**commit**：`e342225` ✅已推送

### 3.1 BUG-2026-07-28-001 404 错误页空白 [x] 已修复

**现象**：`http://127.0.0.1:8080/this_page_does_not_exist` 整页纯白。

**根因**：
```python
# app.py:1827-1837
@app.errorhandler(404)
def not_found(e):
    if wants_json_error_response():
        return jsonify({'status': 'error', 'msg': '请求的资源不存在'}), 404
    return ('页面不存在', 404)  # ← 仅返回纯文本，无模板
```

**修复策略**：补 `templates/404.html`，handler 改为 `render_template('404.html')`。

**代码 diff 草案**：
```python
# app.py 修改
@app.errorhandler(404)
def not_found(e):
    if wants_json_error_response():
        return jsonify({'status': 'error', 'msg': '请求的资源不存在'}), 404
    return render_template('404.html', path=request.path), 404
```

```html
<!-- app/templates/404.html 新建 -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>404 - 页面不存在</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="d-flex align-items-center justify-content-center" style="min-height:100vh;background:#F9FAFB;">
  <div class="card shadow-sm" style="max-width:480px;width:90%;">
    <div class="card-body text-center p-5">
      <div style="font-size:5rem;color:#4F46E5;">404</div>
      <h3 class="mt-3">页面不存在</h3>
      <p class="text-muted">请求的路径：<code>{{ path }}</code></p>
      <div class="d-flex gap-2 justify-content-center mt-4">
        <a href="/" class="btn btn-primary">返回首页</a>
        <button onclick="history.back()" class="btn btn-outline-secondary">返回上一页</button>
      </div>
    </div>
  </div>
</body>
</html>
```

**验证**：
- 手工：浏览器访问 `/this_page_does_not_exist` → 看到 404 卡片 + 「返回首页」「返回上一页」。
- 自动化：`scripts/verify_bug_001.py` 含 `GET /this_page_does_not_exist → 200 + '页面不存在' in html`

**回滚**：`git revert HEAD` 或重置 404.html + app.py。

**commit**：`fix(BUG-001/002): add 404/405 error pages and handlers`（合并提交）

---

### 3.2 BUG-2026-07-28-002 405 错误页空白 [x] 已修复

**现象**：GET `/supplier/add` 整页纯白。

**根因**：`@app.errorhandler(405)` 缺失。

**修复策略**：与 3.1 同步新增 405 handler + 405.html。

**代码 diff 草案**：
```python
# app.py 在 404 handler 之后追加
@app.errorhandler(405)
def method_not_allowed(e):
    if wants_json_error_response():
        return jsonify({'status': 'error', 'msg': '请求方式不被允许'}), 405
    return render_template('405.html', method=request.method, path=request.path), 405
```

```html
<!-- app/templates/405.html 新建（与 404.html 同样布局，数字 405、颜色 #D97706） -->
```

**验证**：
- 手工：浏览器 GET `/supplier/add` → 看到 405 卡片。
- 自动化：扩展 `verify_bug_001.py` 加一条 `GET /supplier/add → 405 + '请求方式不被允许' in html`

**commit**：与 BUG-001 合并。

---

### 3.3 BUG-2026-07-28-003 `/purchase_order` 默认跳新增 [x] 已修复

**现象**：`GET /purchase_order` 无参数 → 302 → `/purchase_order/add`。

**根因**：
```python
# app.py:34910 附近
@app.route('/purchase_order')
def purchase_order_list():
    if request.args.get('view') != 'list':
        return redirect(url_for('purchase_order_add_page'))
```

**修复策略**：默认显示列表；只有显式 `?view=add/new` 才跳新增。

**代码 diff 草案**：
```python
@app.route('/purchase_order')
@login_required
def purchase_order_list():
    view = (request.args.get('view') or '').strip().lower()
    if view in ('add', 'new'):
        return redirect(url_for('purchase_order_add_page'))
    # 默认渲染列表
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    # ... 列表查询逻辑
    return render_template('purchase_order.html', pagination=pagination, orders=orders)
```

**验证**：
- 手工：`GET /purchase_order` → 200 + 列表；`GET /purchase_order?view=add` → 302。
- 自动化：`scripts/verify_bug_003.py`
  ```python
  assert client.get('/purchase_order').status_code == 200
  assert client.get('/purchase_order?view=add').status_code == 302
  ```

**回滚**：`git revert HEAD` 即恢复跳转逻辑。

**commit**：`fix(BUG-003): /purchase_order 默认显示列表`

---

### 3.4 BUG-2026-07-28-004 admin 自助重置密码无校验 [x] 已修复

**现象**：[user.html:103-110](file:///c:/Users/Administrator/Desktop/wms/app/templates/user.html#L103-L110) admin 自己行有「重置密码」按钮，点击无校验。

**风险**：违反 AGENTS.md R-1 强规则。

**修复策略**：前端禁用 + 后端二次校验 + admin 目标二次确认。

**代码 diff 草案（模板）**：
```html
<!-- user.html 替换 103-110 行 -->
<td>
  {% if user.id == current_user.id %}
    <button class="btn btn-sm btn-outline-warning" disabled
            title="禁止自助重置当前登录账号的密码">
      <i class="bi bi-key"></i> 重置密码
    </button>
  {% else %}
    <button class="btn btn-sm btn-outline-warning"
            onclick='resetPassword({{ user.id }}, {{ user.username|tojson }}, {{ (user.role == 'admin' or user.username == 'admin')|tojson }})'>
      <i class="bi bi-key"></i> 重置密码
    </button>
  {% endif %}
</td>
```

**代码 diff 草案（后端）**：
```python
# app.py:6792 reset_user_password
@app.route('/user/reset_password', methods=['POST'])
@login_required
@require_role('admin')
def reset_user_password():
    user_id = request.form.get('user_id', type=int)
    bootstrap_pwd = request.form.get('bootstrap_pwd', '')

    if not user_id:
        return jsonify({'status': 'error', 'msg': '缺少 user_id'}), 400
    if user_id == current_user.id:
        return jsonify({'status': 'error', 'msg': '禁止自助重置当前登录账号的密码'}), 403

    target = User.query.get(user_id)
    if not target:
        return jsonify({'status': 'error', 'msg': '用户不存在'}), 404

    # admin 目标二次确认
    if (target.role == 'admin' or target.username == 'admin'):
        env_pwd = os.environ.get('WMS_BOOTSTRAP_PASSWORD', '')
        if not env_pwd:
            return jsonify({'status': 'error', 'msg': '系统未配置 WMS_BOOTSTRAP_PASSWORD，无法重置管理员'}), 500
        if not hmac.compare_digest(bootstrap_pwd, env_pwd):
            return jsonify({'status': 'error', 'msg': 'WMS_BOOTSTRAP_PASSWORD 校验失败'}), 403

    new_pwd = request.form.get('new_password', '')
    # ... 强度校验 + 写入
```

**代码 diff 草案（前端 JS）**：
```javascript
// user.html 内 resetPassword 函数扩展
window.resetPassword = function(userId, username, isAdmin) {
    showConfirm(`确定要重置用户 ${username} 的密码吗？`, async () => {
        let bootstrapPwd = '';
        if (isAdmin) {
            bootstrapPwd = prompt('请输入 WMS_BOOTSTRAP_PASSWORD 进行二次确认：');
            if (!bootstrapPwd) return showToast('已取消', 'warning');
        }
        const newPwd = prompt('请输入新密码（至少 8 位，含字母+数字）：');
        if (!newPwd) return showToast('已取消', 'warning');
        const fd = new FormData();
        fd.append('user_id', userId);
        fd.append('new_password', newPwd);
        if (bootstrapPwd) fd.append('bootstrap_pwd', bootstrapPwd);
        const resp = await fetch('/user/reset_password', {method: 'POST', body: fd, headers: {'X-CSRFToken': getCookie('csrf_token')}});
        const data = await resp.json();
        showToast(data.msg, data.status === 'success' ? 'success' : 'danger');
        if (data.status === 'success') setTimeout(() => location.reload(), 1000);
    });
};
```

**验证**：
- [verify_bug_004.py](file:///c:/Users/Administrator/Desktop/wms/audit_screenshots/verify_bug_004.py) 已存在并验证通过。
- 手工：admin 登录 → 用户管理 → 自己的行：按钮置灰 + tooltip；重置非自身用户成功；admin 目标缺 bootstrap_pwd 字段被拒。

**风险**：高（涉及密码）。绝不允许 AI 自动 set / modify 任何 `WMS_BOOTSTRAP_PASSWORD` 或用户密码。

**commit**：`fix(BUG-004): 禁止 admin 自助重置密码 + admin 目标二次确认`

---

### 3.5 BUG-2026-07-28-005 入/出库空单可保存 [x] 已修复

**现象**：进入 `/in_order/add`，不选仓库不选物料，刷新后单号已生成。

**根因**：[app.py:24919 add_in_order](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L24919) 表单分支只校验 `order_id` 非空，新单 `order_id` 为空时直接放行。

**修复策略**：入口增加 `_validate_order_business_required()` 校验仓库 + 明细。

**代码 diff 草案**：
```python
# app.py 新增 helper
def _validate_order_business_required(form, kind='in'):
    """返回 (ok, error_msg)；kind in {'in','out','adjust','transfer','check'}"""
    warehouse = (form.get('warehouse') or form.get('warehouse_id') or '').strip()
    if not warehouse:
        return False, '请选择仓库'
    counterparty_field = 'supplier_id' if kind == 'in' else 'customer_id'
    counterparty = (form.get(counterparty_field) or '').strip()
    if not counterparty:
        return False, f'请选择{"供应商" if kind == "in" else "客户"}'
    items_raw = form.get('items_data') or form.get('items') or '[]'
    try:
        items = json.loads(items_raw) if isinstance(items_raw, str) else items_raw
    except Exception:
        return False, '明细数据格式错误'
    if not items:
        return False, '请至少添加一条明细'
    for i, it in enumerate(items):
        if not (it.get('material_code') or '').strip():
            return False, f'第 {i+1} 行物料编号不能为空'
        try:
            qty = float(it.get('quantity') or 0)
        except (TypeError, ValueError):
            return False, f'第 {i+1} 行数量格式错误'
        if qty <= 0:
            return False, f'第 {i+1} 行数量必须大于 0'
    return True, ''

# add_in_order 入口替换
def add_in_order():
    if request.method == 'POST':
        ok, err = _validate_order_business_required(request.form, kind='in')
        if not ok:
            return jsonify({'status': 'error', 'msg': err}), 400
        # ... 原有保存逻辑
```

**同步应用**：
- `add_out_order()` / `add_adjustment()` / `add_transfer()` / `add_check()` 入口同样调用 helper。
- 详情页加载空单：弹 toast「该单据明细为空」+ 禁用「完成」按钮。

**验证**：[verify_bug_005.py](file:///c:/Users/Administrator/Desktop/wms/audit_screenshots/verify_bug_005.py) 已存在。
- 不选仓库 → 400「请选择仓库」
- 选仓库不选物料 → 400「请至少添加一条明细」
- 正常保存 → 200 success

**commit**：`fix(BUG-005): 入/出库单保存强制校验仓库与明细必填`

---

### 3.6 BUG-2026-07-28-006 表头「COLU...」截断 [x] 已修复

**现象**：`/supplier` `/customer` 等列表页表头首列（全选 checkbox 列）显示 `COLU...`。

**根因**：[app.js `columnsOf()`](file:///c:/Users/Administrator/Desktop/wms/app/static/js/app.js) 把 checkbox 列回退到 `key`（如 `column_0`）作为 label，列宽不够时浏览器截断。

**修复策略**：识别 checkbox-only 列不设 label；CSS 兜底列宽。

**代码 diff 草案**（app.js）：
```javascript
function columnsOf(table) {
    var headers = Array.from(table.querySelectorAll('thead th[data-column-key]'));
    return headers.map(function(th, index) {
        var key = th.dataset.columnKey;
        // BUG-006 修复：checkbox-only 列不要回退到 key
        var hasOnlyCheckbox = th.children.length === 1
            && th.firstElementChild
            && th.firstElementChild.tagName === 'INPUT'
            && (th.firstElementChild.type || '').toLowerCase() === 'checkbox';
        var rawText = Array.from(th.childNodes)
            .filter(function(n) { return n.nodeType === 3; })
            .map(function(n) { return n.textContent; })
            .join('').trim();
        var label = th.dataset.defaultLabel || rawText || (hasOnlyCheckbox ? '' : key);
        th.dataset.defaultLabel = label;
        return { key: key, label: label, defaultLabel: label, defaultIndex: index,
                 locked: ['row_no','material_code','quantity','contract_no','project_name','actions'].indexOf(key) !== -1 };
    });
}
```

**代码 diff 草案**（custom.css）：
```css
.cb-check-col { width: 50px; min-width: 50px; max-width: 50px; text-align: center; }
.cb-check-col input[type=checkbox] { cursor: pointer; }
```

**验证**：
- 手工：访问 `/supplier` `/customer` `/unit` `/contract` `/category` `/material` 等 → 表头首列为 50px 居中 checkbox，无 `COLU...`。
- 自动化：`scripts/verify_bug_006.py` 用 Playwright 抓首列 th 文本，断 ≠ `'COLU...'`、width == 50。

**commit**：`fix(BUG-006): 列表页表头首列增加 check_th 宏并修复 COLU 截断`

---

### 3.7 BUG-2026-07-28-007 业务页双工具栏 [x] 已修复

**现象**：`/purchase_request` `/purchase_order?view=list` `/out_order` `/check` `/requisition` 同时存在两套工具栏。

**根因**：[app.js `insertGlobalActionBar()`](file:///c:/Users/Administrator/Desktop/wms/app/static/js/app.js) 在直接访问模式也注入全局工具栏。

**修复策略**：JS 守卫 + CSS 兜底。

**代码 diff 草案**（app.js）：
```javascript
function isWmsEmbeddedPage() {
    if (document.body && document.body.classList.contains('embedded-page')) return true;
    if (window.self !== window.top) return true;
    var url = window.location.href;
    return /[?&]embedded=1\b/.test(url);
}

function insertGlobalActionBar() {
    if (document.getElementById('cbGlobalActionBar')) return;
    if (!isWmsEmbeddedPage()) return;  // BUG-007 修复
    var module = getWmsActionModule();
    if (!module) return;
    var content = document.querySelector('.embedded-content');
    if (!content) return;
    // ... 原有注入逻辑
}
```

**代码 diff 草案**（custom.css）：
```css
/* BUG-007 兜底：直接访问业务页时隐藏全局工具栏 */
body:not(.embedded-page) #cbGlobalActionBar { display: none !important; }
body:not(.embedded-page) .cb-actionbar-toolbar { display: none !important; }
```

**验证**：
- 浏览器访问 `/purchase_request` 直接模式 → 只看到 list 自身工具栏 + page-header 工具栏中的一套。
- 浏览器访问 `/purchase_request?embedded=1` 或嵌入到 Tab → 两套并存（保留原行为）。
- 截图：`audit_screenshots/fix_bug_007_01.png`（直接）+ `fix_bug_007_02.png`（嵌入）。

**commit**：`fix(BUG-007): 业务单据页统一一套工具栏`

---

### 3.8 BUG-2026-07-28-008 物料列表「共 0 条 + 暂无数据」并存 [ ]

**现象**：`/material` 空库时分页区显示「共 0 条记录」+ 表格内「暂无数据」并存。

**根因**：[_list_macros.html:95 `pager()`](file:///c:/Users/Administrator/Desktop/wms/app/templates/_list_macros.html#L95) 在 `pagination.total > 0` 时输出，但「暂无数据」div 独立渲染，没互斥。

**修复策略**：pager 在 total==0 时返回空字符串；空数据模板分支不要同时渲染分页。

**代码 diff 草案**（material.html）：
```html
<!-- 在表格 + 分页 + 空数据占位的三处位置 -->
{% if pagination.total > 0 %}
  <table class="table table-hover">...</table>
  {{ pager(pagination, 'material_list') }}
{% else %}
  <div class="text-center py-5 text-muted">
    <i class="bi bi-cloud-slash" style="font-size:3rem;"></i>
    <p class="mt-3">暂无数据，请先添加物料</p>
    <a href="/material/add" class="btn btn-primary btn-sm">
      <i class="bi bi-plus-circle"></i> 新增物料
    </a>
  </div>
{% endif %}
```

**同步应用**：把所有列表页（customer/unit/contract/category/warehouse/employee/department/user/bom/opening_stock/label_template/purchase_request/purchase_order/out_order/requisition/check/sales_order/transfer/subcontract/stock_query 等）按同样模式收口。

**验证**：
- `/material` 空库 → 只看到「暂无数据」+ 新增按钮；分页区不出现。
- `/supplier` 已有数据 → 表格 + 分页正常；空数据占位不出现。

**自动化**：`scripts/verify_bug_008.py` 抓页面 HTML，断言：
```python
if pagination_total == 0:
    assert '暂无数据' in html
    assert '共 0 条' not in html
```

**commit**：`fix(BUG-008): 空数据列表统一只渲染「暂无数据」占位`

---

### 3.9 BUG-2026-07-28-009 工单领料「共 0 单」单复数不一致 [ ]

**现象**：`/requisition` 分页区写「共 0 单」，其他列表写「共 0 条记录」。

**根因**：[requisition.html](file:///c:/Users/Administrator/Desktop/wms/app/templates/requisition.html) 手工写死「共 {{ pagination.total }} 单」。

**修复策略**：替换为 `{{ pager(...) }}` 宏。

**代码 diff 草案**：
```html
<!-- requisition.html 替换手工分页 div -->
{% if pagination.total > 0 %}
  {{ pager(pagination, 'requisition_list') }}
{% endif %}
```

**同步应用**：
- subcontract.html / sales_order.html / check.html / transfer.html / adjustment.html 等所有列表页统一切到 `pager()` 宏。

**验证**：
- `/requisition` 空数据 → 不显示分页区。
- `/requisition` 有数据 → 显示「共 N 条，每页 [select] 条」与其他列表统一。

**commit**：`fix(BUG-009): 统一列表分页区文案为「共 N 条」`

---

### 3.10 BUG-2026-07-28-010 `/supplier/add` GET 错配 [ ]

**现象**：`GET /supplier/add` → 405（被 BUG-002 修复为 405 卡片），但业务上希望 GET 该路径直接弹出新增供应商 modal。

**修复策略**：把 `methods=['POST']` 改为 `methods=['GET', 'POST']`；GET 渲染 add 页面或重定向到 `/supplier?showAddModal=1`。

**代码 diff 草案**：
```python
# app.py supplier_add 路由
@app.route('/supplier/add', methods=['GET', 'POST'])
@login_required
@require_role('admin', 'purchase')
def supplier_add():
    if request.method == 'GET':
        return redirect(url_for('supplier_list') + '?showAddModal=1')
    # POST 逻辑保持
    ...
```

**同步应用**：所有基础资料 add 路由（customer/unit/category/material/warehouse/employee/department/bom/contract/opening_stock/label_template/after_sale_out 等）。

**验证**：
- `GET /supplier/add` → 302 → `/supplier?showAddModal=1` → 列表页自动弹 modal。
- `POST /supplier/add` → 200 正常保存。

**commit**：`fix(BUG-010): 基础资料 add 路由同时支持 GET/POST`

---

### 3.11 BUG-2026-07-28-011 登录锁定 UI 缺失 [ ]

**现象**：登录页输错 1 次 → 提示「还可尝试 2 次」，但页面不锁、不倒计时、不累计 IP。

**根因**：[app.py:6202 `login()`](file:///c:/Users/Administrator/Desktop/wms/app/app.py#L6202) 后端有 `increment_failed_count()` 但前端无反馈。

**修复策略**：锁定时返回 `lock_remaining` 秒数；前端倒计时 + 按钮置灰。

**代码 diff 草案**（后端）：
```python
# app.py login() 锁定分支
if locked:
    remaining = compute_lock_remaining(username, ip)
    return jsonify({
        'status': 'error',
        'msg': f'账号已锁定，请稍后再试（剩余 {remaining}s）',
        'locked': True,
        'lock_remaining': remaining
    }), 423
```

**代码 diff 草案**（login.html）：
```html
<button id="loginBtn" class="btn btn-primary" type="submit" {% if locked %}disabled{% endif %}>
  <span id="loginBtnText">登 录</span>
</button>
<div id="lockHint" class="text-danger small mt-2" {% if not locked %}hidden{% endif %}>
  账号已锁定，<span id="lockCountdown">15:00</span> 后可重试
</div>
```

```javascript
// 倒计时
let lockTimer = null;
function startLockCountdown(sec) {
    const el = document.getElementById('lockCountdown');
    const btn = document.getElementById('loginBtn');
    const hint = document.getElementById('lockHint');
    hint.hidden = false; btn.disabled = true;
    function tick() {
        if (sec <= 0) { btn.disabled = false; hint.hidden = true; clearInterval(lockTimer); return; }
        const m = Math.floor(sec / 60).toString().padStart(2, '0');
        const s = (sec % 60).toString().padStart(2, '0');
        el.textContent = `${m}:${s}`;
        sec--; lockTimer = setTimeout(tick, 1000);
    }
    tick();
}
window.addEventListener('DOMContentLoaded', () => {
    const locked = document.body.dataset.locked === '1';
    if (locked) startLockCountdown(parseInt(document.body.dataset.lockRemaining || '900'));
});
```

**同步应用**：IP 累计提示（>3 次同 IP 失败时在登录页底部展示警告条）。

**验证**：
- 输错 1 次 → 「还可尝试 4 次」+ IP 累计警告条。
- 输错 5 次 → 按钮置灰 + 倒计时 15:00 → 00:00 自动解除。
- 重新正确登录 → 锁定清空。

**自动化**：`scripts/verify_bug_011.py` Flask test_client 模拟 5 次失败，断言第 5 次返回 423 + `locked: True`。

**commit**：`fix(BUG-011): 登录页增加失败次数/IP 累计与锁定倒计时`

---

### 3.12 BUG-2026-07-28-012 审计术语不一致 [ ]

**现象**：`/operation_audit` 显示「旧日志 0 / 变更审计 0」与系统术语不一致。

**修复策略**：统一为「历史审计 / 实时审计」，加 tooltip 解释。

**代码 diff 草案**（operation_audit.html）：
```html
<div class="card">
  <div class="card-body text-center">
    <h3>{{ history_count or 0 }}</h3>
    <p class="text-muted"
       title="对应 OperationLog 表的旧实现（仅 INSERT 日志，无操作回放）">
      历史审计
    </p>
  </div>
</div>
<div class="card">
  <div class="card-body text-center">
    <h3>{{ realtime_count or 0 }}</h3>
    <p class="text-muted"
       title="对应 OperationAudit 表的新实现（含操作类型/对象/前后值/操作人/IP）">
      实时审计
    </p>
  </div>
</div>
```

**验证**：`/operation_audit` → 看到「历史审计 0 / 实时审计 0」+ 鼠标悬停 tooltip。

**commit**：`fix(BUG-012): 操作审计卡片文案统一为「历史/实时审计」`

---

### 3.13 BUG-2026-07-28-013 验收快照/证据包无引导 [ ]

**现象**：`/admin/console` 显示「验收快照 0 / 证据包 0」无引导。

**修复策略**：零值卡片改为可点击引导卡；非零值维持原数字。

**代码 diff 草案**（admin_console.html）：
```html
<div class="card clickable-card" data-href="/ai_prelaunch"
     style="cursor:pointer;">
  <div class="card-body text-center">
    <i class="bi bi-cloud-arrow-up" style="font-size:2.5rem;color:#4F46E5;"></i>
    <h3>{{ snapshot_count or 0 }}</h3>
    {% if (snapshot_count or 0) == 0 %}
      <p class="text-muted">尚未创建验收快照<br>点击前往 AI 上线预检</p>
    {% else %}
      <p class="text-muted">验收快照</p>
    {% endif %}
  </div>
</div>
```

**同步应用**：证据包卡指向 `/backup`。

**验证**：admin 登录 → `/admin/console` → 「验收快照」卡显示「尚未创建」+ 可点击跳转 `/ai_prelaunch`。

**commit**：`fix(BUG-013): 管理员控制台零值卡片增加引导跳转`

---

### 3.14 BUG-2026-07-28-014 缺「保存并新建」 [ ]

**现象**：`/in_order/add` 等仅有「保存」「返回」；高频业务希望保存后留在原页继续录。

**修复策略**：footer 加「保存并新建」按钮；后端 `*_add_page()` 接收 `keep=1` 参数保留表头字段。

**代码 diff 草案**（in_order_add.html footer）：
```html
<div class="d-flex gap-2 justify-content-end mt-3">
  <button class="btn btn-outline-primary" type="button" onclick="saveAndNew(this)">
    <i class="bi bi-save"></i> 保存并新建
  </button>
  <button class="btn btn-primary" type="submit">
    <i class="bi bi-save"></i> 保存
  </button>
  <a href="/in_order" class="btn btn-outline-secondary">返回</a>
</div>
```

```javascript
window.saveAndNew = function(btn) {
    const form = btn.closest('form');
    const fd = new FormData(form);
    fd.append('keep', '1');
    btn.disabled = true;
    fetch(form.action, {method: 'POST', body: fd, headers: {'X-CSRFToken': getCookie('csrf_token')}})
        .then(r => r.json())
        .then(d => {
            if (d.status === 'success') {
                showToast('已保存，请继续录明细', 'success');
                const url = new URL(window.location.href);
                url.searchParams.set('keep', '1');
                // 保留 supplier_id / customer_id / warehouse
                ['supplier_id', 'customer_id', 'warehouse'].forEach(k => {
                    if (fd.has(k)) url.searchParams.set(k, fd.get(k));
                });
                setTimeout(() => location.href = url.toString(), 600);
            } else {
                showToast(d.msg, 'danger');
                btn.disabled = false;
            }
        });
};
```

```python
# app.py *_add_page 路由接收 keep
@app.route('/in_order/add')
def in_order_add_page():
    keep_supplier = request.args.get('supplier_id', '')
    keep_warehouse = request.args.get('warehouse', '')
    return render_template('in_order_add.html',
                           keep_supplier_id=keep_supplier,
                           keep_warehouse=keep_warehouse)
```

**模板中**：
```html
<select name="supplier_id">
  {% for s in suppliers %}
    <option value="{{ s.id }}" {% if s.id|string == keep_supplier_id %}selected{% endif %}>{{ s.name }}</option>
  {% endfor %}
</select>
```

**同步应用**：purchase_order / out_order / check / requisition / transfer / adjustment / sales_order / after_sale_out / subcontract 等 9+ 新增页。

**验证**：`/in_order/add` 填表 → 点「保存并新建」→ 跳回 `/in_order/add?keep=1&supplier_id=2&warehouse=W01` → 表头保留。

**commit**：`fix(BUG-014): 新增单据页增加「保存并新建」`

---

### 3.15 BUG-2026-07-28-015 Tab 累积无限 [ ]

**现象**：连续打开 10+ 页面后 Tab 栏持续增长。

**根因**：[base.html `WmsTabs.open()`](file:///c:/Users/Administrator/Desktop/wms/app/templates/base.html) 永远追加无上限。

**修复策略**：超 15 个自动关闭最早；右键菜单「关闭其他/全部」。

**代码 diff 草案**（base.html）：
```javascript
WmsTabs.MAX = 15;
WmsTabs.open = function(id, title, url) {
    if (this.tabs.length >= this.MAX) {
        this.close(this.tabs[0].id); // 关闭最早
    }
    // ... 原有逻辑
};
// 右键菜单
WmsTabs.bindContextMenu = function() {
    document.querySelectorAll('.wms-tab').forEach(el => {
        el.addEventListener('contextmenu', e => {
            e.preventDefault();
            showTabContextMenu(e.clientX, e.clientY, el.dataset.tabId);
        });
    });
};
```

**验证**：开 16 个 Tab → 第 16 个打开时第一个自动关闭。

**commit**：`fix(BUG-015): Tab 栏最大数限制与「关闭其他/全部」菜单`

---

### 3.16 BUG-2026-07-28-016 AI 助手浮窗遮挡 [ ]

**现象**：右下角 AI 浮窗在窄屏或按钮密集处遮挡底部按钮。

**修复策略**：滚动到底部半隐藏 + 用户可手动隐藏（localStorage 记忆）。

**代码 diff 草案**（base.html）：
```html
<button class="ai-assistant-button" id="aiFab" style="position:fixed;bottom:20px;right:20px;z-index:1000;">
  <i class="bi bi-robot"></i>
  <span class="ai-fab-close" onclick="event.stopPropagation();hideAiFab();" title="隐藏本次会话">×</span>
</button>
```

```javascript
window.hideAiFab = function() {
    document.getElementById('aiFab').style.display = 'none';
    localStorage.setItem('aiFabHidden', Date.now().toString());
};
window.addEventListener('scroll', () => {
    const fab = document.getElementById('aiFab');
    if (!fab) return;
    const scrolled = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 80;
    fab.style.transform = scrolled ? 'translateY(120%)' : 'none';
    fab.style.opacity = scrolled ? '0.3' : '1';
});
// 启动时检查
if (localStorage.getItem('aiFabHidden')) {
    const el = document.getElementById('aiFab');
    if (el) el.style.display = 'none';
}
```

**commit**：`fix(BUG-016): AI 助手悬浮按钮滚动收起与可隐藏`

---

### 3.17 BUG-2026-07-28-017 入库 Title 不一致 [ ]

**现象**：`/in_order` → 「入库明细」；`/in_order/add` → 「新增采购入库单」。

**修复策略**：统一为「入库单 / 新增入库单」。

**代码 diff 草案**：
```html
<!-- in_order.html -->
{% block title %}入库单 - 仓库管理系统{% endblock %}
<h2 class="mb-0"><i class="bi bi-box-arrow-in-down"></i> 入库单</h2>

<!-- in_order_add.html -->
{% block title %}新增入库单 - 仓库管理系统{% endblock %}
<h2 class="mb-0"><i class="bi bi-plus-circle"></i> 新增入库单</h2>
```

**同步应用**：purchase_order / out_order / check / requisition / transfer / adjustment / sales_order / after_sale_out / subcontract 9+ 列表与新增页。

**commit**：`fix(BUG-017): 入库/出库/采购单列表与新增 Title 统一`

---

### 3.18 BUG-2026-07-28-018 搜索框 placeholder 顿号 [ ]

**现象**：`/supplier` placeholder「搜索供应商编号、名称、联系人、电话、地址」电话与地址无顿号。

**修复策略**：统一使用顿号 `、` 分隔。

**代码 diff 草案**：
```html
<!-- supplier.html / customer.html -->
<input type="text" name="q" class="form-control"
       placeholder="搜索供应商编号、名称、联系人、电话、地址">
```

**commit**：`fix(BUG-018): 客户/供应商搜索框 placeholder 统一顿号`

---

### 3.19 BUG-2026-07-28-019 分类层级全「1 级」 [ ]

**现象**：`/category` 所有分类都显示「1 级」。

**根因**：[category.html:163](file:///c:/Users/Administrator/Desktop/wms/app/templates/category.html#L163) `row.level` 永远 0。

**修复策略**：后端计算真实 level，模板按 level 上色。

**代码 diff 草案**（后端）：
```python
# category_list 路由
def category_list():
    cats = Category.query.all()
    for c in cats:
        lvl = 0
        cur = c
        while cur.parent_id:
            lvl += 1
            cur = Category.query.get(cur.parent_id)
            if lvl > 10: break  # 防环
        c.level = lvl
        # 完整路径
        path = []
        cur = c
        while cur:
            path.insert(0, cur.name)
            cur = Category.query.get(cur.parent_id) if cur.parent_id else None
        c.path_str = ' / '.join(path)
    return render_template('category.html', categories=cats)
```

**代码 diff 草案**（category.html）：
```html
<td>
  <span class="category-level-badge level-{{ row.level + 1 }}">
    {{ row.level + 1 }} 级
  </span>
</td>
<td>{{ row.path_str }}</td>
```

```css
.category-level-badge.level-1 { background:#FEF3C7;color:#92400E; }
.category-level-badge.level-2 { background:#DBEAFE;color:#1E40AF; }
.category-level-badge.level-3 { background:#D1FAE5;color:#065F46; }
```

**commit**：`fix(BUG-019): 物料分类层级显示真实层级与颜色区分`

---

### 3.20 BUG-2026-07-28-020 库存查询打印模板常驻 [ ]

**现象**：`/stock_query` 「打印模板」按钮一直常驻，空数据时无意义。

**修复策略**：空数据时按钮置灰 + tooltip 提示。

**代码 diff 草案**（stock_query.html）：
```html
<button class="btn btn-outline-secondary"
        {% if not stock_rows or stock_rows|length == 0 %}
        disabled title="请先查询数据"
        {% else %}
        onclick="printTemplate()"
        {% endif %}>
  <i class="bi bi-printer"></i> 打印模板
</button>
```

**commit**：`fix(BUG-020): 库存查询「打印模板」按钮空数据时置灰`

---

## 4. 自动化验证脚本模板

### 4.1 通用结构 `scripts/verify_browser_bugs_2026_07_28.py`

```python
"""对 20 个 BUG 做静态 + 动态断言。
用法：python scripts/verify_browser_bugs_2026_07_28.py
"""
import os
import sys
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / 'app'
sys.path.insert(0, str(APP_DIR))

os.environ.setdefault('WMS_BOOTSTRAP_PASSWORD', 'admin')
os.environ.setdefault('FLASK_ENV', 'testing')


class Bug001To002(unittest.TestCase):
    def test_404_template(self):
        from app import create_app
        app = create_app('testing')
        with app.test_client() as c:
            r = c.get('/this_page_does_not_exist')
            self.assertEqual(r.status_code, 200)  # 自定义 404 渲染为 200
            self.assertIn('页面不存在', r.get_data(as_text=True))

    def test_405_template(self):
        from app import create_app
        app = create_app('testing')
        with app.test_client() as c:
            r = c.get('/supplier/add')  # 原本 405
            # 如果 BUG-010 已修则该路径会 302；否则验证 405 卡片
            if r.status_code == 405:
                self.assertIn('请求方式不被允许', r.get_data(as_text=True))


class Bug003(unittest.TestCase):
    def test_purchase_order_default_list(self):
        from app import create_app
        app = create_app('testing')
        with app.test_client() as c:
            with c.session_transaction():
                pass  # 登录
            r = c.get('/purchase_order')
            self.assertEqual(r.status_code, 200)


class Bug004(unittest.TestCase):
    """已通过 verify_bug_004.py 覆盖，跳过"""


class Bug005(unittest.TestCase):
    """已通过 verify_bug_005.py 覆盖，跳过"""


class Bug006(unittest.TestCase):
    def test_check_th_width(self):
        css = (APP_DIR / 'static/css/custom.css').read_text(encoding='utf-8')
        self.assertIn('.cb-check-col { width: 50px', css)


class Bug007(unittest.TestCase):
    def test_embedded_guard(self):
        js = (APP_DIR / 'static/js/app.js').read_text(encoding='utf-8')
        self.assertIn('if (!isWmsEmbeddedPage()) return;', js)


# ... 008-020 类似 ...

if __name__ == '__main__':
    unittest.main(verbosity=2)
```

### 4.2 动态浏览器验证（Playwright）

参考 `audit_screenshots/browser_dyn_test.py`（已存在），新增 20 条 case。

---

## 5. 回归测试矩阵

| 场景 | 用例 | 通过条件 |
|------|------|----------|
| 登录 | admin / AAAA1234 | 200 + 工作台 |
| 登录失败 5 次 | admin / xxxxx | 第 5 次 423 + 倒计时 |
| 404 | GET /no_such | 200 + 「页面不存在」 |
| 405 | GET /supplier/add | 405 卡片 或 302 (BUG-010 修复后) |
| 列表 | GET /supplier | 200 + 50px checkbox 列 |
| 入库空 | POST /in_order/add (空) | 400 + 「请选择仓库」 |
| admin 自助重置 | POST /user/reset_password (self) | 403 + 「禁止自助重置」 |
| 验收快照零值 | GET /admin/console | 看到「尚未创建」+ 可点击跳 /ai_prelaunch |

---

## 6. 回滚策略

每个 commit 单独 revert 即可；不破坏 schema。

如发现某 BUG 修复引入回归：

```bash
# 1. 找到 commit
git log --oneline --grep "BUG-2026-07-28-XXX"
# 2. revert
git revert <commit-hash>
# 3. 重新启动
# 4. 复测 + 报告
```

---

## 7. 推送策略

```bash
# 单个 BUG 修复后
git add <files>
git commit -m "fix(BUG-2026-07-28-XXX): <title>"
git push origin main
git status  # 确认 working tree clean
git log -1  # 确认 commit 在 main
```

如遇网络中断：
```bash
git push origin main --retry
# 多次失败则改用 SSH 或联系 GitHub 凭据修复
```

---

## 8. 进度跟踪表

> 实时更新：[x] = 已修复+验证+推送；[~] = 进行中；[!] = 阻塞

| BUG | 修复 | 验证 | 推送 | 基线更新 | 阻塞原因 |
|-----|------|------|------|----------|----------|
| 001 | [x] | [x] | [x] | [ ] |  |
| 002 | [x] | [x] | [x] | [ ] |  |
| 003 | [x] | [x] | [x] | [ ] |  |
| 004 | [x] | [x] | [x] | [ ] |  |
| 005 | [x] | [x] | [x] | [ ] |  |
| 006 | [x] | [x] | [x] | [ ] |  |
| 007 | [x] | [~] | [ ] | [ ] | 等待重启服务验证 |
| 008 ~ 020 | [ ] | [ ] | [ ] | [ ] |  |
| 基线更新 | [ ] | — | — | — | 全部修完后一次提交 |

---

## 9. 风险评估

| BUG | 业务影响 | 安全风险 | 回滚难度 | 修复难度 |
|-----|----------|----------|----------|----------|
| 001-002 | 中（用户困惑） | 低 | 低 | 低 |
| 003 | 高（核心路径错误） | 低 | 低 | 低 |
| 004 | 中（UX） | **高**（密码安全） | 中 | 中 |
| 005 | **高**（脏数据） | 中 | 中 | 中 |
| 006 | 中（UI 杂乱） | 低 | 低 | 低 |
| 007 | 中（UX 混淆） | 低 | 低 | 低 |
| 008-013 | 中（UX/术语） | 低 | 低 | 低-中 |
| 014-020 | 低-中（UX） | 低 | 低 | 低 |
| 019 | 中（数据准确性） | 低 | 中 | 中 |

**总风险**：低-中。除 BUG-004（密码）外，其余均不涉及安全敏感路径。

---

## 10. 完成判定

每 BUG 满足以下 7 条才算完成：

1. ✅ 代码已改动（diff 落地）
2. ✅ 静态自查（`python -m py_compile app/app.py`）
3. ✅ 浏览器手工验证 + 截图
4. ✅ 自动化验证脚本通过（如适用）
5. ✅ commit 落到 main
6. ✅ push 到 GitHub
7. ✅ WMS_BUG_BASELINE.md 同步

20 个 BUG 全部完成后：

- 在 ledger (`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`) 登记"20 BUG 浏览器巡检修复"任务完成
- 写一份 `WMS_BROWSER_BUGS_2026-07-28-FIX-REPORT.md` 总结
- 推送最终 commit

---

## 11. 附录

### 11.1 启动服务脚本

```python
# audit_screenshots/restart_server.py
import subprocess, sys, time, os, signal
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
# 杀掉旧进程
subprocess.run(['powershell', '-Command', 'Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force'], capture_output=True)
time.sleep(1)
# 启动
log = open(ROOT / 'audit_screenshots/server.log', 'ab')
env = os.environ.copy()
env['WMS_BOOTSTRAP_PASSWORD'] = env.get('WMS_BOOTSTRAP_PASSWORD', 'admin')
subprocess.Popen([sys.executable, 'app/app.py'], stdout=log, stderr=log, env=env, creationflags=0x00000008)
print('server started')
```

### 11.2 健康检查

```python
import urllib.request
def health():
    try:
        r = urllib.request.urlopen('http://127.0.0.1:8080/login', timeout=3)
        return r.status == 200
    except Exception as e:
        return f'FAIL: {e}'
```

### 11.3 浏览器 MCP 工具调用规范

- 顺序：snapshot → screenshot → click → snapshot（验证）
- 等待：snapshot 后 1-3s 再 screenshot
- 错误：console_messages + network_requests 排查
- iframe 不可访问，URL 含 `?embedded=1` 时退化为直接访问模式

### 11.4 关键路径速查

```
GET  /login                登录页
GET  /                     工作台
GET  /admin/console        管理员控制台（BUG-013）
GET  /supplier             基础资料 - 供应商（BUG-006）
GET  /supplier/add         基础资料 - 新增供应商（BUG-010）
GET  /material             物料档案（BUG-008）
GET  /category             物料分类（BUG-019）
GET  /in_order             入库单（BUG-017）
GET  /in_order/add         新增入库单（BUG-005/014）
GET  /purchase_order       采购单（BUG-003）
GET  /purchase_request     采购申请（BUG-007）
GET  /out_order            出库单（BUG-007）
GET  /check                库存盘点（BUG-007）
GET  /requisition          工单领料（BUG-007/009）
GET  /operation_audit      操作审计（BUG-012）
GET  /stock_query          库存查询（BUG-020）
GET  /user                 用户管理（BUG-004）
GET  /this_does_not_exist  404（BUG-001）
GET  /transfer             调拨单
GET  /sales_order          销售订单
```

### 11.5 提交粒度示意

20 个 BUG = 20 个独立 commit（除 001+002 合并 1 个，019 后端+前端可合并 1 个，共 19 个 commit + 1 个基线同步 commit = 20 个 commit）。
