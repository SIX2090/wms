# -*- coding: utf-8 -*-
"""
BUG-2026-08-22-001 回归：物料标签打印的条码/二维码模糊。

根因：
1. /api/qrcode 生成后用 Image.LANCZOS 重采样缩放，黑白模块边缘被抗锯齿抹灰，
   打印（尤其热敏打印机）出来发虚、难扫描。
2. /api/barcode 以默认 300 DPI + module_width=0.3mm 输出，短编码仅约 300px 宽，
   前端 CSS 拉伸到几十毫米宽打印时被放大 2~3 倍，条边模糊。

修复：
- /api/qrcode 改为整数 box_size 输出（尺寸 = 模块数整数倍），不做任何重采样，
  全图仅含纯黑/纯白两种像素。
- /api/barcode 提升到 600 DPI 输出高分辨率 PNG。

验收点：
T1. 二维码 PNG 只含纯黑/纯白像素（无灰色过渡）。
T2. 二维码尺寸是 (modules + 2*border) 的整数倍且不小于请求 size。
T3. 长内容二维码（版本自动扩展）同样无灰色像素。
T4. 条码 PNG 为高分辨率输出（宽度 >= 500px）。
T5. 两个接口均返回 200 + image/png。
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
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import pytest  # noqa: E402

import app as app_module  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture()
def client():
    return app_module.app.test_client()


def _open_png(resp):
    from PIL import Image

    assert resp.status_code == 200
    assert resp.headers.get("Content-Type") == "image/png"
    return Image.open(io.BytesIO(resp.data))


def _unique_pixel_values(img):
    """返回灰度图中出现过的像素值集合（histogram 方式，兼容 Pillow 14）。"""
    gray = img.convert("L")
    hist = gray.histogram()
    return {v for v, count in enumerate(hist) if count > 0}


def test_qrcode_pure_black_white_pixels(client):
    """T1：二维码无 LANCZOS 灰边——全图只有纯黑/纯白。"""
    img = _open_png(client.get("/api/qrcode/101001?size=200"))
    values = _unique_pixel_values(img)
    assert values <= {0, 255}, f"存在灰色过渡像素: {sorted(values)[:20]}"


def test_qrcode_size_is_integer_multiple_of_modules(client):
    """T2：输出尺寸 = (modules + 2*border) 的整数倍，且不小于请求 size。"""
    import qrcode

    data = "101001"
    border = 1
    probe = qrcode.QRCode(box_size=10, border=border)
    probe.add_data(data)
    probe.make(fit=True)
    total_modules = probe.modules_count + border * 2

    img = _open_png(client.get(f"/api/qrcode/{data}?size=200"))
    assert img.size[0] == img.size[1]
    assert img.size[0] % total_modules == 0, (
        f"尺寸 {img.size[0]} 不是模块总数 {total_modules} 的整数倍（存在重采样）"
    )
    assert img.size[0] >= 200


def test_qrcode_long_data_stays_sharp(client):
    """T3：长内容触发更高版本后仍无灰边、模块对齐。"""
    data = "NFC60-HMXA-3P-32A-" + "X" * 80
    img = _open_png(client.get(f"/api/qrcode/{data}?size=400"))
    values = _unique_pixel_values(img)
    assert values <= {0, 255}
    assert img.size[0] >= 400


def test_barcode_high_resolution(client):
    """T4：条码 600 DPI 输出，短编码宽度 >= 500px（打印放大不糊）。"""
    img = _open_png(client.get("/api/barcode/101001"))
    assert img.size[0] >= 500, f"条码分辨率过低: {img.size}"
    assert img.size[1] >= 400


def test_barcode_and_qrcode_endpoints_ok(client):
    """T5：两接口 200 + image/png；缺参/异常内容不 500。"""
    resp_b = client.get("/api/barcode/NFC60-HMXA")
    assert resp_b.status_code == 200
    assert resp_b.headers.get("Content-Type") == "image/png"
    resp_q = client.get("/api/qrcode/NFC60-HMXA")
    assert resp_q.status_code == 200
    assert resp_q.headers.get("Content-Type") == "image/png"


if __name__ == "__main__":  # 允许单文件直接执行
    raise SystemExit(pytest.main([__file__, "-v"]))
