# 前端资源与 CSP

更新日期：2026-10-23。

WMS 使用 Flask/Jinja 服务端渲染，浏览器依赖由本机静态目录提供。

- `custom.css` 定义公共主题变量和通用样式；`shell.css` 保留原公共布局样式，在原位置加载，再加载页面的 `extra_css`。两者的优先级和顺序不同，不能任意合并或调换。
- 自有 CSS/JS 使用 `STATIC_VERSION` 查询参数；启动时计算静态目录的版本，新增、更新和删除资源都参与。静态响应沿用年度缓存和 ETag，HTML 不缓存。更改资源后发布时需要重启，以更新版本和模板缓存。
- Chart.js 由报表仪表盘和销售对账页加载，先加载库再运行页面图表脚本；普通公共布局不加载。仪表盘未选仓库时也不加载。
- ZXing 保持扫码页加载；Excel 导入导出组件按实际需要加载本地 SheetJS。浏览器扫描的摄像头权限仍由操作员按实际用途授予。

生产默认 CSP 的 `script-src` 为 `'self' 'unsafe-inline'`，不再包含 `unsafe-eval`。浏览器不允许 `eval`、`Function` 构造及字符串定时器编译字符串脚本；本地依赖与模板扫描、真实响应头和浏览器组件验收覆盖此约束。

`unsafe-inline` 仍为现有内联脚本和事件处理器保留，不能据此宣称已经消除 XSS 风险。文字进入 HTML 文本/属性时使用公共 `escapeHtml()` 或 DOM `textContent`；动态事件通过程序监听传递数据，HTML 转义不能代替 JavaScript 字符串上下文的防护。业务请求仍遵守 `WMS.api` 规范，代理规则以 AGENTS 和 DEVELOPMENT_RULES 为准。

相关验证：`tests/test_chart_page_loading.py`、`tests/test_shell_styles.py`、`tests/test_shell_source_hygiene.py`、`tests/test_ai_text_event_boundaries.py`、`tests/test_csp_without_eval.py`。详细修复及生效证据见 BUG-2026-10-23-011～015 月度台账。
