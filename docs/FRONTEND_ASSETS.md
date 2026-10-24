# 前端资源与 CSP

更新日期：2026-10-24。

WMS 使用 Flask/Jinja 服务端渲染，浏览器依赖由本机静态目录提供。

- `custom.css` 定义公共主题变量和通用样式；`shell.css` 保留原公共布局样式，在原位置加载，再加载页面的 `extra_css`。两者的优先级和顺序不同，不能任意合并或调换。
- 自有 CSS/JS 使用 `STATIC_VERSION` 查询参数；启动时计算静态目录的版本，新增、更新和删除资源都参与。静态响应沿用年度缓存和 ETag，HTML 不缓存。更改资源后发布时需要重启，以更新版本和模板缓存。
- `js/pages/shell-navigation.js` 承载公共菜单、面包屑及原有日期/触控初始化，保持在 `shell.css` 后、页面样式和 CSRF 刷新脚本前同步加载。该段不含服务端插值，原代码逐字节迁移到静态资源；保留页面所需的菜单函数入口，不使用 async/defer 改变初始化时序。请求封装仍在原公共模板中；AI 助手加载方式见下条。
- `js/pages/ai-assistant.js` 承载 AI 浮窗，在原角色条件内、DOM 和 `api.js`/`app.js` 后同步加载并使用静态版本缓存。历史查询、反馈、普通聊天及清空历史复用 `WMS.api`；流式聊天使用已有 `postResponse` 保留未消费的响应体，SSE 读取失败进入错误提示与解锁路径。清空服务器历史失败时明确说明仅清空本地上下文。公共模板仍保留请求封装和定时 CSRF 刷新。
- `js/select-refresh.js` 在 `api.js`/`app.js` 后同步加载，集中处理入出库、调拨、盘点及领料的仓库下拉和出库部门下拉刷新。使用 `WMS.api.getRaw` 校验 HTTP 与列表封套，按下拉元素淘汰过期响应，并在应用结果时保留当前选择；只有有效选择实际丢失时触发 change，供库位联动处理。只读和禁用字段保留历史值。
- `js/material-cache.js` 由出库新增、公共单据表单及调整页按需加载，在页面脚本之前运行。三个完整本地物料缓存按 `/material/api/all` 的 `pages` 与显式 `per_page=2000` 取全后再替换，任一页失败保留旧缓存；检测到分页总数变化或重复记录时提示重新刷新。入库页仍只保留300条初始缓存并使用服务端搜索。
- Chart.js 由报表仪表盘和销售对账页加载，先加载库再运行页面图表脚本；普通公共布局不加载。仪表盘未选仓库时也不加载。
- ZXing 保持扫码页加载；Excel 导入导出组件按实际需要加载本地 SheetJS。浏览器扫描的摄像头权限仍由操作员按实际用途授予。

生产默认 CSP 的 `script-src` 为 `'self' 'unsafe-inline'`，不再包含 `unsafe-eval`。浏览器不允许 `eval`、`Function` 构造及字符串定时器编译字符串脚本；本地依赖与模板扫描、真实响应头和浏览器组件验收覆盖此约束。

`unsafe-inline` 仍为现有内联脚本和事件处理器保留，不能据此宣称已经消除 XSS 风险。文字进入 HTML 文本/属性时使用公共 `escapeHtml()` 或 DOM `textContent`；动态事件通过程序监听传递数据，HTML 转义不能代替 JavaScript 字符串上下文的防护。业务请求仍遵守 `WMS.api` 规范，代理规则以 AGENTS 和 DEVELOPMENT_RULES 为准。

相关验证：`tests/test_chart_page_loading.py`、`tests/test_shell_styles.py`、`tests/test_shell_source_hygiene.py`、`tests/test_ai_text_event_boundaries.py`、`tests/test_csp_without_eval.py`。详细修复及生效证据见 BUG-2026-10-23-011～015 月度台账。
