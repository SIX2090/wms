# WMS 全系统审计遗留项修复 AI 提示词

> **使用说明**：把本文件全文作为 prompt 发给 AI 编码助手（如 TRAE/Cursor/Copilot/CodeBuddy），AI 会按顺序执行 P1 → P2 修复。每个修复项都是独立 atomic action，修一个 commit 一个 push 一个，不批量打包。
>
> **修复前必读**：
> 1. 先 `bash .githooks/install-hooks.sh` 启用 pre-commit 钩子（A1-A9 规则门禁）
> 2. 先 `cat AGENTS.md` 阅读仓库与库位必填规则全文
> 3. 先 `cat DEVELOPMENT_RULES.md` 阅读 9 条防 BUG 规则
> 4. 所有提交直接到 `main` 分支，**禁止建分支**
> 5. 业务 JS 禁止裸 `fetch`，必须用 `WMS.api.post/put/delete`
> 6. 新增 POST/PUT/DELETE 路由必须用 pydantic BaseModel 输入校验（A8）
> 7. 新增业务函数必须在 `tests/` 至少 1 个 pytest 测试（A9）
> 8. 测试文件改动后必须跑对应回归确认通过，不能破坏既有 golden 测试

---

## 背景

依据 `wms_full_audit_20260802.md` 全系统审计结果，WMS 代码层面 0 缺陷、回归稳定。仅剩 **1 项低优先级产品缺陷**（P1）+ **2 项测试平台/收集兼容问题**（P2）+ **1 项平台限制**（手动操作）。本提示词逐项给出修复方案、关键代码位置、回归测试要求。

**审计基准**：commit `52349521`（P2-1 报表仓库必填守卫已推送 main）。

---

## P1 修复（产品代码，低优先级）

### P1-1：`batch_delete_in_order` 更新采购订单状态失败时返回信息未提示

**位置**：`app/app.py` 函数 `batch_delete_in_order`（约第 27993-28066 行，重点 28053-28066 行）

**根因**：批量删除入库单时，删除循环（每张单据独立 commit）成功后，再统一更新受影响的采购订单状态（`update_purchase_order_status`）。若该更新失败（`except Exception` 分支 rollback），函数仍返回 `{'status': 'success', 'msg': '批量删除完成，共删除 X 张入库单'}`，**未向用户提示 PO 状态统计更新失败**。虽然单据删除主流程已成功（单据已被物理删除），但 PO 的 received_quantity / status 可能与实际不一致，且用户无感知。

**当前代码（约 28052-28066 行）**：
```python
    # 更新受影响的采购订单状态（已提交的单据不受后续 rollback 影响）
    try:
        for po_id in affected_purchase_order_ids:
            po = db.session.get(PurchaseOrder, po_id)
            if po:
                update_purchase_order_status(po)
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception('批量删除入库单后更新采购订单状态失败')

    msg = f'批量删除完成，共删除 {deleted_count} 张入库单'
    if skipped:
        msg += f'，跳过 {len(skipped)} 张：{", ".join(skipped[:10])}'
    return jsonify({'status': 'success', 'msg': msg, 'deleted': deleted_count, 'skipped': skipped})
```

**修复方案**：

把 PO 状态更新失败标记为一个 `po_update_failed` 标志，失败时在返回信息中明确提示（仍保持单据删除已成功的事实，只是提示 PO 统计可能需人工复核）：

```python
    # 更新受影响的采购订单状态（已提交的单据不受后续 rollback 影响）
    po_update_failed = False
    try:
        for po_id in affected_purchase_order_ids:
            po = db.session.get(PurchaseOrder, po_id)
            if po:
                update_purchase_order_status(po)
        db.session.commit()
    except Exception:
        db.session.rollback()
        po_update_failed = True
        app.logger.exception('批量删除入库单后更新采购订单状态失败')

    msg = f'批量删除完成，共删除 {deleted_count} 张入库单'
    if skipped:
        msg += f'，跳过 {len(skipped)} 张：{", ".join(skipped[:10])}'
    if po_update_failed:
        msg += '；但部分采购订单状态更新失败，请人工核对采购订单执行进度'
    return jsonify({
        'status': 'success',
        'msg': msg,
        'deleted': deleted_count,
        'skipped': skipped,
        'po_update_failed': po_update_failed,
    })
```

> 说明：`po_update_failed` 字段是新增的非破坏字段，前端无需改动（可后续在前端弹窗中读取该字段做醒目提示，本次只改后端返回）。

**回归测试**：扩展 `tests/verify_bug_P15_P16_P21.py` 或新建 `scripts/verify_bug_2026_08_02_P11.py`，新增用例：
- 构造 1 张来源采购订单的草稿入库单，batch_delete 删除成功
- mock/monkeypatch `update_purchase_order_status` 抛异常，验证返回 `po_update_failed=True` 且 msg 含"采购订单状态更新失败"提示
- 正常路径验证 `po_update_failed=False`

**验收命令**：
```bash
python3 -m pytest tests/verify_bug_P15_P16_P21.py -q   # 不能回归
python3 scripts/verify_wms_bugs.py                     # BUG-NEW-001 / BUG-NEW-011 等不能回归
```

**commit message**：
```
fix(in_order): batch_delete_in_order PO状态更新失败时在返回信息中提示

批量删除后统一更新采购订单状态失败时，原实现静默 rollback 仍返回
success，用户无感知 PO 执行进度可能与实际不一致。新增 po_update_failed
标志并在 msg 中提示人工核对采购订单执行进度。
```

---

## P2 修复（测试平台/收集兼容，不影响生产）

### P2-1：golden 测试 `test_lint_wms_rules_a8_a9_golden.py` 中 `python3` 在 Windows 不可用

**位置**：`tests/test_lint_wms_rules_a8_a9_golden.py` 第 74 行、第 295 行

**根因**：测试通过 `subprocess.run(["python3", ...])` 调用 `scripts/lint_wms_rules.py`。Windows 系统无 `python3` 命令（只有 `python`），导致 `returncode=9009`（命令未找到），9 个 A8/A9 golden 测试在 Windows 全部失败。Linux CI（有 `python3`）不受影响。

**修复方案**：

1. 文件顶部（第 18 行 `import subprocess` 后）补充 `import sys`：
```python
import subprocess
import sys
import tempfile
```

2. 两处 `"python3"` 改为 `sys.executable`：

第 71-80 行 `_run_lint_staged`：
```python
def _run_lint_staged(repo: Path, rule: str) -> tuple:
    """跑 lint_wms_rules.py --staged --rule <rule>，返回 (returncode, stdout)。"""
    proc = subprocess.run(
        [sys.executable, "scripts/lint_wms_rules.py", "--staged", "--rule", rule],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout
```

第 294-300 行 `test_list命令输出包含A8A9`：
```python
    def test_list命令输出包含A8A9(self):
        """``--list`` 输出必须包含 A8/A9。"""
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_LINT), "--list"],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert "[A8]" in proc.stdout
```

**回归测试**：该文件本身就是 golden 测试，修改后直接运行验证：
- `test_lint_wms_rules_a8_a9_golden.py` 全部通过（9 个 A8/A9 用例 + TestRuleRegistry）

**验收命令**：
```bash
python3 -m pytest tests/test_lint_wms_rules_a8_a9_golden.py -q  # 必须全绿（之前 9 failed → 现在全过）
python3 -m pytest tests/ -q                                      # 不能引入新回归
```

**commit message**：
```
test(lint): golden 测试 python3 改为 sys.executable 兼容 Windows

tests/test_lint_wms_rules_a8_a9_golden.py 中两处 subprocess.run(["python3",...])
在 Windows 无 python3 命令导致 9 个 A8/A9 用例 rc=9009 失败。改为
sys.executable，使 golden 测试在 Windows/Linux 均可复现。
```

---

### P2-2：warehouse 测试与 golden 测试批量收集时 `app` 模块解析冲突 —— **评估后不在本次修复范围（已知环境差异）**

> **状态：已评估，决定不修复（Won't Fix）**。warehouse 测试与 golden 测试各自单独运行均通过；仅在本机 Windows + pytest 9 批量收集时冲突，CI（Linux + pytest 8）`pytest tests/ -q` 通过。属测试环境差异，非产品代码缺陷，强行修复会破坏 CI。

**位置**：`tests/test_get_default_warehouse.py` 第 8-14 行、`tests/test_resolve_active_sales_warehouse.py` 第 8-14 行

**根因**：两类测试对 `app` 模块的解析方式本质互斥，且 `app/app.py` 只能被执行一次：
- **golden 测试**（如 `test_document_confirmation_golden.py`）：`from app.ai.documents import ...`，需要 `app` 是 **namespace package**（访问 `app.ai` 子包，不执行 app.py）。
- **warehouse 测试**：`sys.path.insert(0, APP_DIR); from app import Warehouse`，需要 `app` 是 **模块**（执行 `app/app.py` 注册 ORM）。

`app/app.py` 使用裸导入（`from config import config_dict`），强制 `APP_DIR` 在 `sys.path`；而 `APP_DIR/app.py` 一旦在 `sys.path`，`import app` 就被解析为模块而非 package。单进程 pytest 会话中，谁先 import `app` 就决定其形态，后者必然冲突。

**已验证的候选方案均不可行**：
1. `sys.modules.pop('app', None)` 强制重新解析 → 重新执行 `app/app.py`，SQLAlchemy 表（`user` 等）重复定义 `InvalidRequestError: Table 'user' is already defined`。
2. 条件导入 `try: from app import ... except: from app.app import ...` → 收集顺序决定成败：warehouse 测试先收集时 `app` 变模块，后续 golden 测试 `from app.ai...` 失败（`app is not a package`）。
3. `tests/conftest.py` 统一加载 app 为 package → 因 `APP_DIR/app.py` 在 `sys.path` 优先级高于 namespace package，`import app` 仍解析为模块，golden 测试失败。

**结论**：该冲突是 `app/app.py` 裸导入设计 + pytest 收集机制导致的深层架构问题，单进程会话无法在不破坏任一类测试的前提下完美解决。

**规避方式（推荐）**：
- 分组运行：`python3 -m pytest tests/test_get_default_warehouse.py tests/test_resolve_active_sales_warehouse.py -q`（warehouse 组）与 `python3 -m pytest tests/test_*_golden.py -q`（golden 组）分开执行，各自全绿。
- CI 在 Linux + pytest 8 下 `pytest tests/ -q` 本就不冲突，无需改动。

**如未来要根治**（非本次范围）：需重构 `app/app.py` 去掉裸导入（改为 `from app.config import ...` 包内相对导入）或为 `app/` 补 `__init__.py` 并统一所有测试从包路径导入，属较大重构，应单独立项评估。

---

## 手动操作项（AI 无法自动修复，需仓库 owner 执行）

### M-1：GitHub `main` 分支保护未真正启用（BUG-2026-07-31-002）

**现状**：`main` 分支可直接 push 绕过 PR + review。GitHub App token 无 `Administration: write` 权限，无法通过 API 设置分支保护（已实测 GET/PUT/PATCH 全部 403）。

**当前兜底**：`.githooks/pre-commit`（A1-A9 门禁）+ `.githooks/pre-push`（拒绝向非 main 分支推送）+ CI `lint-and-test` 三道防线，服务端保护未启用。

**owner 手动操作步骤**（任选其一）：

**方式 A（推荐，Web UI）**：
1. 登录 GitHub → 打开 `SIX2090/wms` 仓库 → `Settings` → `Branches`
2. `Add branch ruleset`（或 `Add rule`）→ 目标分支 `main`
3. 勾选：
   - `Require a pull request before merging` → `Require approvals: 1`
   - `Require status checks to pass before merging` → `Require branches to be up to date` → 添加 status check `lint-and-test`
   - `Require linear history`
   - `Do not allow bypassing the above settings`（如需）
   - 关闭 `Allow force pushes`、`Allow deletions`
4. 保存

**方式 B（fine-grained PAT）**：
1. 生成 fine-grained PAT，Repository access 选 `SIX2090/wms`，Permissions 勾选 `Administration: write`（含 Branch protection rules）
2. 执行：
```bash
curl -X PUT \
  -H "Authorization: Bearer <PAT>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/SIX2090/wms/branches/main/protection \
  -d '{"required_status_checks":{"strict":true,"contexts":["lint-and-test"]},"required_pull_request_reviews":{"required_approving_review_count":1},"enforce_admins":false,"required_linear_history":true,"allow_force_pushes":false,"allow_deletions":false,"required_conversation_resolution":true}'
```
3. 验证 `curl https://api.github.com/repos/SIX2090/wms/branches/main/protection` 返回 200

**验收**：`git push origin main` 直接推送应被拒绝（需走 PR）；force push 应被拒绝。

---

## 执行顺序建议

1. **P1-1**（PO 状态提示）→ 产品代码，优先 ✅ 已完成（commit `15eb92b1`）
2. **P2-1**（python3 → sys.executable + UTF-8 编码）→ 独立测试文件 ✅ 已完成（commit `eaea8857`）
3. **P2-2**（warehouse/golden 收集冲突）→ **已评估不修复（Won't Fix）**，属测试环境差异，分组运行规避
4. **M-1**（GitHub 分支保护）→ 由 owner 手动执行，AI 仅输出操作步骤

每个修复完成后：commit + push → 验证 `git log -1` == `git log origin/main -1` → 在 `WMS_BUG_BASELINE.md` 登记（若为 BUG 则加 BUG-YYYY-MM-DD-NNN）→ 最后统一跑 `python3 -m pytest tests/ -q` + `python3 scripts/verify_wms_bugs.py` 确认无回归。

> **本批执行结果（2026-08-02）**：P1-1、P2-1 已修复并推送 main（本地 HEAD == origin/main == `eaea8857`）；P2-2 经实测三方案均会破坏 CI，回退保持原状，单独分组运行均通过；M-1 为平台限制待 owner 手动操作。最终验证：lint 0 违规、无裸 fetch、verify_wms_bugs 回归通过、关键回归 26 passed + golden 102 passed。
