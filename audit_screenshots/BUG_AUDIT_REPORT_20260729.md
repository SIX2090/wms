# WMS 浏览器+接口探索性测试 BUG 报告

- 测试时间：2026-07-28 23:00 ~ 2026-07-29 00:30
- 测试地址：http://127.0.0.1:8080（admin 账号）
- 测试方式：Playwright 真实浏览器（Chrome 151）+ HTTP 接口层全路由爬取/参数模糊/全链路业务验证
- 证据目录：`audit_screenshots/qa_*.png`（20 张截图）、`_browser_result.log`、`_crawl2_result.json`

## 一、确认的 BUG（2 个，均为 P1）

### BUG-001【P1】AI 智能补货建议页（新版）HTTP 500
- 模块：AI 功能 / 智能补货
- 路径：`GET /ai/replenishment_live`
- 复现：登录 admin → 访问 `/ai/replenishment_live` → 页面仅显示 "Error"，HTTP 500
- 根因（进程内复现堆栈）：路由 `ai_replenishment_live_page()`（app.py:20291）只调用
  `render_template('ai_replenishment.html')`，未传入模板必需的 `report` 变量 →
  `jinja2.exceptions.UndefinedError: 'report' is undefined`（ai_replenishment.html:23 `report.summary.days`）
- 预期：正常渲染补货建议页；实际：500
- 证据：`qa_ai_replenishment_live.png`

### BUG-002【P1】AI 库存健康度评分页 HTTP 500
- 模块：AI 功能 / 库存健康度
- 路径：`GET /ai/inventory_health_live`
- 复现：登录 admin → 访问 `/ai/inventory_health_live` → HTTP 500，页面仅显示 "Error"
- 根因：与 BUG-001 同类——路由 `ai_inventory_health_live_page()`（app.py:20298）
  未向 `ai_inventory_health.html` 传入 `report` 变量 → `jinja2 UndefinedError: 'report' is undefined`
- 证据：`qa_ai_inventory_health_live.png`

## 二、疑似/观察项（非确认 BUG，建议人工复核）

- OBS-1【P2】`/out_order`（领料单列表）默认只显示"领料单"业务类型，新建的"其他出库"草稿
  需切换到 `/other_out_order` 才能看到，页面无明显的类型切换提示（模板确认为分列表设计）。
- OBS-2【P2】测试期间发现系统为空库（无任何物料/供应商/单位），若演示环境期望有示例数据，
  需另行导入；本次 QA 测试数据（QAU01 单位、QASUP01 供应商、QAMAT01 物料）已保留在库中。

## 三、验证通过项（未发现 BUG）

| 类别 | 覆盖 | 结果 |
|---|---|---|
| 全量 GET 路由爬取 | 215 个静态 GET 路由 | 仅 BUG-001/002 两个 500，其余全部 200 |
| 参数路由（详情/打印） | 141 个（含 id=1 与 id=99999999 无效 ID） | 全部正常，无 500 |
| 列表页参数模糊 | 24 列表页 × 8 参数（page 越界/负/字符、XSS、SQL 注入、超长 500 字符），共 192 用例 | 0 异常，无未转义反射 |
| 登录/登出 | 登录、登出后访问内页踢回登录页、未登录访问 302 | 正常 |
| CSRF | 无 token POST → 400 拦截；登录后 token 轮换 | 正常 |
| 表单校验 | 单位/分类/仓库空表单 POST → 有校验提示；XSS 名称被拦截 | 正常 |
| 库存核心规则 | 手工新增采购入库（不关联订单）→ 完成 → 库存+10 ✓；已完成单直接删除 → 409"请先反提交" ✓；详情页/列表页无可见删除按钮（截图 qa_19/20）✓；反提交 → 库存准确回退为 0 ✓；草稿删除 ✓ | 全部符合 AGENTS.md 规则 |
| 超额出库 | 库存 0 出库 999999：草稿可保存，完成时拦截"库存不足或并发冲突，当前库存：0.00" ✓ | 正常（草稿不校验为设计行为） |
| 浏览器 JS 控制台 | 15 个核心页面真实浏览器加载 | 0 JS 错误（除两个 500 页） |
| 权限/匿名访问 | 7 个敏感页未登录访问 | 全部 302 跳转登录 |

## 四、汇总

- 总 BUG 数：**2**（P1 × 2，均集中在 AI "live" 新版页面的模板上下文缺失）
- P0：0；P1：2；P2（观察项）：2
- 模块分布：AI 功能 2；其余模块 0

## 五、修复建议

为 `/ai/replenishment_live` 与 `/ai/inventory_health_live` 两个路由补充模板上下文
（参照旧版 `/ai/replenishment`、`/ai/inventory_health` 路由的 `report` 组装逻辑），
或将模板中的 `report.summary.*` 引用改为可选默认值（`report.summary.days|default(30)`）。
修复后需回归：两页 200 渲染 + 截图确认。
