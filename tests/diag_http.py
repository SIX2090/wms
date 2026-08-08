# -*- coding: utf-8 -*-
"""临时诊断（用完即删）：对真实 HTTP 服务(127.0.0.1:8080) 实测下推流程耗时。"""
from __future__ import annotations

import re
import time
import urllib.parse
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE = "http://127.0.0.1:8080"
opener = build_opener(HTTPCookieProcessor(CookieJar()))


def _t(method, url, data=None, label=""):
    body = None
    headers = {}
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = Request(BASE + url, data=body, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        resp = opener.open(req, timeout=60)
        content = resp.read()
        code = resp.status
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", "ERR")
        content = b""
    ms = (time.perf_counter() - t0) * 1000
    print(f"[DIAG] {label:<32} {ms:>7.0f} ms  http={code}")
    return code, content


if __name__ == "__main__":
    code, html = _t("GET", "/login", label="GET /login")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html.decode("utf-8", "ignore"))
    token = m.group(1) if m else ""
    _t("POST", "/login",
       {"username": "admin", "password": "admin", "csrf_token": token},
       label="POST /login")
    _t("GET", "/in_order/2", label="GET /in_order/2 (来源详情)")
    _t("GET", "/in_order/2/push", label="GET /in_order/2/push (下推页)")
    _t("GET", "/out_order/2", label="GET /out_order/2 (领料详情)")