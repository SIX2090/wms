# WMS 开发规范（DEVELOPMENT RULES）

> 目的：减少 BUG 数量，提升代码质量，让"加功能"不再"天天几十个 BUG"
> 适用范围：所有在 WMS 仓库 `SIX2090/wms` 工作的开发者
> 最后更新：2026-07-31

---

## 一、加新功能 checklist

每次加新功能前，**必须**逐条确认：

### 1.1 前端

- [ ] HTTP 请求统一用 `WMS.api`（`app/static/js/api.js`）
- [ ] 禁止直接 `fetch(` / `csrfFetch(`（除非在 `app.js` 顶部或 `base.html` 的统一封装里）
- [ ] 新增 `<form method="post">` 必须包含 `{{ form.csrf_token }}` 或 `<input name="csrf_token" type="hidden" value="{{ csrf_token() }}">`
- [ ] 业务 JS 不留 `console.log` / `debugger` / `alert(`
- [ ] 业务 JS 不写 `eval(` / `new Function(`
- [ ] 用 `showToast(msg, 'success'|'danger')` 统一提示，不写 `alert(`

### 1.2 后端

- [ ] 新增 POST 路由必须有 `@login_required` 或 `@csrf.exempt`（带理由注释）
- [ ] **新增 POST/PUT/DELETE 路由必须用 pydantic `BaseModel` 做输入校验**（A8，门禁强制）
- [ ] **新增业务函数必须先写至少 1 个 pytest 失败测试**（A9，门禁强制）
- [ ] 不直接拼接 SQL，用 SQLAlchemy 参数化
- [ ] 不写 `print(` 调试（用 `app.logger.info()` 代替）
- [ ] 关键业务逻辑加 try/except + 业务日志

### 1.3 提交前

- [ ] 跑过 `python3 scripts/lint_wms_rules.py`，全部通过
- [ ] 跑过 `python3 scripts/verify_wms_bugs.py`，无 FAIL
- [ ] 跑过 `pytest tests/ -q`，全过
- [ ] 如果动了模板或路由，跑过 `python3 scripts/full_smoke_test.py`

---

## 二、修复 BUG 流程

### 2.1 登记

发现 BUG 后：

1. 在 `WMS_BUG_BASELINE.md` 添加一条
2. 格式：`BUG-YYYY-MM-DD-NNN: <标题>`
3. 状态：未修复

### 2.2 修复

1. commit message 写明：`fix(<模块>): BUG-YYYY-MM-DD-NNN <简述>`
2. 加一个回归测试（如果是 verify_wms_bugs 脚本能查的，就在那里加一条）
3. 在 `WMS_BUG_BASELINE.md` 把状态改为"已修复"

### 2.3 复盘（每月一次）

月底统计：

- 本月新增 BUG 数
- 按模块/类型分布
- 根因 Top 3
- 写进 `WMS_QUALITY_REPORT.md`

---

## 三、禁止事项（黑名单）

### 3.1 代码层面

- ❌ 业务 JS 裸调 `fetch(method: 'POST')`（必须 `csrfFetch` 或 `WMS.api`）
- ❌ 业务 JS 写 `console.log` / `debugger` / `alert(` / `eval(`
- ❌ 业务 Python 写 `print(`
- ❌ 业务 Python 字符串拼接 SQL
- ❌ `<form method="post">` 不带 csrf_token
- ❌ `@app.route(POST)` 不带 `@login_required` / `@csrf.exempt`

### 3.2 流程层面

- ❌ 直接 push 到 main 前不跑测试（不写 `--no-verify`）
- ❌ 修复 BUG 不写 commit message 关联 BUG ID
- ❌ 加新功能不更新文档/README

---

## 四、推荐做法

### 4.1 HTTP 请求

- ✅ 用 `WMS.api.get/post/put/delete(url, data)`
- ✅ 错误处理统一：`api.xxx().then().catch(err => showToast(err.message, 'danger'))`

### 4.2 CSRF

- ✅ 默认走 `base.html` 的全局 fetch 拦截器
- ✅ 长会话依赖 `base.html` 的 25 分钟自动刷新
- ✅ token 寿命不要再调（已稳定在 30min + 自动刷新）

### 4.3 调试

- ✅ Python 端用 `app.logger.info(msg)` 或 `app.logger.warning(msg)`
- ✅ JS 端用临时的 `console.log`，提交前删除
- ✅ 复杂 bug 用 debugger，但提交前必须删除

### 4.4 错误处理

- ✅ 业务逻辑抛业务异常（带用户可读 msg）
- ✅ 路由层统一捕获 + 返回 JSON 或友好页面
- ✅ 用 `try/except` 包裹外部调用（DB、API、文件 IO）

---

## 五、CI / pre-commit 门禁

| 工具 | 检查内容 | 必跑 |
|---|---|---|
| `scripts/lint_wms_rules.py` | 9 条防 BUG 规则 | ✅ pre-commit |
| `scripts/lint_no_raw_post_fetch.py` | 裸调 fetch 检查 | ✅ pre-commit |
| `scripts/verify_wms_bugs.py` | 86 项静态回归 | ✅ pre-commit |
| `pytest tests/` | 90 项黄金测试 | ✅ pre-commit |
| `scripts/full_smoke_test.py` | 121 项冒烟 | 推荐（需启动服务） |

pre-commit 钩子位置：`.githooks/pre-commit`
启用命令（一键脚本，**推荐**）：`bash .githooks/install-hooks.sh`
启用命令（手动等效）：`git config core.hooksPath .githooks`
验证启用：`python3 scripts/check_hooks_installed.py`

跳过钩子（紧急情况）：`git commit --no-verify`（**不推荐，会绕过所有检查**）
不要主动 `git config --unset core.hooksPath`（绕过检查，等于把责任全推给 CI）

---

## 六、防 BUG 规则清单

`scripts/lint_wms_rules.py` 共 10 条规则，每条独立可开关：

| 编号 | 规则 | 防的 BUG | 扫描范围 |
|---|---|---|---|
| **A1** | `<form method="post">` 必须有 csrf_token | 表单 400 / 死循环 | `app/templates/*.html` |
| **A2** | Python POST 路由必须 `@login_required` 或 `@csrf.exempt` | 漏 CSRF 保护 | `app/**/*.py`（除 `app/ai/`） |
| **A3** | 业务 JS 不能 `console.log` | 调试代码泄漏 | `app/static/js/*.js` |
| **A4** | 业务 JS 不能 `debugger` / `alert` | 调试残留 / 体验差 | `app/static/js/*.js` |
| **A5** | 业务 JS 不能 `eval` / `new Function`（严格） | XSS / 注入 | `app/static/js/*.js` |
| **A6** | 业务 Python 不能 `print` | 调试代码污染日志 | `app/**/*.py`（除 `app/ai/` 与 runner 脚本） |
| **A7** | SQL 必须参数化，禁止字符串拼接（严格） | SQL 注入 | `app/**/*.py`（除 `app/ai/`） |
| **A8** | **新增** POST/PUT/DELETE 路由必须用 pydantic `BaseModel` 输入校验 | 数据类型 BUG / 字段漂移 | `app/**/*.py`（除 `app/ai/`，仅看 git staged 新增行） |
| **A9** | **新增** 业务函数必须在 `tests/` 至少有 1 个对应 pytest 测试 | 未测试代码上线 | `app/**/*.py`（除 `app/ai/`，仅看 git staged 新增行） |
| **A10** | **新增** `app/app.py` 禁止新增 `@app.route` 路由，强制走 `app/routes/` 模块 | app.py 重新膨胀 / 可维护性下滑 | `app/app.py`（仅看 git staged 新增行） |

### 6.1 白名单与例外

- **A1**：`app/templates/csrf_error.html` 是 CSRF 错误页，本身不写 form；其它 form 可加注释 `<!-- nocsrf:reason -->` 豁免。
- **A2**：登录前的端点（`/api/login`、`/api/csrf_refresh`、`/api/webhook/*`、`/wechat/*`、`/login`）豁免。
- **A3**：行尾加 `// allow-console` 注释可豁免。
- **A4**：`debugger;` 加 `// allow-debugger`，`alert(` 加 `// allow-alert`。
- **A5**：完全禁止，无白名单。
- **A6**：行尾加 `# allow-print` 注释可豁免；`if __name__ == '__main__':` 块内不检查；`scripts/audit/*`、`scripts/benchmark_*`、`scripts/verify_*` 是测试脚本。
- **A7**：完全禁止，无白名单。必须用 SQLAlchemy 参数化（`text("..."), {"param": val}`）。
- **A8**：路由装饰器行/上一行/紧邻 `def` 行加 `# pydantic:reason=<理由>` 注释可豁免；登录/csrf/webhook/wechat 端点与 A2 一致豁免。
- **A9**：同行/上一行加 `# no-test:reason=<理由>` 注释可豁免；`_xxx` 内部 helper、`test_xxx` 测试函数、`__dunder__` 魔术方法、装饰器（`@property` / `@staticmethod` / `@classmethod`）以及路由函数（`@app.route` 装饰的 def）均不算"业务函数"。
- **A10**：`@app.route` 装饰器行/上一行/下一行加 `# route-in-app:reason=<理由>` 注释可豁免（用于确有必要留在 app.py 的极少数特殊端点）；存量路由不强制，仅拦 git staged 新增行。

### 6.2 排除路径

- A2 / A6 / A7 / A8 / A9 都排除 `app/ai/`（AI 子包）。
- A10 仅作用于 `app/app.py` 这一个文件，`app/routes/` 等其他文件天然不适用。
- A6 额外排除 `app/run_server.py`、`app/auto_update.py`、`app/restart.py`、`app/notifications.py`、`app/wechat_helper.py`（这些是 CLI / 启动 / 辅助脚本，`print` 是合法的运维输出）。
- A3 / A4 / A5 自动跳过 `app/static/js/lib/` 和 `xlsx.full.min.js` 等第三方库。
- **A8 / A9 / A10 是"新增代码生效"规则**：仅扫描 `git diff --cached` 的新增行（含 `--diff-filter=A` 新增文件），存量代码不会一次性报几百条违规。

---

## 六点五、为什么强制 pydantic + 测试

**为什么强制 pydantic**（A8）：

- 手工 `if not x: return error` 容易漏掉类型校验（数字/字符串混淆、None 检查遗漏）。
- 没有契约文档，前端 / 后端字段名/类型漂移几个月后才被业务用户发现。
- pydantic 一次给出 422 + 详细错误，避免脏数据进库。
- 团队 3 个月以来 BUG 数居高不下，根因 Top 3 之一就是"输入校验不全"。A8 是对症下药。

**为什么强制测试**（A9）：

- AI 写完函数直接 commit 到 `main`，没有红绿循环 → 上线后才发现 BUG。
- "我人工测过了" 不能替代自动化测试：每次重构、改字段、改 SQL 时人工测试 100% 漏掉。
- 仓库当前 `tests/` 覆盖率极低（仅 3 个文件），A9 强制每个新增业务函数至少有 1 个失败测试，逼迫 AI 写可验证的代码。
- 修复 BUG 时（A1-A7 触发的）也算"新增业务函数"，A9 顺带把回归测试也强制了。

写测试和写实现不矛盾——A9 不要求覆盖率 100%，只要求"新增的每个 def 至少 1 个 test_xxx 跑得过"。对"小工具函数"用 `_xxx` 命名直接豁免，对路由函数按 A2 走（不重复强制）。

---

## 七、新人上手

1. 克隆仓库：`git clone https://github.com/SIX2090/wms.git`
2. 启用 pre-commit：**`bash .githooks/install-hooks.sh`**（不要手动设、不要 unset）
3. 读 `README.md`、`AGENTS.md`、`DEVELOPMENT_RULES.md`、`WMS_BUG_BASELINE.md`
4. 看 `app/static/js/api.js` 了解 HTTP 调用方式
5. 跑测试：`python3 scripts/verify_wms_bugs.py` `pytest tests/ -q`
6. 验证钩子：`python3 scripts/check_hooks_installed.py`（应输出 `✓ core.hooksPath 已正确指向 .githooks`）

---

## 八、规则扩展流程

要新增一条防 BUG 规则：

1. 在 `scripts/lint_wms_rules.py` 加一个新 Rule 子类
2. 在 `RULES` 字典里注册
3. 更新本文档"防 BUG 规则清单"
4. 提 PR（如果未来加 review 制度）

---

## 九、版本

| 日期 | 修订 | 修订人 |
|---|---|---|
| 2026-07-31 | 初版（A1-A7 7 条规则） | AI + SIX2090 |
| 2026-07-31 | v2：新增 A8（pydantic 必填） + A9（必写测试） | AI + SIX2090 |
| 2026-08-05 | v3：新增 A10（app.py 禁止新增路由，防膨胀） | AI + SIX2090 |
