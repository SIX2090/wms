# -*- coding: utf-8 -*-
"""F4.2 回归：CSV 导出加 utf-8-sig BOM + RFC 5987 中文文件名。

修复前：两处 CSV 导出（/ai/inventory_health、/ai/replenishment_smart）
用 io.StringIO + text/csv + 手工拼 Content-Disposition：
  - 无 BOM，Excel 直接打开中文列名乱码（用户必须"导入"才正常）
  - 第二处中文文件名裸放 filename="补货建议规则_….csv"，非 ASCII 乱码

修复后对齐 opening_stock.py 范式：BytesIO + TextIOWrapper('utf-8-sig')
+ send_file(download_name=…)，BOM 与 RFC 5987 编码均由框架保证。

断言以真实 HTTP 响应为准（非源码字符串匹配）。
"""
from __future__ import annotations

import os
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"

UTF8_BOM = b"\xef\xbb\xbf"


@pytest.fixture
def wms_env():
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
    os.environ.setdefault("WMS_DEBUG", "0")
    os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
    os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")

    import app as wms
    from werkzeug.security import generate_password_hash

    wms.app.config["TESTING"] = True
    wms.app.config["WTF_CSRF_ENABLED"] = False
    ctx = wms.app.app_context()
    ctx.push()
    try:
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        wms.db.session.add(wms.User(
            username="f42admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
            must_change_password=False,
        ))
        wms.db.session.commit()
        yield wms
    finally:
        wms.db.session.remove()
        ctx.pop()


@pytest.fixture
def client(wms_env, monkeypatch):
    """登录 admin，并旁路 AI 能力开关链（本测试只验证 CSV 编码，不验证权限）。"""
    monkeypatch.setattr(wms_env, "_ai_capability_allowed", lambda *a, **k: True)
    user = wms_env.User.query.filter_by(username="f42admin").first()
    with wms_env.app.test_client() as c:
        with c.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
        yield c


def _disposition_filename(resp):
    """解析 Content-Disposition 的文件名（优先 RFC 5987 filename*）。"""
    disp = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", disp)
    if m:
        return urllib.parse.unquote(m.group(1))
    m = re.search(r'filename="?([^";]+)"?', disp)
    return m.group(1) if m else ""


def test_inventory_health_csv_has_bom(client):
    resp = client.get("/ai/inventory_health?export=csv")
    assert resp.status_code == 200, resp.status_code
    assert resp.data.startswith(UTF8_BOM), "CSV 缺少 utf-8-sig BOM，Excel 打开中文会乱码"
    text = resp.data.decode("utf-8-sig")
    assert "物料编码" in text.splitlines()[0]
    assert _disposition_filename(resp) == "inventory_health_report.csv"


def test_replenishment_csv_has_bom_and_rfc5987_filename(client):
    resp = client.get("/ai/replenishment_smart?export=csv")
    assert resp.status_code == 200, resp.status_code
    assert resp.data.startswith(UTF8_BOM), "CSV 缺少 utf-8-sig BOM"
    text = resp.data.decode("utf-8-sig")
    assert "物料编码" in text.splitlines()[0]
    disp = resp.headers.get("Content-Disposition", "")
    # 中文文件名必须走 RFC 5987 filename*（否则浏览器/下载器乱码）
    assert "filename*=UTF-8''" in disp, disp
    fname = _disposition_filename(resp)
    assert fname.startswith("补货建议规则_") and fname.endswith(".csv"), fname


def test_csv_body_roundtrip_no_mojibake(client):
    """整体可被 utf-8-sig 解码，说明字节流对 Excel 友好。"""
    resp = client.get("/ai/inventory_health?export=csv")
    decoded = resp.data.decode("utf-8-sig")  # 不抛异常即通过
    assert decoded and "\ufffd" not in decoded
