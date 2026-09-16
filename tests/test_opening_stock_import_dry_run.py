# -*- coding: utf-8 -*-
"""P1-B 期初库存导入预检两段式（dry-run）回归。

用户诉求：导入是批量写库存的高风险动作，原来"选文件 → 直接入账"一步到位，
看不到会导入什么、跳过哪些、会不会覆盖已有单据，出错只能事后删单回冲。

两段式：`dry_run=true` 只校验不落库并返回逐行结果 → 用户确认后正式导入。

核心不变量（本测试重点）：
  - **预检绝不写任何数据**：不建单据、不动 Material.stock、不落明细、不写流水；
  - 预检与正式导入**共用同一条代码路径**（同一解析+校验），dry_run 只控制写不写，
    因此"预检说能导入的行"与"正式导入真正写入的行"必须一致（不得漂移）；
  - 预检如实区分"新增"与"并入已有期初"，不掩盖叠加。

覆盖：
  T1 预检返回 dry_run 标记 + 逐行结果 + 计数
  T2 预检零写入：单据/明细/库位账/总账库存/流水 全部无变化（最核心的不变量）
  T3 预检识别非法行：物料不存在 / 仓库不存在 / 缺仓库 / 数量非法 / 文件内重复
  T4 预检识别"并入已有期初"并给出当前合计
  T5 预检后正式导入结果与预检一致（同一路径不漂移）
  T6 预检 request 不写 OperationLog
  T7 正式导入（不带 dry_run）行为不变：照旧落库并生成单据
  T8 扩展名/大小校验对预检同样生效
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app import app as flask_app  # noqa: E402
from app import (  # noqa: E402
    LocationInventory,
    Material,
    OpeningStock,
    OpeningStockDoc,
    OperationLog,
    StockTransaction,
    Unit,
    User,
    Warehouse,
    db,
)

flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False

TEMPLATE_SRC = APP_DIR / "templates" / "batch_import.html"


def _xlsx(rows):
    """按导入模板表头生成 xlsx 字节流。"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["仓库编码", "物料编码", "物料名称", "规格", "单位",
               "数量", "单价", "备注", "日期"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestOpeningStockImportDryRun:
    """两段式导入：预检只读、正式导入写库，且两者判定一致。"""

    def setup_method(self):
        self.ctx = flask_app.app_context()
        self.ctx.push()
        db.create_all()
        self._wipe()

        unit = Unit(code="PCS", name="个")
        db.session.add(unit)
        db.session.flush()
        self.wh1 = Warehouse(code="W1", name="一号仓", status="active")
        self.wh2 = Warehouse(code="W2", name="停用仓", status="inactive")
        db.session.add_all([self.wh1, self.wh2])
        db.session.flush()
        self.m1 = Material(code="M001", name="螺丝", unit_id=unit.id, stock=0)
        self.m2 = Material(code="M002", name="螺母", unit_id=unit.id, stock=0)
        db.session.add_all([self.m1, self.m2])
        db.session.commit()

        self.client = flask_app.test_client()
        self._login()

    def teardown_method(self):
        self._wipe()
        db.session.commit()
        db.session.remove()
        self.ctx.pop()

    def _wipe(self):
        for model in (OpeningStock, OpeningStockDoc, StockTransaction,
                      LocationInventory, OperationLog, Material, Warehouse, Unit, User):
            db.session.query(model).delete()
        db.session.commit()

    def _login(self):
        from werkzeug.security import generate_password_hash
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin",
                must_change_password=False,
            ))
            db.session.commit()
        self.client.post("/login",
                         data={"username": "admin", "password": "admin"},
                         content_type="application/x-www-form-urlencoded")

    def _import(self, rows, dry_run=True, filename="stock.xlsx"):
        data = {"file": (_xlsx(rows), filename)}
        if dry_run:
            data["dry_run"] = "true"
        return self.client.post("/opening_stock/import", data=data,
                                content_type="multipart/form-data")

    def _snapshot(self):
        """库存相关全量快照，用于证明预检零写入。"""
        return {
            "docs": OpeningStockDoc.query.count(),
            "lines": OpeningStock.query.count(),
            "stock": {m.code: float(m.stock or 0) for m in Material.query.all()},
            "txn": StockTransaction.query.count(),
            "loc": LocationInventory.query.count(),
            "logs": OperationLog.query.count(),
        }

    # ---- T1 预检返回结构 ----

    def test_t1_dry_run_returns_preview(self):
        resp = self._import([["W1", "M001", "螺丝", "", "个", 100, 5, "", ""]])
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        assert body["dry_run"] is True, "预检响应必须带 dry_run 标记"
        assert body["imported"] == 1
        assert body["skipped"] == 0
        rows = body["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert row["action"] == "import"
        assert row["material_code"] == "M001"
        assert row["quantity"] == 100
        assert body["fresh_count"] == 1, "首次导入应算新增"
        assert body["overwrite_count"] == 0

    # ---- T2 预检零写入（最核心） ----

    def test_t2_dry_run_writes_nothing(self):
        before = self._snapshot()
        resp = self._import([
            ["W1", "M001", "螺丝", "", "个", 100, 5, "", ""],
            ["W1", "M002", "螺母", "", "个", 50, 2, "", ""],
        ])
        assert resp.status_code == 200
        assert resp.get_json()["imported"] == 2
        after = self._snapshot()
        assert after == before, f"预检绝不能写任何数据\nbefore={before}\nafter={after}"

    def test_t2b_dry_run_writes_nothing_even_with_errors(self):
        """含错误行的预检同样不得写库（不能因为是错误文件就放松）。"""
        before = self._snapshot()
        self._import([
            ["W1", "M001", "螺丝", "", "个", 100, 5, "", ""],
            ["W1", "NOPE", "不存在", "", "个", 10, 1, "", ""],
        ])
        assert self._snapshot() == before

    def test_t2c_dry_run_writes_nothing_even_with_overwrite(self):
        """已存在期初时预检也不得改动那笔期初（不能顺手"修正"）。"""
        st, body = self.client.post("/opening_stock/save", json={
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 5}],
        }).status_code, None
        assert st == 200
        before = self._snapshot()
        self._import([["W1", "M001", "螺丝", "", "个", 999, 9, "", ""]])
        assert self._snapshot() == before, "预检不得修改既有期初"
        # 既有期初数量原样保留
        line = OpeningStock.query.filter_by(material_id=self.m1.id).first()
        assert float(line.quantity) == 100

    # ---- T3 非法行识别 ----

    def test_t3_error_rows_are_flagged(self):
        resp = self._import([
            ["W1", "NOPE", "不存在", "", "个", 10, 1, "", ""],          # 物料不存在
            ["NOPE_WH", "M001", "螺丝", "", "个", 10, 1, "", ""],       # 仓库不存在
            ["", "M001", "螺丝", "", "个", 10, 1, "", ""],              # 缺仓库
            ["W2", "M001", "螺丝", "", "个", 10, 1, "", ""],            # 停用仓库
            ["W1", "M001", "螺丝", "", "个", -5, 1, "", ""],            # 数量为负
            ["W1", "M001", "螺丝", "", "个", 10, 1, "", ""],            # 有效行
            ["W1", "M001", "螺丝", "", "个", 20, 1, "", ""],            # 文件内重复
            ["W1", "M002", "螺母", "", "个", 50, 1, "", ""],            # 有效行（不同物料）
        ])
        body = resp.get_json()
        assert body["imported"] == 2, "M001 与 M002 各一行有效"
        assert body["skipped"] == 6
        skip_reasons = " ".join(r["reason"] for r in body["rows"] if r["action"] == "skip")
        assert "不存在" in skip_reasons
        assert "未指定仓库" in skip_reasons
        assert "已停用" in skip_reasons
        assert "不能小于 0" in skip_reasons
        assert "重复" in skip_reasons
        # 逐行 action 齐全
        assert all(r["action"] in ("import", "skip") for r in body["rows"])
        # 跳过的行必须带原因，不能只有 action
        assert all(r["reason"] for r in body["rows"] if r["action"] == "skip")

    def test_t3b_invalid_quantity_is_skip_not_500(self):
        """BUG-2026-09-16-015 回归：非法数量必须是"跳过该行"，不得 500。

        原实现 `parse_float_value(x, None)` 在 value 非法时执行 `float(None)`
        抛 TypeError，被外层 except Exception 兜成 500「服务器内部错误」，
        用户拿不到"哪一行、错在哪"。非数字/负数/空值三种都要覆盖。
        """
        for bad_qty, expect in [("abc", "无效"), (-5, "不能小于 0"), ("", "数量为空")]:
            resp = self._import([["W1", "M001", "螺丝", "", "个", bad_qty, 1, "", ""]])
            assert resp.status_code == 200, f"数量 {bad_qty!r} 不应 500，实际 {resp.status_code}"
            body = resp.get_json()
            assert body["status"] == "success"
            assert body["imported"] == 0
            assert body["skipped"] == 1
            reason = body["rows"][0]["reason"]
            assert expect in reason, f"数量 {bad_qty!r} 的提示应含 {expect!r}，实际 {reason!r}"

    def test_t3c_bad_row_does_not_poison_dedup(self):
        """BUG-2026-09-16-016 回归：被跳过的坏行不得占用去重键，堵死后续合法行。

        原实现在"物料+仓库重复"检查后立刻 `seen_keys.add(dedup_key)`，
        于是紧接着的非法行（数量为负）虽被跳过，其 (物料,仓库) 键已登记；
        文件里再出现同一 (物料,仓库) 的**合法**行就会被误判成"文件内重复"
        一并跳过。用户按提示改了错误行重传，仍然一行都导不进去，
        且提示是"重复"而非真实原因——极强的误导。
        """
        resp = self._import([
            ["W1", "M001", "螺丝", "", "个", -5, 1, "", ""],      # 坏行（负数）
            ["W1", "M001", "螺丝", "", "个", 100, 5, "", ""],    # 修复后的合法行
        ])
        body = resp.get_json()
        assert body["imported"] == 1, (
            "坏行不得占用去重键，同 (物料,仓库) 的合法行必须能导入；"
            f"实际 rows={[(r['row_no'], r['action'], r.get('reason')) for r in body['rows']]}")
        assert body["skipped"] == 1
        assert body["rows"][0]["action"] == "skip"
        assert body["rows"][1]["action"] == "import"

    def test_t3d_real_duplicate_still_detected(self):
        """去重不能因上述修复而失效：两行**都合法**时仍是重复。"""
        resp = self._import([
            ["W1", "M001", "螺丝", "", "个", 100, 5, "", ""],
            ["W1", "M001", "螺丝", "", "个", 200, 5, "", ""],
        ])
        body = resp.get_json()
        assert body["imported"] == 1
        assert body["skipped"] == 1
        assert "重复" in body["rows"][1]["reason"]

    # ---- T4 并入已有期初 ----

    def test_t4_detects_merge_into_existing(self):
        self.client.post("/opening_stock/save", json={
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 5}],
        })
        resp = self._import([["W1", "M001", "螺丝", "", "个", 50, 5, "", ""]])
        row = resp.get_json()["rows"][0]
        assert row["action"] == "import"
        assert row["existing_docs"] == 1, "应识别出该物料在该仓已有期初"
        assert float(row["existing_quantity"]) == 100, "应给出当前已有合计"
        assert resp.get_json()["overwrite_count"] == 1
        assert resp.get_json()["fresh_count"] == 0

    def test_t4b_existing_sum_excludes_other_warehouse(self):
        """R2 多仓隔离：别的仓库的期初不得算进本仓的"已有合计"。"""
        tpl_wh2 = Warehouse(code="W3", name="二号仓", status="active")
        db.session.add(tpl_wh2)
        db.session.commit()
        self.client.post("/opening_stock/save", json={
            "warehouse_id": tpl_wh2.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": tpl_wh2.id,
                       "quantity": 777, "price": 1}],
        })
        resp = self._import([["W1", "M001", "螺丝", "", "个", 50, 5, "", ""]])
        row = resp.get_json()["rows"][0]
        assert row["existing_docs"] == 0, "本仓无期初，不应被别仓的记录命中"
        assert float(row["existing_quantity"]) == 0

    # ---- T5 预检与正式导入一致（不漂移） ----

    def test_t5_precheck_matches_real_import(self):
        """核心不变量：预检说能导入的行，正式导入必须真的导入。

        两段共用同一条解析+校验路径，dry_run 只控制写不写——若有人为预检
        另写一套校验，这条断言会失败。
        """
        rows = [
            ["W1", "M001", "螺丝", "", "个", 100, 5, "", ""],
            ["W1", "M002", "螺母", "", "个", 50, 2, "", ""],
            ["W1", "NOPE", "不存在", "", "个", 10, 1, "", ""],   # 错误行
            ["", "M001", "螺丝", "", "个", 10, 1, "", ""],       # 缺仓库
        ]
        pre = self._import(rows, dry_run=True).get_json()
        real = self._import(rows, dry_run=False).get_json()

        assert pre["imported"] == real["imported"], "预检可导入行数与正式导入不一致"
        assert pre["skipped"] == real["skipped"], "预检跳过行数与正式导入不一致"

        pre_ok = sorted(r["material_code"] for r in pre["rows"] if r["action"] == "import")
        real_ok = sorted(r["material_code"] for r in real["rows"] if r["action"] == "import")
        assert pre_ok == real_ok, f"预检与正式导入的行集合不一致：{pre_ok} vs {real_ok}"
        assert pre_ok == ["M001", "M002"]

        pre_bad = sorted(r["row_no"] for r in pre["rows"] if r["action"] == "skip")
        real_bad = sorted(r["row_no"] for r in real["rows"] if r["action"] == "skip")
        assert pre_bad == real_bad, "预检与正式导入的跳过行不一致"

    # ---- T6 预检不写操作日志 ----

    def test_t6_dry_run_no_operation_log(self):
        before_logs = OperationLog.query.count()
        self._import([["W1", "M001", "螺丝", "", "个", 100, 5, "", ""]])
        assert OperationLog.query.count() == before_logs, "预检不应写操作日志"

    # ---- T7 正式导入行为不变 ----

    def test_t7_real_import_still_works(self):
        resp = self._import([
            ["W1", "M001", "螺丝", "", "个", 100, 5, "", ""],
            ["W1", "M002", "螺母", "", "个", 50, 2, "", ""],
        ], dry_run=False)
        body = resp.get_json()
        assert body["status"] == "success"
        assert body.get("dry_run") is not True, "正式导入不得带 dry_run 标记"
        assert body["imported"] == 2
        assert body["doc_id"], "正式导入应生成单据"
        assert body["detail_url"]
        # 库存真的进来了（100×5 + 50×2）
        assert float(db.session.get(Material, self.m1.id).stock) == 100
        assert float(db.session.get(Material, self.m2.id).stock) == 50
        assert OpeningStock.query.count() == 2
        assert OpeningStockDoc.query.count() == 1

    # ---- T8 文件校验对预检同样生效 ----

    def test_t8_file_validation_applies_to_dry_run(self):
        resp = self.client.post("/opening_stock/import",
                                data={"file": (io.BytesIO(b"x"), "bad.txt"),
                                      "dry_run": "true"},
                                content_type="multipart/form-data")
        assert resp.status_code == 400, "非 Excel 文件预检也必须拒绝"

    def test_t8b_missing_header_rejected_in_dry_run(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["物料名称", "备注"])       # 缺 物料编码/数量
        ws.append(["螺丝", "x"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = self.client.post("/opening_stock/import",
                                data={"file": (buf, "bad.xlsx"), "dry_run": "true"},
                                content_type="multipart/form-data")
        assert resp.status_code == 400
        assert "表头" in resp.get_json()["msg"]

    # ---- 模板静态契约 ----

    def test_t9_template_has_two_stage_ui(self):
        """静态断言：导入卡片必须有预检按钮、确认按钮与预检结果容器。"""
        src = TEMPLATE_SRC.read_text(encoding="utf-8")
        assert "precheckOpeningStock" in src, "缺少预检入口"
        assert "confirmOpeningStockImport" in src, "缺少确认导入"
        assert "openingStockPreview" in src, "缺少预检结果容器"
        assert "dry_run" in src, "前端未传 dry_run"
        assert "openingStockPrechecked" in src, "缺少预检门禁标记"
        assert "文件已更换，请重新预检" in src, "换文件后应作废预检结果"
