# -*- coding: utf-8 -*-
"""
BUG-2026-08-13-003/004 回归测试：远程图片下载 TypeError + SSRF 重定向校验。

BUG-003: requests.get 不接受 max_redirects 参数（旧实现每次 TypeError）。
BUG-004: 旧实现 allow_redirects=True 不对 302 目标重新校验内网地址。

修复：改用 allow_redirects=False 手动逐跳跟随，每跳重新校验 scheme 与
_is_private_or_loopback_host，重定向上限 5 跳。

覆盖：
T1：直连 200 OK 图片成功。
T2：302 跳 127.0.0.1 被拒绝（内网地址）。
T3：302 跳 169.254.169.254 被拒绝（元数据服务）。
T4：302 合法外网 -> 外网成功跟随。
T5：超过 5 跳拒绝（重定向次数过多）。
T6：Location 缺失拒绝。
T7：302 跳 file:// 协议被拒绝。
T8：源码静态——无 max_redirects= 参数，使用 allow_redirects=False。
"""
from __future__ import annotations

import inspect
import io
import os
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import app as app_module  # noqa: E402


# 最小有效 1x1 RGB PNG（PIL/Image 可解析），用于伪造响应 body
import struct as _struct
import zlib as _zlib
def _mk_png_1x1():
    def _chunk(tag, data):
        crc = _zlib.crc32(tag + data) & 0xFFFFFFFF
        return _struct.pack(">I", len(data)) + tag + data + _struct.pack(">I", crc)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = _struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1 8bit RGB
    raw = b'\x00\x00\x00\x00'  # filter byte + one pixel RGB(0,0,0)
    idat = _zlib.compress(raw, 9)
    return sig + _chunk(b'IHDR', ihdr) + _chunk(b'IDAT', idat) + _chunk(b'IEND', b'')
_VALID_PNG_BYTES = _mk_png_1x1()


# 伪造 Material 对象（仅需要 .id / .image 属性 / SQLAlchemy class hook）
class _FakeMat:
    def __init__(self, id_: int = 1):
        self.id = id_
        self.image = None


class _FakeResp:
    def __init__(self, status: int, is_redirect: bool = False,
                 location: str | None = None, body: bytes = b"",
                 content_type: str = "image/png"):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        if location:
            self.headers["Location"] = location
        self.is_redirect = is_redirect and status in (301, 302, 303, 307, 308)
        self.is_permanent_redirect = is_redirect and status in (301, 308)
        self._body = body
        self._closed = False
        self.ok = status < 400

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1):
        yield self._body

    def close(self):
        self._closed = True

    @property
    def raw(self):
        return io.BytesIO(self._body)


class TestRemoteImageSsrf(unittest.TestCase):
    def _run(self, build_responses, start_url="https://cdn.example.com/a.png",
             private_host_fn=None):
        """
        build_responses(next_url) 应返回 (status, redirect, location, body) 或
        返回 None 表示断言该 URL 不该被请求。

        private_host_fn(hostname) -> bool：若提供则用其覆盖 _is_private_or_loopback_host，
        默认：所有 hostname 使用真实判断（沙箱内可能 DNS 失败 = 保守拒绝）。
        本测试默认用一个「hostname 含 'example.com' 视为公网；IP 调用真实判断」的函数，
        以便让 SSRF 防护逻辑（在 redirect 目标上重新校验内网 IP）的路径真正被覆盖。
        """
        call_log = []

        def fake_get(url, **kwargs):
            call_log.append(url)
            resp = build_responses(url)
            if resp is None:
                raise AssertionError(f"未预期的请求 URL：{url}")
            status, redirect, location, body = resp
            return _FakeResp(status, redirect, location, body or _VALID_PNG_BYTES)

        if private_host_fn is None:
            # 默认：hostname 像域名（含字母且非纯十六进制 + 点号）的「example.com」公网域名
            # 判 False，其它委托真实实现。真实实现在沙箱 DNS 下会判未知域名 = True（保守），
            # 但我们要覆盖 redirect 里的 127.0.0.1 等真实 IP，所以 IP 走真实实现。
            real_fn = app_module._is_private_or_loopback_host
            def default_host_check(hostname):
                if hostname and isinstance(hostname, str):
                    if 'example.com' in hostname.lower():
                        return False
                    # 纯 IP：交给真实实现
                    if hostname.replace('.', '').replace(':', '').isdigit() or \
                       (':' in hostname and hostname.count(':') >= 2):
                        return real_fn(hostname)
                # 其它 unknown 域名：按公网处理（避免 DNS 失败影响）
                return False
            private_host_fn = default_host_check

        from unittest.mock import patch as _p
        with patch_get(fake_get), \
             _p.object(app_module, "_is_private_or_loopback_host", side_effect=private_host_fn):
            return app_module._save_material_image_from_url(_FakeMat(1), start_url), call_log

    def test_direct_ok(self):
        """T1：直连 200 图片成功。"""
        def responses(url):
            return (200, False, None, _VALID_PNG_BYTES)
        result, log = self._run(responses)
        path, err = result
        # 成功时函数返回 (path, '')，允许 None 或空字符串
        self.assertFalse(err, f"err={err!r}")
        self.assertIsNotNone(path)

    def test_redirect_127_0_0_1_rejected(self):
        """T2：302 跳 127.0.0.1 -> 拒绝。"""
        def responses(url):
            if url.startswith("https://cdn.example.com/"):
                return (302, True, "http://127.0.0.1/admin.png", None)
            return None
        result, log = self._run(responses)
        path, err = result
        self.assertIsNone(path)
        self.assertIn("内网地址", err)

    def test_redirect_metadata_rejected(self):
        """T3：302 跳 169.254.169.254（云元数据）-> 拒绝。"""
        def responses(url):
            if url.startswith("https://cdn.example.com/"):
                return (302, True, "http://169.254.169.254/latest/", None)
            return None
        result, log = self._run(responses)
        path, err = result
        self.assertIsNone(path)
        self.assertIn("内网地址", err)

    def test_redirect_public_public_ok(self):
        """T4：302 合法外网 -> 合法外网 跟随成功。"""
        def responses(url):
            if url.startswith("https://cdn.example.com/"):
                return (302, True, "https://cdn2.example.com/b.png", None)
            if url.startswith("https://cdn2.example.com/"):
                return (200, False, None, _VALID_PNG_BYTES)
            return None
        result, log = self._run(responses)
        path, err = result
        # 成功时函数返回 (path, '')，允许 None 或空字符串
        self.assertFalse(err, f"err={err!r}")
        self.assertIsNotNone(path)

    def test_too_many_redirects_rejected(self):
        """T5：6 跳（超过上限 5）拒绝。"""
        urls = [f"https://s{i}.example.com/r" for i in range(7)]
        def responses(url):
            # 初始 URL=s0 -> s1, s1->s2, s2->s3, s3->s4, s4->s5, s5->s6, s6->200
            # 实际重定向数：s0->s1(1) s1->s2(2) s2->s3(3) s3->s4(4) s4->s5(5) s5->s6(6) -> 超过
            for i, u in enumerate(urls[:-1]):
                if url.startswith(u.split("?")[0]):
                    return (302, True, urls[i+1], None)
            return (200, False, None, _VALID_PNG_BYTES)
        # 所有 sX.example.com 视为公网
        def host_check(hostname):
            if hostname and 'example.com' in hostname.lower():
                return False
            return app_module._is_private_or_loopback_host(hostname)
        res, log = self._run(responses, start_url=urls[0], private_host_fn=host_check)
        path, err = res
        self.assertIsNone(path)
        self.assertIn("重定向次数过多", err)

    def test_missing_location_rejected(self):
        """T6：302 但 Location 缺失 -> 拒绝。"""
        def responses(url):
            return (302, True, None, None)
        result, log = self._run(responses)
        path, err = result
        self.assertIsNone(path)
        self.assertIn("缺失", err)

    def test_redirect_file_scheme_rejected(self):
        """T7：302 跳 file:// 协议拒绝。"""
        def responses(url):
            if url.startswith("https://cdn.example.com/"):
                return (302, True, "file:///etc/passwd", None)
            return None
        result, log = self._run(responses)
        path, err = result
        self.assertIsNone(path)
        self.assertIn("不允许", err)

    def test_source_no_malformed_kwargs(self):
        """T8：源码静态——删除 max_redirects=，且使用 allow_redirects=False。"""
        src = inspect.getsource(app_module._save_material_image_from_url)
        self.assertNotIn("max_redirects=", src)
        self.assertIn("allow_redirects=False", src)


def patch_get(fn):
    import app
    from unittest.mock import patch as _p
    return _p.object(app.requests, "get", side_effect=fn)


if __name__ == "__main__":
    unittest.main(verbosity=2)
