# Bug: 删除采购入库单后库存台账残留

> Status: FIXED
> Mode: (default)
> Severity: functional
> Author: 用户反馈
> Last updated: 2026-08-17

## Symptom

采购入库单被反提交并删除后，库存台账仍然可以查到该采购入库单。

## Expected

删除草稿入库单后，该单据产生的库存流水应一并清理；库存台账、库存月报等基于库存流水的报表不应再显示已删除单据。

## Reproduction

- 步骤：创建已完成采购入库单 → 反提交 → 删除 → 查询库存台账。
- 测试位置：`tests/test_bug_2026_08_17_006_delete_in_order_ledger_cleanup.py`
- 复现稳定性：修复前连续 3 次失败；移除修复后回归测试重新失败。

## Hypotheses & diagnosis

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | 删除入库单只删除主单和明细，未删除关联 `StockTransaction` | confirmed | 修复前删除成功后，`reference_type='in_order'`、`reference_id=单据 ID` 的流水仍有 2 条；台账正从该表读取 |
| H2 | 台账只是错误缓存了已删除单据 | eliminated | `_collect_ledger_rows()` 每次直接查询 `StockTransaction`，不存在独立的单据缓存 |

## Root cause

反提交流程会写入 `reference_type='in_order'`、`reference_id=入库单 ID` 的负向补偿流水，用于库存追溯。单张删除和批量删除路径原本只删除入库单及其明细，没有删除同一引用 ID 的正向和负向流水，形成了指向已删除单据的悬挂台账记录。

## Fix

- 改动文件：`app/routes/in_order.py`
- 单张删除和批量删除在物理删除入库单前，执行同一引用条件的流水清理：`reference_type='in_order'` 且 `reference_id=order.id`。
- 仅在已满足草稿删除条件的路径执行，不改变已完成单据必须先反提交的业务边界，也不删除操作审计记录。
- 改动文件：`tests/test_bug_2026_08_17_006_delete_in_order_ledger_cleanup.py`
- 新增完整链路回归，验证单据、关联流水和仓库库存台账均为空。

## Verification

- V-1: 修复前回归测试 → RED，连续 3 次稳定复现。
- V-2: 修复后回归测试 → GREEN，1 passed。
- V-3: 临时 stash 修复 → RED；恢复修复 → GREEN，证明测试确实捕获本次根因。
- V-4: 入库单域专项测试 → 21 passed。
- V-5: `scripts/lint_wms_rules.py` → 0 处违规。
- V-6: `scripts/verify_wms_bugs.py` → 回归检查通过。
- V-7: `python -m compileall -q app` → 通过。

## Regression test

- 路径：`tests/test_bug_2026_08_17_006_delete_in_order_ledger_cleanup.py`
- 名称：`test_delete_in_order_cleans_stock_transactions_and_ledger`

## Pattern analysis

| 搜索方式 | 命中数 | 是否本次同类隐患 |
|---|---:|---|
| `db.session.delete(order)` in route delete paths | 14 | 需后续逐一核对：不同单据的流水生命周期和删除保护规则不完全相同 |
| `StockTransaction.query.filter_by(...)` in route modules | 2 | 本次修复已覆盖入库单单张和批量删除两入口 |

## Open questions / Follow-ups

- 其他允许物理删除的库存业务单据，例如出库、调整、委外等，应单独核对其流水清理策略；本次不扩展修改，避免混入不同单据的状态机变更。
- 历史数据库中已经存在的悬挂流水需要另行提供人工确认后的清理脚本，不在删除接口中自动追溯清理。
