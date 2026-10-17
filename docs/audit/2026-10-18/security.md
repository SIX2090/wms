# WMS 安全审计报告（认证 / CSRF / 注入 / XSS / 密钥 / 文件 / 越权）

- 审计员：security（团队成员）
- 审计日期：2026-10-18
- 基线：main HEAD `0f8442b31e27845cac2f627424732624b0dba2a1`，版本 `2026.09.1`
- 方法：**纯静态只读分析**。本会话无法执行任何外部进程（pwsh 0xC0000142、python/git EPERM），全部结论来自 `glob/grep/read` 与 Node `fs` 正则扫描，未运行 pytest / 服务实例；凡需运行时才能定性的点，确认程度标注为 `高度可疑` 或 `风险提示`。
- 未改动 `app/`、`tests/` 任何代码；本文件为唯一产出。

---

## 1. 审计范围与覆盖度

### 1.1 量化矩阵（可复核的硬数字）

| 维度 | 扫描/统计结果 | 判定 |
|---|---|---|
| `app/` 下 .py 文件 | **167** 个（含 `app/ai/` 74、`app/routes/` 49） | 全量正则扫描 |
| Flask 路由装饰器总数 | **709**（`app/routes/` 615 + `app/app.py` 94）；其中 blueprint 装饰器 **42**（`app/ai/` 37、`unit.py` 5） | 逐条解析 |
| 写路由（POST/PUT/DELETE/PATCH） | **360**（`app/routes/` 317 + `app/app.py` 43） | 逐条解析 |
| 写路由**无任何**鉴权/CSRF 装饰器 | **1** = `app/routes/user_auth.py:70 login`（A2 内置豁免路径，且受全局 `CSRFProtect` 保护 + 表单带 csrf_token） | 无裸奔 |
| 写路由无**显式角色**装饰器 | **30**：自服务 3（改密/资料/登录）、查询型 POST 15、仅 `web_or_api_required` 3、Bearer 前后端 4、`csrf.exempt` 但函数体内鉴权 3、`csrf.exempt` 匿名设计 2（`/api/csrf_refresh`、`/api/mobile/crash_report`） | 逐条归类后无越权缺口 |
| GET 路由无鉴权装饰器 | **15**：`/healthz`（设计免认证）、`/mobile/app`（APK 下载，设计免认证）、ptoken 打印页 4（`print_token_or_login_required`）、微信助手 2（`X-Wechat-Helper-Token` 强校验）、`api_options`（请求期注入 `web_or_api_required`）、native_api 4（`api_role_required` Bearer） | 无未授权页面 |
| `csrf.exempt` 站点 | **43** 处（其中 1 处是按 URL 前缀的批量循环 `app/app.py:3463-3467`，实际豁免 13 条 `/mobile/api/*`） | 见 P2-2 |
| A1：模板 `form method=post` | **30** 个，缺 `csrf_token` 的 **0** 个 | 通过 |
| A3/A4/A5：业务 JS | `console.log` 2（均带 `allow-console`/文档注释）、`alert` 6（均带 `allow-alert`）、`debugger/eval/new Function` **0** | 通过 |
| A6：`print(` | 50 处，全部位于启动/运维脚本或带 `allow-print` | 通过 |
| A7：SQL 拼接 | `execute/executemany` **449** 处；`text()` **24** 处（其中 18 处是 PIL `draw.text`）；f-string 拼**用户输入**进 SQL：**0** 处 | 见 1.3 已复核项 |
| 密钥/凭证文件 | `.git/index` 内不含 `instance/`、`.env`、`*.db`、`*.bak`、`secret_key`、`uploads/`（0 命中）；`.gitignore` 已覆盖 | 无入库泄露 |
| 硬编码凭证字面量 | 全仓库 password/secret/api_key/token = '...' 模式 **3** 命中，逐一核实均为误报/说明文本 | 无硬编码凭证 |

### 1.2 精读清单（读过实现，不只是 grep）

- 配置与安全基础设施：`app/config.py`（全文 159 行）、`app/rate_limit.py`（全文）、`app/app.py` 安全相关区域约 60 处：SECRET_KEY/CSRF/cookie 启动校验（3050-3130、3297-3316）、security headers（3557-3571）、`@app.before_request` ×5（4395-4481）、errorhandler ×4（4522-4614）、`@login_manager`/`get_request_ip`/`hash_access_token`/`get_bearer_user`/`api_role_required`/`web_or_api*`/`role_required`（6852-7092）、`validate_password_strength`（7855）、secret 加解密 Fernet（12652-12698）、备份/上传/打印模板/OCR/微信助手/门户 20 余处；`app.py` 内 43 条写路由的装饰器逐条核对。
- 路由模块：`user_auth.py`（全文 846 行：登录/限流/改密/用户管理/密码重置）、`label_barcode.py`、`print_queue.py` 认证与打印段、`print_template_center.py`（全文）、`print_template_editor.py` 写段、`backup.py`（全文）+ `backup_catalog.py` 关键函数、`health.py`（全文）、`wechat_share.py` 认证段、`system_settings.py` 写段、`report.py` AI 洞察段、`mobile.py` 归档/上传/APK 段、`in_order.py`/`out_order.py` 打印与模板下载段、`options_api.py`、`ai/routes.py` 头部、`ai_excel.py`、`doc_print_excel.py`。
- 其他模块：`app/ai/security.py`（全文 557 行）、`app/utils.py` 上传/打印模板/打印令牌/HTML 净化（440-620、832-880）、`app/print_fill.py`、`app/document_evidence.py`（全文）、`app/local_print_agent.py` 子进程/CMD 段、`app/notifications.py` 头部、`app/startup_check.py`、`scripts/lint_wms_rules.py` 的 A1-A8 规则实现。
- 模板（136 个 HTML 抽样精读）：`base.html`（`escapeHtml`/`renderMarkdown`/`addMessage`，3031-3213）、`label_template_detail.html`、`print_in_with_html.html`/`print_out_with_html.html`、`report_dashboard.html`、`ai_supplier_evaluation.html`、`print_label.html`、`material.html` 归档段。
- JS（9 个业务 .js 全量 sink 扫描）：`app.js`/`api.js`/`excel-table.js`/`excel-import-export.js`/`quick-select.js` 的 37 处 `innerHTML` 赋值逐点判定。

### 1.3 已复核为**安全**的点（避免误报，逐条给证据）

1. **SQL 注入（A7）：0 处可达**。449 处 execute 中仅 20 处含字符串插值，全部为启动期迁移 DDL，表名/列名来自**硬编码元组**，值全部走 `?` 参数：`app/app.py:1270-1284`（`_header/_item/_fk` 四元组白名单）、`app/app.py:6122-6181`（builtins 两个表名白名单，注释与实现一致）、`app/app.py:2539`（`.format(limit=int(limit))` 已强转 int）。`app/ai/` 被 A7 规则排除，本次**人工补扫** app/ai 74 文件：无 `execute(f"..." )` / `text(f"...")` 命中。
2. **SSTI**：用户可编辑 HTML 打印模板经 `jinja2.sandbox.SandboxedEnvironment` + 白名单净化器渲染（`app/app.py:34952-34970`，`utils.py:461-486`），且 `create_print_template` 已强制 `template_type='excel'`（`app/app.py:34972-34990`）。`render_template_string` 仅用于服务端自建邮件 HTML。
3. **备份下载/删除路径穿越**：`backup_catalog.resolve_backup_file` 校验 source 白名单、拒绝 `/ \ : \0 ..`、拒绝重解析点、校验 `resolved.parent == root`、保护当前业务库（`backup_catalog.py:42-65`），且 `/backup/*` 全部 `login_required + require_role('admin')`（`routes/backup.py:33-45/104-108/118-120`）。
4. **上传**：扩展名白名单 + magic bytes + Pillow `verify()` + `uuid4().hex` 随机文件名（`utils.py:556-614`）；打印模板上传仅 .xlsx 且 `validate_template_file`（`print_template_center.py:232-241`）。物料档案图片删除仅需 warehouse 角色且无跨租户概念（单库）。
5. **密钥**：无硬编码 SECRET_KEY；未配置时 `instance/secret_key` 随机生成 + `chmod 600`，生产不可持久化且未显式放行则**拒绝启动**（`app/app.py:3061-3099`）；`WMS_DISABLE_CSRF` 在生产直接 `RuntimeError` 禁止（`config.py:93-95`）；API Key 用 Fernet 加密落库、明文仅响应一次性返显（`app.py:12652-12698`、`native_api.py:952-967`）；`.git/index` 无敏感路径。
6. **打印令牌 / Bearer 令牌 / 工作站令牌**：ptoken 为 `SECRET_KEY` 签名的 itsdangerous 短令牌（10 分钟）+ 绑定 `job_id`/单据 id（`utils.py:832-880`）；ApiToken/工作站 token 哈希存储、明文仅签发时返回一次（`app.py:6918-6969`、`print_queue.py:507-541`）；微信助手 token 走 Header + `secrets.compare_digest`（`app.py:25383-25390`）。
7. **登录链路**：`session.clear()` 后 `login_user`（会话固定防护，`user_auth.py:208-216`）、`remember` 由用户勾选（:213）、账号/IP 双维度锁定（:183-206、:236-257）、IP 级滑动窗口限流（:126-131 + `rate_limit.is_rate_limited`）、开放重定向有 `is_safe_redirect_target` 白名单（`app.py:6872-6890`）。密码重置强制复用强度校验、禁止自助重置自己、重置 admin 需 `WMS_BOOTSTRAP_PASSWORD` 二次确认且未配置时拒绝（`user_auth.py:791-846`）。
8. **AI 输出渲染主路径**：`base.html` 的 AI 对话渲染 `renderMarkdown` 第一步就 `escapeHtml(text)`，且不做 markdown 链接到 `<a href>` 的转换（`base.html:3041-3144`）→ 无 HTML/URL 注入面。AI 生成的单据草稿必须人工二次确认（`app.py:22706-22760`，R5 边界成立）。

### 1.4 未覆盖 / 未验证（明确声明）

- `app/android-native-wms/` 111 文件（Kotlin 端 token 明文存储、证书信任、WebView 配置）**未审计**。
- `app/ai/` 74 文件仅精读 `security.py` 与 `routes.py` 头部；`ai/tools/`、`ai/handlers.py`、`ai/documents/*` 的业务逻辑/提示词构造**未逐条审计**。
- `tests/` 688 个 py、`app/models/*` 字段定义（是否有明文敏感列）只做了抽查。
- 49 个 routes 中约 20 个只做了装饰器静态统计、未细读业务体（`subcontract.py`(45 写路由)/`in_order.py`/`out_order.py`/`check.py`/`adjustment.py`/`sales.py` 等）——其鉴权装饰器已核对，但**字段级越权/IDOR**未逐条验证。
- 前端 DOM XSS 仅做 sink 级扫描（37 处 innerHTML）+ 6 个高危模板精读，未逐行审 132 个模板的全部内联脚本。
- 所有运行时行为（CSRF 实际拦截、限流阈值、cookie 实际属性、模板渲染）标 `[需运行验证]`。

---

## 2. 结论摘要

| 级别 | 数量 |
|---|---|
| **P0 致命** | **0** |
| **P1 严重** | **1** |
| **P2 一般** | **6** |
| **P3 轻微** | **7** |
| 合计 | 14 |

**一句话总评**：认证/授权/CSRF/密钥/文件路径这几条主干做得扎实（360 条写路由无一裸奔、SQL 注入 0 处可达、备份与上传路径穿越均已防住、SSTI 走沙箱），**主要风险集中在"输出编码"与"安全控制接线"两类**：1 条可利用的存储型 XSS（标签模板 layout 直插 `<script>`），以及 `ai/security.py` 一整套安全能力**零调用**、AI 洞察前端未转义、CSRF 豁免与 Web 会话鉴权叠加等防御纵深缺口。未发现未授权访问、SQL 注入、任意文件读、明文凭证入库等 P0 级问题。

---

## 3. 详细 findings

### [P0] 无

本次未发现符合 P0 定义（数据错误/资金损失/未授权访问/注入/敏感信息泄露/生产不可用）的问题。依据：360 条写路由逐条装饰器核对后仅 `/login` 无装饰器（A2 官方豁免 + 全局 CSRF）；449 处 SQL 执行点无用户输入拼接；备份/上传/微信图片/打印模板下载均有白名单或包含性校验；.git/index 无敏感文件；未发现无鉴权的状态变更端点。**不排除** 1.4 未覆盖模块中存在 P0（Android 端、AI 工具层、IDOR）。

---

### [P1] 标签模板 layout 直插 `<script>` 导致存储型 XSS（可打到 admin 会话）

- 位置：`app/templates/label_template_detail.html:520`（sink）；写入点 `app/routes/label_barcode.py:50-52/70/80-83`、`app/routes/label_barcode.py:121-145`（两条写路径）；受害者入口 `app/routes/label_barcode.py:96-102`
- 现象：模板布局 JSON 以 **`|safe` 原样嵌入内联 `<script>`**，字符串值里的 `</script>` 会提前闭合脚本标签，后续内容被浏览器当 JS 执行 → 存储型 XSS。
- 证据：

~~~django
{# app/templates/label_template_detail.html:520 #}
let layoutData = {{ template.layout | default('{}') | safe }};
~~~
~~~python
# app/routes/label_barcode.py:70,80-83  （写路径 1：新增模板，layout 完全不校验）
layout = request.form.get('layout', '{}')
...
template = LabelTemplate(name=name, width=width, height=height,
                         cols=cols, rows=rows, is_default=is_default, layout=layout)
~~~
~~~python
# app/routes/label_barcode.py:138-145  （写路径 2：只校验是 dict/list，json.dumps 不转义 </script>）
layout = payload.get('layout')
if not isinstance(layout, (dict, list)):
    return jsonify({'status': 'error', 'msg': '布局数据格式不正确（必须为对象或数组）'}), 400
template.layout = json.dumps(layout, ensure_ascii=False)
~~~
  攻击载荷（两次写入都可用）：`{"c":"</script><script>new Image().src='/api/leak?c='+document.cookie</script>"}`。
- 影响：**写权限 = `require_role('warehouse')`（新增）或 `require_role('admin','warehouse')`（保存布局）；读 = 任何进入 /label_template/<id> 的 admin/warehouse**。即：warehouse 角色账号可持久化脚本，在 admin 打开模板设计页时以 admin 身份执行任意请求（建管理员、导出数据等）= **越权/会话劫持**。当前 AGENTS §〇 单人环境降低了跨用户命中率（需同一账号先写入再打开），但角色边界与多账号场景下是实打实的提权链。⚠️ 若评估口径按多用户生产环境，本条应升 **P0**。
- 根因：输出点用 `|safe` 渲染**未转义的 JSON 字符串**（应使用 `tojson`，它会转义 < > &）；同时写入侧未做 JSON 结构校验（新增路径把原始字符串直接落库，layout 甚至可能不是合法 JSON，进而让页面 JS 语法错误）。
- 建议（最小修复，2 处）：① `label_template_detail.html:520` 改 `let layoutData = {{ template.layout|tojson }};`（若 layout 可能是非法 JSON，后端先 `_normalize_label_template_layout` 再传 dict）；② `label_barcode.py:70` 改为 `json.loads` 校验失败即 400，并按 save_layout 同样 `json.dumps` 规范化落库。③ 回归测试：POST 含 `</script>` 的 layout，断言响应 HTML 中不出现裸 `</script>` 后接脚本。
- 确认程度：**已确认**（读代码可断定；未运行验证渲染结果）
- 关联规则：A7 精神（输出编码）、R6（同类输出点：`print_label.html:236` 用 `from_json` 已安全，无需改）

---

### [P2] 报表 AI 洞察结果未转义直接拼进 `innerHTML`

- 位置：`app/templates/report_dashboard.html:334-341`；数据源 `app/routes/report.py:167-210`
- 现象：把 LLM 返回的多行文本 `res.insights.split('\n')` 后**逐行原样**拼进 `html += ... + line.replace(...) + ...`，最后 `content.innerHTML = html`，全程无 `escapeHtml`。
- 证据：

~~~javascript
// app/templates/report_dashboard.html:334-341
var lines = res.insights.split('\n').filter(function(l) { return l.trim(); });
var html = '<div class="d-flex flex-column gap-3">';
lines.forEach(function(line, idx) {
    ...
    html += '...<div class="text-muted" ...>' + line.replace(/^\d+[.、]\s*/, '') + '</div></div>';
});
html += '</div>';
content.innerHTML = html;
~~~
~~~python
# app/routes/report.py:204-207  LLM 原文直接返回，无净化
insights = _ai_call_llm_chat(prompt)
if not insights:
    return api_error('AI生成失败，请稍后重试')
return jsonify({'status': 'success', 'insights': insights})
~~~
- 影响：仓库自己的规则（`ai/security.py:7` "外部模型返回全部视为不可信输入"）被绕过。若大模型端点被替换/被污染、或模型把某条业务数据中的 `<img onerror=...>` 原样复述（提示词含 chart_data JSON 与统计值），则以任何 `login_required` 用户身份在其浏览器执行脚本。攻击门槛高于 P1（需控制/诱导 LLM 输出），故定 P2。
- 根因：前端渲染层缺输出编码；`ai/security.py` 本应提供的 `sanitize_markdown` 未被接线（见 P2-4）。
- 建议：与 `ai_supplier_evaluation.html:166` 保持一致，改为 `escapeHtml(line.replace(...))`；或统一走 `renderMarkdown`（其先 escape），并加一条模板级回归断言：注入 `<img src=x onerror=1>` 的 insights 必须显示为文本。
- 确认程度：**已确认**
- 关联规则：R5（AI 输出不可信）、A3/A5 精神

---

### [P2] CSRF 豁免面过宽：11 条接受 Web 会话鉴权的写端点被 `csrf.exempt` 豁免（另有按前缀自动豁免机制）

- 位置（逐条，均为 `csrf.exempt` **且** 同时接受"会话 Cookie"凭证）：
  - `app/app.py:32124-32126` `POST /api/ai/document_ocr`（`web_or_api_role_required('warehouse','purchase')`）
  - `app/routes/ai_excel.py:104` `POST /api/ai/document_ocr_excel`（豁免在 `app/app.py:3433` 注册，装饰器 `_web_or_api_role_required`）
  - `app/routes/print_queue.py:549-552` `POST /print_queue/jobs`（函数体内 `current_user` 或 Bearer，见 :560-564）
  - `app/routes/mobile.py:380/752/849/989/1077/1202/1456/1506` 共 8 条 `POST/DELETE /mobile/api/*`（`_web_or_api_role_required` 接受会话）
- 现象：这 11 条本可用"会话 Cookie + 实体表单"发起跨站请求，唯一防线是 `SESSION_COOKIE_SAMESITE='Lax'`（`config.py:72`）——Lax 不随跨站 POST 发送 Cookie，**当前现代浏览器下实际被缓解**，但：① 依赖单一配置，一旦为兼容老客户端改 `SameSite=None` 立即失守；② `print_queue_create_job` 的副作用是**触发打印机出纸**（物理信息泄露）；③ 按 URL 前缀的批量豁免是"默认不设防"的机制。
- 证据：

~~~python
# app/app.py:3459-3467  按前缀批量豁免：未来任何 /mobile/api/* 写路由自动失去 CSRF
for _ep, _view_func in list(app.view_functions.items()):
    for _rule in app.url_map.iter_rules(_ep):
        if _rule.rule.startswith('/mobile/api/'):
            csrf.exempt(_view_func)
            break
~~~
~~~python
# app/routes/print_queue.py:549-564
@app.route('/print_queue/jobs', methods=['POST'])
@csrf.exempt
def print_queue_create_job():
    user = current_user if current_user.is_authenticated else get_bearer_user()
~~~
- 影响：CSRF 威胁模型下，攻击者页面可代受害者创建打印任务/触发 OCR 上传接口；`/mobile/api/*` 未来新增写端点不会再经过 CSRF 评审。当前 SameSite=Lax 使其为"防御纵深缺口"而非可直接利用。
- 根因：把"Bearer 客户端无 CSRF token"的豁免，加到了同时接受 Web 会话的双通道装饰器上；豁免按前缀而不是按凭证通道。
- 建议：① 对 `csrf.exempt` 的写端点，在装饰器里改为"仅当 `Authorization: Bearer` 存在时才放行，否则要求 CSRF token"（或拆成 /mobile/api/* 仅 Bearer、Web 走另设 /mobile/web/*）；② 取消按前缀批量豁免，改为在装饰器中请求期判定；③ 加测试：带会话 Cookie 无 CSRF token 的 POST 必须 400。
- 确认程度：**已确认**（豁免事实）/ 可利用性 **风险提示**（依赖 SameSite=Lax 是否被改）
- 关联规则：A2、A1 精神

---

### [P2] `/api/login` 缺少 IP 级失败限流（Web 登录有，API 登录无）

- 位置：`app/routes/native_api.py:899-948`；对照实现 `app/routes/user_auth.py:126-131`、`:233-257`
- 现象：Web `/login` 在 POST 入口先做跨账号的 IP 滑动窗口限流（`login_fail:{ip}`，超限 429），而 `POST /api/login` 只有 `user.increment_failed_count(request_ip)` 的**按账号**锁定（5 次/30 分钟），**同一 IP 对无限多个用户名扫号没有任何全局上限**，且该端点 `csrf.exempt`。
- 证据：

~~~python
# app/routes/native_api.py:920-948  —— 无 rate_limit 导入/无 is_rate_limited 判定
request_ip = get_request_ip()
user = User.query.filter_by(username=username).first()
if not user:
    add_login_log(status='failed', username=username, user=user, fail_reason='api_failed')
    ...
    return api_json_error('账号或密码错误', 401)
...
if not check_password_hash(user.password_hash, password):
    user.increment_failed_count(request_ip)   # 仅按账号累计
~~~
~~~python
# app/routes/user_auth.py:126-131（Web 侧对照）
request_ip = get_request_ip()
rate_key = f'login_fail:{request_ip}'
if is_rate_limited(rate_key, LOGIN_IP_RATE_LIMIT_PER_MINUTE, 60):
    ...
    return render_template('login.html', **login_ctx), 429
~~~
- 影响：内网/公网暴露 API 时可对账号名做高速枚举与密码喷洒；单账号仍受 5 次锁定保护（admin 被暴力破解风险有限），但**多账号/长期在线服务**下弱化了 F2.2 的限流设计。
- 根因：两套登录实现（Web 表单 / 原生 App）分叉，F2.2 的限流只落到 Web 分支。
- 建议：在 `native_api_login` POST 入口复用 `rate_limit.is_rate_limited/record_failure`（key 与 Web 相同 `login_fail:{ip}`，共享计数），并补回归测试。
- 确认程度：**已确认**
- 关联规则：R6（同根因查全量消费点）

---

### [P2] `app/ai/security.py` 一整套安全能力**零调用**（安全控制未接线，形成"纸面防护"）

- 位置：`app/ai/security.py`：`check_prompt_safety`(:267)、`detect_prompt_injection`(:305)、`safe_document_context`(:319)、`sanitize_markdown`(:465)、`TokenStore/get_token_store`(:367-453, :551-556)
- 现象：全仓库（`app/` 全部 .py/.html/.js，除该文件自身）grep 上述符号 = **0 处引用**；唯一被用的是 `mask_phone/mask_email/.../desensitize_text`（仅 `ai/ops/data_retention.py:11` 注释提及）。与此同时 OCR 的提示词是**裸 f-string 拼接用户输入**：
- 证据：

~~~python
# app/app.py:32224, 32259, 32261-32262（OCR 端点：用户备注直接拼进 prompt）
remarks = request.form.get('remarks', '').strip()
...
prompt = f'提示：{type_labels.get(doc_type_hint, "")}\n\n' + prompt
...
if remarks:
    prompt += f'\n\n用户备注：{remarks}'
~~~
~~~python
# app/ai/security.py:465  对比：该模块声称提供 Markdown 链接白名单/脚本移除，但无人调用
def sanitize_markdown(text, allowed_domains=None) -> str: ...
# app/ai/security.py:551-556  TokenStore 内存版（进程内），无调用方
_token_store = TokenStore()
def get_token_store() -> TokenStore: return _token_store
~~~
- 影响：项目文档/模块 docstring 承诺的"提示注入防护、Markdown 安全渲染、敏感信息过滤"实际不生效；后续开发者按文档以为已有防护 → 真实缺口（本报告 P2-1 的 XSS 即因此没有被提前拦住）。也意味着 `detect_prompt_injection/safe_document_context` 的 R5 边界在提示词层是"无防护、仅靠人工确认"。
- 根因：能力实现后未接入 handler/route（未完成 wiring），模块注释描述了目标态而非现状。
- 建议：二选一并落测试：① 把 `safe_document_context`/`sanitize_markdown` 接到 `ai/handlers.py` 与 `report_dashboard` 前端渲染（推荐）；② 在 `ai/security.py` 标注"未接线"并从文档删除承诺，登记台账，避免误信。
- 确认程度：**已确认**（grep 零引用）
- 关联规则：R5、R6、A9 精神

---

### [P2] A2/A7/A8 pre-commit 规则只覆盖 `app.route` 且整体排除 `app/ai/`，42+10 条路由不在门禁内

- 位置：`scripts/lint_wms_rules.py:574-582`（A2 正则 `app\.route`）、`:575`（`exclude_paths=("app/ai",)`）、`:910-931`（A7 排除 app/ai）、`:987-994`（A8 `_WRITE_ROUTE` 只匹配 `app\.route`）
- 现象：三种"绕过 lint 的合法写法"在仓库里**已真实存在**：
  1. **blueprint 装饰器 42 条**：`app/ai/routes.py` 的 `ai_bp.post` ×14、`app/ai/v2_routes.py` ×6、`app/routes/unit.py` 的 `unit_bp.route` ×5（其中 3 条 POST）等 → A2/A8 完全不扫；
  2. **`add_url_rule` 注册 10 条**：`app/routes/doc_print_excel.py:68-78` 在循环里 `app.add_url_rule(...)`，任何静态路由审计都不敏感；
  3. **`app/ai/` 整体被排除在 A2/A7/A8 之外**（A7 注释称"AI 模块不需要此规则"）。
- 证据：

~~~python
# scripts/lint_wms_rules.py:579-582
_ROUTE_POST = re.compile(
    r"@app\.route\(\s*['\"]([^'\"]+)['\"]\s*,\s*methods\s*=\s*\[[^\]]*['\"]POST['\"]",
    re.IGNORECASE,)
# scripts/lint_wms_rules.py:574-575
scan_paths = ("app",)
exclude_paths = ("app/ai",)
~~~
~~~python
# app/routes/doc_print_excel.py:70-78  —— 门禁看不见的路由注册方式
for target_code, (prefix, model_name) in _DOC_ROUTE_MODELS.items():
    view = login_required(_make_doc_print_excel_view(app, target_code, model_name))
    app.add_url_rule(f'/{prefix}/<int:id>/print_excel', endpoint=..., view_func=view, methods=['GET'])
~~~
- 影响：这不是"已存在的漏洞"，而是**门禁失效**——新增 AI 写路由/blueprint 写路由即使漏 `login_required`/pydantic/SQL 参数化，pre-commit 也全绿。结合 P2-4（AI 安全能力未接线），AI 域是规则覆盖面最薄的高风险区。
- 根因：A2/A8 用"`app.route` 字面量"识别路由，未用 AST/`url_map` 全量枚举；`app/ai` 被当作"不需要规则"的例外。
- 建议：① 三条规则统一改为"扫描 `<任意>.route|get|post|...` + `add_url_rule`"；② 去掉 `app/ai` 的 A2/A8 排除（A7 的人工补扫结论是 app/ai 当前无拼接 SQL，说明排除没有必要）；③ 加一条自检：`len(url_map)` 与扫描到的路由数差异 > 0 即失败（防再次漏扫）。
- 确认程度：**已确认**（规则源码 + 实际路由源码对照）
- 关联规则：A2、A7、A8、R6

---

### [P2] "记住我"365 天长效 Cookie 未显式配置 HttpOnly/Secure/SameSite（依赖 Flask-Login 默认值）

- 位置：`app/config.py:64-68`（`REMEMBER_COOKIE_DURATION = timedelta(days=365)`、`SESSION_COOKIE_*` 三项有配）；`app/requirements.txt:55`（`Flask-Login==0.6.3`）；全仓库 grep **无** `REMEMBER_COOKIE_SECURE / REMEMBER_COOKIE_HTTPONLY / REMEMBER_COOKIE_SAMESITE`。
- 现象：登录勾选"记住我"后下发 365 天持久 `remember_token`（`user_auth.py:210-214`）。会话 Cookie 有 `HttpOnly=True / SameSite=Lax`，但 remember 系列三项**全部依赖 Flask-Login 库默认**（0.6.3 上游默认：SECURE=None、HTTPONLY=False、SAMESITE=None）→ 该长效令牌可被 JS 读取、可跨站携带、HTTP 下明文回落。
- 证据：

~~~python
# app/config.py:64-72
PERMANENT_SESSION_LIFETIME = 28800
REMEMBER_COOKIE_DURATION = timedelta(days=int(os.environ.get('WMS_REMEMBER_LOGIN_DAYS', '365') or 0))
WTF_CSRF_TIME_LIMIT = 28800
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('true', '1', 'yes')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
~~~
- 影响：一旦命中 P1 的 XSS（或其他任一 XSS），攻击者可**直接盗走 365 天有效的 remember_token**（HttpOnly=False 时），无需等 8 小时会话过期即长期接管账号；HTTPS 部署下 remember 令牌仍可能随 HTTP 请求回落。
- 根因：加固只做了 `SESSION_COOKIE_*`，漏了 Flask-Login 的 `REMEMBER_COOKIE_*` 命名空间（两套配置名）。
- 建议：`config.py` 补 `REMEMBER_COOKIE_HTTPONLY=True`、`REMEMBER_COOKIE_SAMESITE='Lax'`、`REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE`，并加启动自检（与 `validate_production_security_config` 对齐：HTTPS 部署下 remember 必须 Secure）。
- 确认程度：**高度可疑**（库默认值需在目标环境用 `app.config` 或响应头确认；`[需运行验证]`）
- 关联规则：BUG-2026-09-19-003 同类（生产 Cookie 硬门禁）→ R6

---

### [P3] 表格内联编辑把用户输入直接写入 `innerHTML`（self-XSS）

- 位置：`app/static/js/excel-table.js:264-274`（另 `:223-224` 用保存的 innerHTML 快照回填）
- 现象：文本列（remark/remarks/note）保存成功后 `cell.innerHTML = displayValue`，`displayValue` 即用户输入原文 → 输入 `<img src=x onerror=alert(1)>` 会在本人浏览器执行。刷新后服务端渲染是转义的（Jinja autoescape），故为 self-XSS。
- 证据：

~~~javascript
// app/static/js/excel-table.js:271-274
const displayValue = isTextField ? newValue
    : (field === 'price' ? '¥' + newValue.toFixed(2) : newValue.toFixed(2));
cell.innerHTML = displayValue;
~~~
- 影响：本人会话内的脚本执行（可被社工/粘贴利用），不跨用户；但它是**同一 XSS 类问题的第 2 个消费点**（R6 要求同类点一起排查）。
- 建议：文本列改 `cell.textContent = newValue`；数字列保留受限格式化。
- 确认程度：**已确认**
- 关联规则：R6（同根因：未编码的输出写入）

---

### [P3] 登录失败响应可枚举账号名 + `GET /login` 泄露 admin 锁定状态

- 位置：`app/routes/user_auth.py:163-174`（不存在=401"用户名或密码错误"、被禁用=403"账号已被禁用"）、`:205-206`（锁定=423"账号已锁定"）；`:97-123`（GET 页探测 admin 锁定状态并渲染倒计时）；API 侧同类 `app/routes/native_api.py:930-931`
- 现象：三种失败返回**不同的状态码与文案**，可据此判定"账号存在/被禁用/被锁定"；并且匿名 GET /login 会把 **admin** 的锁定状态渲染进页面。
- 证据：

~~~python
# app/routes/user_auth.py:166-174
if not user.is_active:
    ...
    flash('账号已被禁用，请联系管理员', 'danger')
    return render_template('login.html', **login_ctx), 403
# app/routes/user_auth.py:99-110  GET /login 匿名即可探测 admin 锁定
locked_admin = User.query.filter_by(username='admin').first()
if locked_admin and locked_admin.locked_until and locked_admin.locked_until > _dt.now():
    ... login_ctx.update({'locked': True, ...'username': 'admin'})
~~~
- 影响：内部系统单人部署下影响很小；若对外暴露可辅助定向爆破（先确认 admin 是否存在/是否锁定）。定性为体验/信息泄露级别。
- 建议：失败统一返回 401 + "用户名或密码错误"；锁定/禁用信息仅在**已通过密码校验后**返回（或统一走"若启用邮箱可发重置邮件"）。
- 确认程度：**已确认**
- 关联规则：—

---

### [P3] 密码强度策略仅"最小长度 6 位"，无复杂度/黑名单

- 位置：`app/app.py:7855-7865`（`validate_password_strength` 只校验 `len >= PASSWORD_MIN_LENGTH`，默认 6）；`config.py` 无其他策略
- 现象：`123456` 等弱口令可通过；三个写入口（改密 `user_auth.py:56`、新增用户 `:573`、重置密码 `:808`）共用同一策略。
- 证据：

~~~python
# app/app.py:7855-7865
def validate_password_strength(password):
    ...
    min_length = int(os.environ.get('PASSWORD_MIN_LENGTH', SYSTEM_CONFIG.get('PASSWORD_MIN_LENGTH', 6)))
    if len(password) < min_length:
        return False, f'密码长度不能少于 {min_length} 位'
    return True, None
~~~
- 影响：弱口令风险；但**bootstrap 固定默认密码 '`admin`' 是 AGENTS.md §一（2026-10-03 拍板）明确要求的设计**（`app/app.py:6688-6692`，并强制 `must_change_password`，`:6702`），故按简报要求**不列为缺陷**；此处仅就"用户自设密码仍可 6 位纯数字"提示。
- 建议：`validate_password_strength` 增加"长度 ≥8 或 三类字符"可配置策略，并保持 bootstrap 逻辑不变。
- 确认程度：**已确认**
- 关联规则：AGENTS §一（不报项已避开）

---

### [P3] `/api/options/<entity>` 500 时把内部异常文本回显给客户端

- 位置：`app/routes/options_api.py:324-327`
- 现象：`except Exception as exc: ... return jsonify({'status':'error','message': str(exc),'data':[]}), 500` → 内部异常（含 SQL 片段/路径）回显。
- 证据：

~~~python
except Exception as exc:
    current_app.logger.exception('[options] 候选查询失败 entity=%s kw=%s', entity, kw)
    return jsonify({'status': 'error', 'message': str(exc), 'data': []}), 500
~~~
- 影响：信息泄露（内部结构/字段名），需已登录且触发异常，危害低。另：`kw` 原样写日志（%s 格式串，无换行注入风险，但可污染日志）。
- 建议：返回固定文案，详情仅日志。
- 确认程度：**已确认**
- 关联规则：BUG-2026-08-16-019 同类（不返回内部异常细节）→ R6

---

### [P3] 两个死模板保留 `{{ rendered_content|safe }}`（HTML 打印模板已停用，属潜在回归风险）

- 位置：`app/templates/print_in_with_html.html:66-67`、`app/templates/print_out_with_html.html:62-63`
- 现象：这两个模板**全仓库无任何 `render_template('print_*_with_html.html')` 调用**（grep 0）；HTML 打印模板已被"仅 Excel 模板"策略取代（`app/routes/in_order.py:3141-3155` 注释"历史 HTML 模板不再渲染"、`app/app.py:34972-34990` 强制 `template_type='excel'`），故 `rendered_content` 永远为空、`|safe` 分支不可达。
- 证据：

~~~django
{# app/templates/print_in_with_html.html:66-67 #}
{% if rendered_content %}
    {{ rendered_content|safe }}
~~~
- 影响：当前**不可利用**（死代码）；风险是未来有人恢复 HTML 模板渲染时把未净化内容接上 `|safe`（`_render_html_print_content` 已有沙箱+净化，但此模板绕过了它）。
- 建议：删除这两个模板，或改为 `{{ rendered_content|safe }}` 前先经 `sanitize_print_html`（与 `app.py:34967` 一致）。
- 确认程度：**已确认**（不可达）
- 关联规则：A1/A7 精神

---

### [P3] `print_fill.template_file_abspath` 缺反向包含性校验（防御纵深）

- 位置：`app/print_fill.py:170-182`；消费点 `app/routes/in_order.py:3229`、`app/routes/out_order.py:1627`、`app/routes/print_template_editor.py:324`、`app/routes/print_template_center.py:271`
- 现象：把 DB 列 `excel_template_path` 转绝对路径时只做 `os.path.join(static_folder, rel)`，**未校验结果仍在 static_folder 内**；若该列被写成 `/static/../../instance/secret_key`，则会越出静态目录。当前所有写入点都是服务端生成路径（`print_template_center.py:215/245`、`app.py:34999`、`app.py:5999/6019`），**未发现用户可控写入** → 不可利用。
- 证据：

~~~python
# app/print_fill.py:174-182
p = excel_template_path.replace('\\', '/')
if p.startswith('/static/'):
    rel = p[len('/static/'):]
elif p.startswith('uploads/'):
    rel = p
else:
    rel = os.path.join('uploads', 'print_templates', os.path.basename(p))
return os.path.join(static_folder, rel)   # 未做 realpath 包含性校验
~~~
- 影响：纵深防御缺失——一旦未来出现可写 `excel_template_path` 的非管理员接口，立即升级为任意文件读/写（`print_template_editor._write_grid` 会往解析出的路径写文件，`:335-353`）。
- 建议：函数末尾加 `realpath` + `commonpath` 校验（参照 `backup_catalog.resolve_backup_file:59-61` 的写法）。
- 确认程度：**已确认**（当前不可达）
- 关联规则：—

---

### [P3] 3 条写路由采用"函数体内手工鉴权"，A2 静态规则无法覆盖

- 位置：`app/routes/print_queue.py:549-564`（`/print_queue/jobs`，`csrf.exempt` 后在体内 `current_user / get_bearer_user` + 角色判断）、`app/routes/native_api.py:3047-3084`（`/api/mobile/crash_report` 匿名设计，仅大小/字段上限）、`app/app.py:25441-25445`（`/api/wechat_helper/task/<id>/report`，`csrf.exempt` 后在体内 `_wechat_helper_authorized()`）
- 现象：三处都**实际有鉴权/受控**（已逐行确认），但以 A2 规则的口径看，`csrf.exempt` 直接把路由"豁免"给静态检查，**体内漏写鉴权不会被 lint 发现**。`mobile_api_crash_report` 是明确设计（崩溃可能发生在登录前）+ 字段上限 20KB + 只追加 `logs/crash_reports.log`，未入业务库，风险可接受；但若 `stacktrace` 含换行会被原样写入日志（日志伪造，`[需运行验证]`）。
- 建议：把体内鉴权改为自定义装饰器（如 `wechat_helper_token_required`、`web_or_bearer_role_required`），让 A2 的允许列表显式包含它们；崩溃上报日志做单行化/转义。
- 确认程度：**已确认**（鉴权存在）/ 日志伪造 **风险提示**
- 关联规则：A2

---

## 4. 建议优先级路线图（≤10 条）

1. **（P1，立即）** 修标签模板 XSS：`label_template_detail.html:520` 改 `|tojson`；`label_barcode.py:70` 增加 `json.loads` 校验；补 1 条模板注入回归测试。——**唯一可直接拿到跨角色脚本执行的洞。**
2. **（P2，本周）** 报表 AI 洞察 `escapeHtml`（`report_dashboard.html:334-341`），并把 `ai/security.sanitize_markdown` 接线到所有 AI 前端渲染点（顺带解决 P2-4 的一半）。
3. **（P2，本周）** 收窄 CSRF 豁免：`/api/ai/document_ocr`、`/api/ai/document_ocr_excel`、`/print_queue/jobs`、`/mobile/api/*` 改为"Bearer 免 CSRF / 会话必 CSRF"，删除 `app.py:3463-3467` 的前缀批量豁免。
4. **（P2，本周）** `/api/login` 复用 Web 的 IP 级限流（同一 `login_fail:{ip}` 键），并用一条测试锁住"两套登录都限流"。
5. **（P2，两周）** 修 lint 覆盖缺口：A2/A7/A8 支持 blueprint 与 `add_url_rule`，移除 `app/ai` 排除；加"`url_map` 路由数 vs 扫描数"自检。**这是防止本报告后续问题复发的根因修复。**
6. **（P2，两周）** 补 `REMEMBER_COOKIE_HTTPONLY/SAMESITE/SECURE` 并纳入生产启动自检（与 `validate_production_security_config` 同处）。
7. **（P2，记账）** 给 `app/ai/security.py` 的 5 项能力标注"未接线"或真正接线；登记 BUG 台账（含生效确认字段，A13）。
8. **（P3，随迭代）** `excel-table.js:274` 文本列改 `textContent`；删除 2 个死模板；`template_file_abspath` 加包含性校验。
9. **（P3，随迭代）** 登录失败响应统一化（401 单一文案），锁定/禁用信息后置；`api_options` 500 改固定文案。
10. **（覆盖补强，下一轮）** Android 端（`app/android-native-wms/` 111 文件：token 存储/证书校验/WebView）与 AI 工具层（`ai/tools/`、`ai/handlers.py`、`ai/documents/`）为本次未覆盖的高风险区，建议单独立项审计。

---

## 5. 附：本次审计**明确不报**的项（防误报声明）

- **入/出库单无作废态**、**入/出库主链路无审核岗**：AGENTS.md §〇（2026-10-03 用户拍板）已接受，按简报要求不作为缺陷。
- **库位管理默认关闭时库位不必填**：同上（环境画像：库位管理未开启，`app/app.py:4227` 默认 `'0'`）。
- **bootstrap 固定默认密码 `'admin'`**：AGENTS.md §一明确要求"必须使用固定默认密码并告警"，且实现强制 `must_change_password`（`app.py:6688-6767`），不作为缺陷（仅在 P3 密码策略条目中提示用户自设口令仍可 6 位）。
- **`/healthz` 免认证、`/mobile/app` 免认证下载 APK、崩溃上报匿名**：均有设计注释与风险控制（不查库、仅静态文件、字段上限 + 日志文件），判定为可接受设计，未列缺陷。
- **测试用固定 SECRET_KEY（`TestingConfig: 'test-secret-key'`）**：仅 `FLASK_ENV=testing` 生效，不属生产泄露。
