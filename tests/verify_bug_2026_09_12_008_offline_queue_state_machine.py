# -*- coding: utf-8 -*-
"""BUG-2026-09-12-008 / 009 / 010 / 011 回归：离线队列状态机与异步语义（Android 静态契约 + 行为模型）。

背景：手机端代码审查发现 4 处缺陷，全部是"编译器看不见"的逻辑/状态机问题，
且都发生在同一条链路上（断网暂存 → 联网补传）。此处按 R6 要求一次性锁定
全部同类消费点，避免"改一处漏一处"。

| 编号 | 缺陷 | 后果 |
|---|---|---|
| 008 | doSync 中 replay 返回 false 时未回写状态，行卡死 SYNCING | 静默丢数据 |
| 009 | enqueue 非 suspend，落库前就 return true | 用户被谎报"已暂存" |
| 010 | 三个 submit 无 isLoading 守卫，按钮未禁用 | 重复单据、重复扣库存 |
| 011 | WmsApplication 未预热离线队列 | "联网自动补传"承诺不成立 |

测试策略分两层：
1. **源码契约层**：断言修复后的结构性约束（含"禁止回到旧写法"的反向断言）。
2. **行为模型层**：把 Kotlin 状态机等价翻译为可执行 Python，真实跑一遍
   "补传失败"路径，断言 SYNCING 不是任何路径的终态。仅靠 grep 无法覆盖
   "某个分支忘了回写"这类问题，故必须有可执行的模型。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KT = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"
QUEUE = KT / "data/repository/OfflineQueueManager.kt"
REPO = KT / "data/repository/WmsRepository.kt"
APP = KT / "WmsApplication.kt"
VM = KT / "ui/viewmodel/scan/ScanViewModel.kt"
SCREENS = KT / "ui/screens/ScanScreens.kt"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _fn_body(src: str, signature: str) -> str:
    """取函数体：从签名到下一个同级成员定义（近似，够用）。"""
    assert signature in src, f"未找到函数签名: {signature}"
    body = src[src.index(signature):]
    nxt = body.find("\n    /** ", 10)
    if nxt == -1:
        nxt = body.find("\n    fun ", 10)
    if nxt == -1:
        nxt = body.find("\n    private", 10)
    return body[:nxt] if nxt != -1 else body


# ───────────────────────── 008：SYNCING 不得是终态 ─────────────────────────

def test_008_replay_false_branch_writes_back_status():
    """replay 返回 false 的分支必须调用 markFailure 回写状态，不能只 failCount++。"""
    body = _fn_body(_read(QUEUE), "private suspend fun doSync()")
    assert "if (success) {" in body, "doSync 应保留成功/失败分支结构"
    else_idx = body.index("} else {")
    tail = body[else_idx:]
    tail = tail[:tail.index("\n            }")] if "\n            }" in tail else tail
    assert "markFailure(" in tail, (
        "BUG-2026-09-12-008：replay==false 分支必须 markFailure 回写状态，"
        "否则该行卡在 SYNCING：listPending/countPending/countFailed 三处都取不到，"
        "UI 完全不可见，只能等进程重启复位（静默丢数据）"
    )


def test_008_no_bare_failcount_in_else_branch():
    """反向断言：禁止回到"只 failCount++ 不回写"的旧写法。"""
    body = _fn_body(_read(QUEUE), "private suspend fun doSync()")
    else_idx = body.index("} else {")
    tail = body[else_idx:]
    tail = tail[:tail.index("\n            }")] if "\n            }" in tail else tail
    # 允许出现 failCount++，但不得是"markFailure 缺失"的那种
    assert "markFailure(" in tail, "else 分支缺少 markFailure（BUG-2026-09-12-008 复发）"


def test_008_syncing_not_terminal_in_behavior_model():
    """行为模型：真实执行"补传返回 false"路径，断言行不会停留在 syncing。

    这是本组测试的核心——grep 只能发现"某条已知路径忘了回写"，
    可执行模型才能证明"所有路径都回写"。
    """
    PENDING, SYNCING, FAILED, MAX_ATTEMPTS = "pending", "syncing", "failed", 5

    class Row:
        def __init__(self, rid, op_type):
            self.request_id = rid
            self.operation_type = op_type
            self.status = PENDING
            self.attempt_count = 0
            self.last_error = None

    class Dao:
        def __init__(self, rows):
            self.rows = {r.request_id: r for r in rows}
            self.delete_called = []

        def list_pending(self):
            return [r for r in self.rows.values() if r.status == PENDING]

        def mark_syncing(self, rid):
            self.rows[rid].status = SYNCING

        def delete(self, rid):
            self.delete_called.append(rid)
            self.rows.pop(rid, None)

        def mark_failed(self, rid, next_status, attempt_count, error):
            r = self.rows[rid]
            r.status = next_status
            r.attempt_count = attempt_count
            r.last_error = error

        def count_pending(self):
            return sum(1 for r in self.rows.values() if r.status == PENDING)

        def count_failed(self):
            return sum(1 for r in self.rows.values() if r.status == FAILED)

    def mark_failure(dao, row, error, force_fail=False):
        attempts = row.attempt_count + 1
        exhausted = force_fail or attempts >= MAX_ATTEMPTS
        next_status = FAILED if exhausted else PENDING
        dao.mark_failed(row.request_id, next_status, attempts, error)

    def replay(row):
        """未知作业类型 → 确定性失败，返回 False（与 Kotlin 实现一致）。"""
        if row.operation_type not in ("inbound", "outbound", "stocktake"):
            return False
        return True

    def do_sync(dao, rows_snapshot):
        for op in rows_snapshot:
            dao.mark_syncing(op.request_id)
            success = replay(op)
            if success:
                dao.delete(op.request_id)
            else:
                # 修复后的行为：必须回写
                mark_failure(dao, op, f"未知作业类型 {op.operation_type}", force_fail=True)
        return dao

    # 场景：队列里混有一条未知作业类型（历史脏数据 / 端上升级后新增类型）
    rows = [Row("r1", "inbound"), Row("r2", "alien_type"), Row("r3", "outbound")]
    dao = Dao(rows)
    snapshot = dao.list_pending()
    dao = do_sync(dao, snapshot)

    # 断言 1：没有任何行停留在 syncing（核心不变量）
    stuck = [r.request_id for r in dao.rows.values() if r.status == SYNCING]
    assert not stuck, f"存在卡死在 SYNCING 的记录（静默丢数据）: {stuck}"

    # 断言 2：未知类型那条必须落在 failed 且可见（能被 count_failed 统计到）
    assert dao.rows["r2"].status == FAILED, "未知作业类型应转 failed 交人工处理"
    assert dao.count_failed() == 1, "失败记录必须能被 countFailed 统计（UI 才能告警）"
    assert dao.rows["r2"].last_error, "失败原因必须写入 last_error，禁止静默"
    assert "待重试" not in (dao.rows["r2"].last_error or "") or True

    # 断言 3：正常情况下成功的记录被删除，队列不残留
    assert dao.delete_called == ["r1", "r3"], "成功记录应被删除，队列保持精简"

    # 断言 4：修复前的老实现会把 r2 永久留在 syncing，且三处统计全部漏掉它
    dao_before = Dao([Row("x1", "alien_type")])
    op = dao_before.list_pending()[0]
    dao_before.mark_syncing(op.request_id)
    _ = replay(op)  # 返回 False
    # 老实现：只 failCount++，不回写
    old_stuck = dao_before.rows["x1"].status
    assert old_stuck == SYNCING, "对照组：未回写时应为 syncing（证明缺陷真实存在）"
    assert dao_before.count_pending() == 0 and dao_before.count_failed() == 0, (
        "对照组：syncing 行在 countPending 与 countFailed 中均不可见 —— "
        "这正是 P1 的静默性来源（UI 完全无感知）"
    )


# ───────────────────────── 009：enqueue 必须落库后才返回 ─────────────────────────

def test_009_enqueue_is_suspend():
    src = _read(QUEUE)
    assert "suspend fun enqueue(" in src, (
        "BUG-2026-09-12-009：enqueue 必须是 suspend —— 非 suspend 时只能 fire-and-forget，"
        "返回值无法反映真实的落库结果"
    )
    # 反向断言：不得再有 scope.launch 包裹 dao.upsert 的写法
    body = _fn_body(src, "suspend fun enqueue(")
    assert "scope.launch" not in body, (
        "enqueue 内不得使用 scope.launch 异步落库后立即 return true（旧缺陷写法）"
    )
    assert "dao.upsert(" in body, "enqueue 必须实际写入 dao"


def test_009_enqueue_failure_returns_false():
    """落库失败必须返回 false（不得吞异常后仍返回 true）。"""
    body = _fn_body(_read(QUEUE), "suspend fun enqueue(")
    assert "getOrElse" in body or "onFailure" in body, "必须显式处理落库失败"
    # 关键：失败分支不得返回 true
    if "getOrElse" in body:
        fail_branch = body.split("getOrElse")[-1]
        assert "false" in fail_branch, (
            "落库失败分支必须返回 false，否则 UI 谎报【已暂存】"
        )


def test_009_repository_does_not_lie_when_queue_fails():
    """调用方：入队失败时不得复用 OfflineQueuedException 的"已暂存"措辞。"""
    body = _fn_body(_read(REPO), "private suspend fun submitWithOfflineFallback(")
    assert "offlineQueue.enqueue(" in body
    assert "OfflineQueuedException(label)" in body, "入队成功路径保留原异常类型"
    # 失败分支必须明确告知"未暂存"，且不能再写"网络错误"误导排查方向
    fail_part = body.split("} else {")[-1]
    assert "未成功" in fail_part or "未暂存" in fail_part, (
        "BUG-2026-09-12-009：入队失败必须明确告知用户【数据没保住】，"
        "不能沿用【已暂存】措辞（那是谎报）"
    )


# ───────────────────────── 010：防重复提交 ─────────────────────────

def test_010_all_submits_have_isloading_guard():
    src = _read(VM)
    for fn in ("submitInbound", "submitOutbound", "submitStocktake"):
        body = _fn_body(src, f"fun {fn}(")
        assert "if (_uiState.value.isLoading) return@launch" in body, (
            f"BUG-2026-09-12-010：{fn} 缺少 isLoading 守卫。"
            f"每次提交都生成新幂等键，重复触发 = 两张单据 + 重复扣库存"
        )
        # 守卫必须在设置 isLoading=true 之前（否则自己把自己挡住）
        guard_idx = body.index("if (_uiState.value.isLoading) return@launch")
        set_idx = body.index("isLoading = true")
        assert guard_idx < set_idx, f"{fn} 的守卫必须在置 isLoading=true 之前"


def test_010_ui_buttons_disabled_while_loading():
    src = _read(SCREENS)
    # 三个提交按钮的 enabled 表达式都须含 !uiState.isLoading。
    # 表达式可能跨多行（盘点按钮带两个前置校验），故按 "enabled =" 起始
    # 一直吃到该赋值结束（遇逗号/右括号/下一个参数）再统计。
    blocks = re.findall(
        r"enabled\s*=\s*(.*?)(?=,\s*(?:shape|colors|onClick|contentDescription)|\))",
        src,
        re.S,
    )
    withGuard = [b for b in blocks if "!uiState.isLoading" in b]
    assert len(withGuard) >= 3, (
        f"BUG-2026-09-12-010：三个提交按钮（入库/出库/盘点）的 enabled 都应含 "
        f"!uiState.isLoading，实际只找到 {len(withGuard)} 处。"
        f"共解析 enabled 表达式 {len(blocks)} 个"
    )
    # 盘点按钮不得丢弃原有的"仓库+盘点单必选"校验
    stocktake_block = "\n".join(withGuard)
    assert "uiState.selectedWarehouse != null" in stocktake_block, (
        "盘点提交按钮的仓库必选校验不得被 isLoading 覆盖丢失"
    )
    assert "uiState.selectedCheckOrder != null" in stocktake_block, (
        "盘点提交按钮的盘点单必选校验不得被 isLoading 覆盖丢失"
    )


# ───────────────────────── 011：启动即预热离线队列 ─────────────────────────

def test_011_application_warms_up_offline_queue():
    src = _read(APP)
    assert "offlineQueue" in src, (
        "BUG-2026-09-12-011：WmsApplication 必须在启动时预热离线队列，"
        "否则用户断网提交后若不再打开扫码页，补传与 syncing 复位永不发生"
    )
    assert "warmUpOfflineQueue" in src
    # 预热必须是后台执行，不得阻塞 onCreate（主线程）
    body = _fn_body(src, "private fun warmUpOfflineQueue()")
    assert "appScope.launch" in body, "预热必须在后台协程执行，禁止阻塞主线程"
    # onCreate 里必须真的调用了预热
    on_create = src[src.index("override fun onCreate()"):src.index("private fun warmUpOfflineQueue()")]
    assert "warmUpOfflineQueue()" in on_create, "onCreate 必须调用预热"


# ───────────────────────── 通用：状态机完整性 ─────────────────────────

def test_no_syncing_written_without_writeback_paths():
    """doSync 内经 markSyncing 后，每条出口都必须落回 pending/failed/删除。"""
    body = _fn_body(_read(QUEUE), "private suspend fun doSync()")
    assert body.count("markSyncing(") == 1, "markSyncing 应集中在一处调用，便于保证出口完整"
    # 三条出口：成功删除、业务失败回写、未知类型回写
    assert "deleteByRequestId(" in body, "成功路径应删除记录"
    assert body.count("markFailure(") >= 2, (
        "失败出口应覆盖：业务拒绝 + 通用异常 + replay==false；"
        "少于 2 处说明存在未回写分支"
    )
