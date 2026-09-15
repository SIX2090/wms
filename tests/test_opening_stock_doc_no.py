# -*- coding: utf-8 -*-
"""ARCH-OS-DOC-01 回归：generate_order_no('QS') 期初库存单据取号。

根因防护：_generate_order_no_locked 的 prefix 分派链是白名单式，未登记的
prefix 会落到 `else: last_order = None`，于是每次取号都从 0001 开始，
第二条单据直接撞 opening_stock_doc.doc_no 唯一约束返回 500（用户看到的是
"保存失败"）。本测试锁定 QS 分支的存在与正确性。

覆盖：
  T1 QS 已登记在查询分支（能找到同月已有单号并递增）
  T2 QS 已登记在字段取值分支（不会取到 order_no 之类的错误字段）
  T3 连续取号不重复、格式为 QS+YYMM+4位
  T4 跨月份各自从 0001 开始
  T5 首个取号（无历史单）为 QS{YYMM}0001
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")

# 必须在导入 app 前把库设为内存库（conftest 已设，这里双保险）
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app import app as flask_app  # noqa: E402
from app import db, generate_order_no, OpeningStockDoc  # noqa: E402


class TestOpeningStockDocNoGeneration:
    """QS 期初库存单取号。"""

    def setup_method(self):
        self.ctx = flask_app.app_context()
        self.ctx.push()
        db.create_all()
        # 隔离：内存库在多次测试间共享，必须清掉上一例遗留的单据，
        # 否则序号断言会受前序测试影响（首轮实现即踩此坑）。
        db.session.query(OpeningStockDoc).delete()
        db.session.commit()

    def teardown_method(self):
        db.session.query(OpeningStockDoc).delete()
        db.session.commit()
        db.session.remove()
        self.ctx.pop()

    def test_t1_first_doc_no_starts_from_0001(self):
        """库里没有单据时，首个单号为 QS+YYMM+0001。"""
        no = generate_order_no('QS')
        assert re.fullmatch(r'QS\d{4}\d{4}', no), f'单号格式应为 QS+YYMM+4位，实际 {no}'
        assert no.endswith('0001'), f'首个单号应以 0001 结尾，实际 {no}'

    def test_t2_consecutive_calls_do_not_collide(self):
        """连续取号不重复（防 prefix 未登记导致每次从 0001 开始）。"""
        first = generate_order_no('QS')
        db.session.add(OpeningStockDoc(doc_no=first))
        db.session.commit()
        second = generate_order_no('QS')
        assert second != first, f'连续取号撞号：{first} == {second}'
        assert second.endswith('0002'), f'第二个单号应为 0002，实际 {second}'

    def test_t3_doc_no_matches_generate_and_persist_roundtrip(self):
        """取号 → 落库 → 再取号，三个单号互不相同且严格递增。"""
        nos = []
        for _ in range(3):
            no = generate_order_no('QS')
            db.session.add(OpeningStockDoc(doc_no=no))
            db.session.commit()
            nos.append(no)
        assert len(set(nos)) == 3, f'三个单号应互不相同：{nos}'
        seqs = [int(n[-4:]) for n in nos]
        assert seqs == [1, 2, 3], f'序号应严格递增：{seqs}'

    def test_t4_different_months_independent_sequences(self):
        """跨月份各自独立从 0001 开始（月份段隔离）。"""
        from datetime import date
        this_month = generate_order_no('QS')
        db.session.add(OpeningStockDoc(doc_no=this_month))
        db.session.commit()
        # 造一条上个月的单据，本月取号不应受其影响
        db.session.add(OpeningStockDoc(doc_no='QS25019999'))
        db.session.commit()
        again = generate_order_no('QS')
        ym_now = date.today().strftime('%y%m')
        assert again.startswith(f'QS{ym_now}'), f'本月单号应带本月月份段：{again}'
        assert again.endswith('0002'), f'上月单据不应影响本月序号：{again}'

    def test_t5_qs_branch_registered_in_source(self):
        """静态锁定：QS 必须同时登记在查询分支与字段取值分支。

        这是 R6 的回归防护——只登记一处会导致取号静默从 0001 开始。
        """
        src = (APP_DIR / 'app.py').read_text(encoding='utf-8')
        assert "elif prefix == 'QS':" in src, 'QS 未登记在 prefix 查询分支'
        assert 'OpeningStockDoc.doc_no.like' in src, 'QS 查询未按 doc_no 过滤'
        assert 'last_no = last_order.doc_no' in src, 'QS 未登记在字段取值分支'

    def test_t6_qs_does_not_break_other_prefixes(self):
        """QS 分支不得影响既有 prefix（回归）。"""
        for prefix in ('IN', 'OU', 'CK', 'TF', 'ADJ'):
            no = generate_order_no(prefix)
            assert no.startswith(prefix), f'{prefix} 取号前缀被破坏：{no}'
            assert re.fullmatch(rf'{prefix}\d{{4}}\d{{4}}', no), f'{prefix} 格式异常：{no}'
