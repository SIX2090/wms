# WMS 全系统 AI 审计报告

## 0. 审计元信息

- **审计日期**：2026-08-05
- **审计基准 commit（本地）**：`0deb5c22 feat: WMS代码提交高影响缺陷检查`
- **审计基准 commit（origin/main）**：`0deb5c22`（与本地一致，无需 pull --rebase）
- **分支**：main（未建任何分支，符合红线）
- **工作区状态**：审计开始时干净；审计结束仅清理 benchmark 产物 `performance_report_*.json`（由审计脚本生成，已删除）
- **审计范围（M1-M10）**：全部勾选执行

### 验证命令汇总

| 命令 | 通过 | 失败 | 失败用例 |
|---|---|---|---|
| `make check`（lint + 86 回归 + pytest） | lint 0 违规；86 回归 PASS；pytest **116 passed** | 0 | — |
| `make smoke`（121 冒烟，需先启动服务） | **121/121** | 0 | — |
| `scripts/verify_ai_all.py --level full` | **70/70** | 0 | — |
| `scripts/verify_wms_bugs.py`（86 项静态回归） | PASS | 0 | — |
| `scripts/scan_wms_risks.py` | OK（4 个 `\|safe` 候选已人工复核） | 0 | — |
| `scripts/verify_stability_gate.py` | **FAIL** | 1（`bug 2026-08-02-001 regression`） | 详见 P1-001 |
| `scripts/lint_wms_rules.py`（A1-A10） | 0 违规 | 0 | — |
| `scripts/lint_no_raw_post_fetch.py` | 通过 | 0 | — |
| `scripts/verify_opening_stock_multi_warehouse.py` | 37 PASS | **8 FAIL（静态误报）** | 详见 P1-001 |
| `tests/verify_bug_2026_08_04_001/002_location_inventory_*.py` | PASS | 0 | — |
| `scripts/benchmark_performance.py` | 全部指标达标 | 0 | — |

> 注：`make check` 在系统 `python3` 下会因缺依赖失败（详见 P2-002）；上表用装有项目依赖的 pyenv python3.11 执行。

---

## 1. 审计结论

- **总缺陷数**：P0=0，P1=1，P2=3，P3=3（共 7）
- **一句话结论**：系统当前健康度评级为 **基本健康**——核心业务逻辑（状态机、库存同步、引用完整性、安全、权限、路由拆分、漏导入）经审计均正确，未发现数据丢失/越权/SQL 注入/密码可改等 P0 级缺陷；主要问题集中在**测试基建**：若干审计脚本因路由迁移后仍静态读取 `app/app.py`，产生误报并导致稳定性门禁 `verify_stability_gate.py` 失败，需优先修复以保证门禁可信。

---

## 2. P0 缺陷（必须修复）

无。未发现数据丢失、越权、安全漏洞或核心流程不可用的 P0 级缺陷。

---

## 3. P1 缺陷

### 3.1 [P1-001] 路由迁移后审计脚本仍静态读取 `app/app.py`，导致稳定性门禁误报失败

- **位置**：
  - [verify_bug_2026_08_02_001.py](file:///workspace/scripts/verify_bug_2026_08_02_001.py#L42)（`app_py = read_text("app/app.py")`，第 75-95 行 C 段 5 项静态检查）
  - [verify_opening_stock_multi_warehouse.py](file:///workspace/scripts/verify_opening_stock_multi_warehouse.py#L31)（`APP_PY = (ROOT/"app/app.py")`，第 130-169 行 8 项静态检查）
  - 被迁移的真实代码：[in_order.py](file:///workspace/app/routes/in_order.py#L550)、[opening_stock.py](file:///workspace/app/routes/opening_stock.py#L101)
- **证据**：
  - `verify_bug_2026_08_02_001.py` 在 `app/app.py` 中找 `add_in_order/update_in_order/complete_in_order/update_completed_in_order/batch_complete_in_order`，但上述函数已迁至 `app/routes/in_order.py`，故 5 项 C 检查全 False。
  - `verify_opening_stock_multi_warehouse.py` 在 `app/app.py` 中找 `add_opening_stock/batch_save_opening_stock/edit_opening_stock/opening_stock_list`，但已迁至 `app/routes/opening_stock.py`，8 项静态检查全 False。
  - 同一脚本的**动态**检查全部通过（opening_stock：37 PASS；in_order：D1-D5 全 PASS），且 [in_order.py](file:///workspace/app/routes/in_order.py#L469-L473) 与 [opening_stock.py](file:///workspace/app/routes/opening_stock.py#L249) 中"默认仓库/请选择仓库"逻辑确实存在，证明**产品功能正确，属脚本误报**。
- **复现步骤**：`python3 scripts/verify_stability_gate.py` → 输出 `FAIL: bug 2026-08-02-001 regression`，门禁整体返回 1。
- **根因**：A10 规则要求路由迁入 `app/routes/`，但脚本的正则/文本断言仍锚定 `app/app.py`，未同步指向拆分后的模块。
- **影响**：`verify_stability_gate.py` 是 AGENTS.md 规定的强制发布门禁，当前**必然误报失败**，会错误阻塞发布或让团队对该门禁失去信任（"假红灯"）。
- **修复建议**：将两个脚本的静态读取目标由 `app/app.py` 改为正确的模块：
  ```python
  # verify_bug_2026_08_02_001.py：改为扫描 app/routes/in_order.py
  APP_DIR = ROOT / "app" / "routes"
  in_order_src = (APP_DIR / "in_order.py").read_text(encoding="utf-8")
  # 用 in_order_src 替换原有的 app_py 做 C 段断言
  ```
  `verify_opening_stock_multi_warehouse.py` 同理改为读取 `app/routes/opening_stock.py`。
- **回归测试**：修复后执行 `python3 scripts/verify_stability_gate.py` 应全绿；`verify_opening_stock_multi_warehouse.py` 静态 8 项应转 PASS。
- **状态**：待确认

---

## 4. P2 / P3 缺陷

| ID | 级别 | 位置 | 问题 | 建议 |
|---|---|---|---|---|
| P2-002 | P2 | [Makefile](file:///workspace/Makefile#L11)（`PYTHON ?= python3`） | `make check/make smoke` 依赖系统 `python3`，该解释器未装项目依赖时 `verify_wms_bugs.py` 报 `ModuleNotFoundError: werkzeug` 直接失败（本环境复现）。用装有依赖的 python 则全绿。 | ① 文档/message 明确"先 `make install`"；② 或在 `check` 前自动探测/提示调用带依赖的解释器；③ 将 `requirements` 固化到 CI 使用的解释器。 |
| P2-003 | P2 | [stock_query.py](file:///workspace/app/routes/stock_query.py#L74-L102) | 库存查询的 `warehouse_id` 仅作为"是否返回数据"门禁，`Material.query` 未按仓库真正过滤（`Material.stock` 为全局总库存，非按仓）。选择仓库 A 或 B 返回完全相同的物料与总库存，UI 上"按仓库筛选"产生误导。 | ① 在页面/列头明确"此库存为全仓总库存"；② 或按 `LocationInventory` 聚合展示所选仓库库存；③ 至少在 dropdown 上注明仓库筛选为入口门禁。 |
| P2-004 | P2 | [print_in_with_html.html](file:///workspace/app/templates/print_in_with_html.html#L67)、[print_out_with_html.html](file:///workspace/app/templates/print_out_with_html.html#L63) | 自定义打印模板内容经 `{{ rendered_content|safe }}` 原样输出。若模板编辑权限向低权限角色开放，存在存储型 XSS 面（模板内可注入 `<script>`）。 | 确认模板编辑仅限可信管理员；若需开放，对模板 HTML 做白名单净化（如 bleach）后再 `|safe`。 |
| P3-001 | P3 | `app/routes/*.py`（pyflakes 39 处） | 大量 `imported but unused` 延迟导入，如 [transfer.py](file:///workspace/app/routes/transfer.py#L20-L22) 模块级 8 个未用 flask 导入、`in_order.py:1144`、`native_api.py` 多处等。 | 清理无效延迟导入；`transfer.py` 模块级 flask 导入为重构残留，应删除。 |
| P3-002 | P3 | [verify_transfer_state_machine.py](file:///workspace/scripts/verify_transfer_state_machine.py#L33-L47) | 调拨状态机脚本未开启库位管理却断言库位库存变化，需手工预置 `location_management_enabled` 才通过（产品功能正确，属测试脚本对环境依赖不健壮）。 | 脚本内显式开启库位管理再断言，避免依赖外部环境。 |
| P3-003 | P3 | 审计提示 [WMS_FULL_AI_AUDIT_PROMPT.md](file:///workspace/WMS_FULL_AI_AUDIT_PROMPT.md) | 提示中 `scripts/verify_bug_2026_08_04_001_location_inventory_savepoint.py` / `..._002_...` 路径不存在，实际位于 `tests/` 下。 | 修正提示中的脚本路径。 |

> 说明：`scan_wms_risks.py` 报告的 4 个 `|safe` 中，`alert.html:237` 实为 JS 变量 `safetyStock` 的文本误匹配（非 `|safe` 过滤器）；`sales_reconciliation_report.html:147` 为 `{{ chart_data|tojson|safe }}` 标准安全写法；均非真实 XSS。仅打印模板（P2-004）需关注。

---

## 5. 正项清单（做得好的，供团队延续）

- **引用完整性**：`delete_material` 已覆盖全部 19 张关联表，被引用时返回清晰业务提示而非 DB 外键错误，`repro_material_delete_ref.py` 验证通过。
- **状态机**：入库/出库/调拨/盘点/调整/下推状态机测试通过，`complete_*` 使用 `_acquire_order_write_lock` 防并发重复完成，已完成单据禁止直接删除、必须反提交回草稿。
- **库存正确性**：期初库存多仓库独立建账、`LocationInventory` 保存点/不静默失败测试通过；完成/反提交/删除对称回退。
- **漏导入**：`pyflakes` 未发现任何 `undefined name`，路由拆分后延迟导入完整，无运行时 NameError。
- **安全**：AI 安全治理（脱敏/提示注入/确认令牌/Markdown 渲染/日志过滤）全 PASS；跨用户隔离、高风险边界、权限矩阵全 PASS；admin 引导密码遵循固定 `'admin'` + 告警、禁止随机生成。
- **规则合规**：A1-A10 lint 0 违规；业务 JS 无裸调非 GET fetch；SQL 全参数化。
- **测试覆盖**：`make check` 116 pytest + 86 BUG 回归 + 121 冒烟 + AI 70 项全绿；38 个 `verify_app_py_split_*` 覆盖路由拆分模块。
- **性能**：benchmark 全部指标达标（工具注册表 P95 0.0007ms、策略引擎 0.0254ms、文档模式 0.0036ms、熔断器 0.0007ms）。

---

## 6. 修复执行顺序建议

1. **P1-001**（优先）：修正两个审计脚本的静态读取路径 → 恢复 `verify_stability_gate.py` 门禁可信。这是唯一会让强制门禁误报的项。
2. **P2-002**：明确 `make check` 的 python 依赖说明，避免 CI/新环境误失败。
3. **P2-003 / P2-004**：库存查询数据范围标注 + 打印模板 `|safe` 权限/净化确认。
4. **P3 清理**：删除无效延迟导入（尤其 `transfer.py` 模块级残留）、修正审计提示路径、增强 `verify_transfer_state_machine.py` 环境自洽。

依赖关系：P1-001 独立无依赖；P2-002 与 P1-001 同属验证基建，可一并处理；P3 均不阻塞。

---

## 7. 交付说明

- 本报告为**只读审计产出**，未修改任何业务代码/模型/模板/数据库/测试/文档（仅按提示要求新建本报告文件）。
- 未进行任何授权修复；如需进入修复流程，请逐项授权 P1/P2 所列改动，并遵循 AGENTS.md 的 atomic-action push 规则与 BUG 台账登记。
- 审计使用解释器：`/root/.pyenv/versions/3.11.15/bin/python3.11`（已装项目依赖）。