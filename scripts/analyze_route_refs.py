# -*- coding: utf-8 -*-
"""审查 app.py 拆分后遗症：核对模板 url_for 端点 与 JS 请求路径是否都能命中注册路由。
- 模板 url_for('endpoint', ...) 静态端点若不在 url_map 会抛 BuildError
- JS 里硬编码的相对 URL 若不在 url_map 会 404
只报告有证据的高置信缺失。"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"

os.chdir(APP_DIR)
sys.path.insert(0, str(APP_DIR))
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"

url_for_re = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
# 静态 JS 里的相对请求路径（排除 http 外部、static、模板变量）
js_url_re = re.compile(r"['\"]\s*(/[a-zA-Z][a-zA-Z0-9_/<>:\-\.]*)\s*['\"]")

from app import app  # noqa: E402

endpoints = {r.endpoint for r in app.url_map.iter_rules()}
rules = [r.rule for r in app.url_map.iter_rules()]

# 忽略的动态/变量端点白名单
IGNORE_EP = {
    "static",
    "auth.login",
    "login",
    "native_api_login",
    "logout",
    "change_password",
    "index",
    "dashboard",
    "user_avatar",
    "favicon",
}


def rule_matches_url(url):
    """URL 是否匹配某条 rule（去掉 <vars> 后做前缀/等值判断）。"""
    if url in rules:
        return True
    # 尝试把 <int:...> 替换
    stripped = re.sub(r"<[^>]+>", "1", url)
    for r in rules:
        r_stripped = re.sub(r"<[^>]+>", "1", r)
        if stripped == r_stripped:
            return True
    # 前缀宽松匹配（/api/ai/xxx 泛化）
    for r in rules:
        if r in url and r.endswith("/"):
            return True
    return False


def main():
    print("[INFO] endpoints:", len(endpoints), "rules:", len(rules))
    missing_ep = []
    for tpl in sorted((APP_DIR / "templates").rglob("*.html")):
        text = tpl.read_text(encoding="utf-8", errors="ignore")
        for m in url_for_re.finditer(text):
            ep = m.group(1)
            if ep in IGNORE_EP or ep.startswith("ai.") or ep.startswith("v2."):
                continue
            if ep not in endpoints:
                line = text[: m.start()].count("\n") + 1
                missing_ep.append((str(tpl.relative_to(APP_DIR)), line, ep))

    missing_js = []
    for js in sorted((APP_DIR / "static" / "js").rglob("*.js")):
        text = js.read_text(encoding="utf-8", errors="ignore")
        for m in js_url_re.finditer(text):
            url = m.group(1)
            if url.startswith("/static/") or url == "/" or url.startswith("/api/"):
                continue
            if "<" in url:
                continue
            if not rule_matches_url(url):
                line = text[: m.start()].count("\n") + 1
                missing_js.append((str(js.relative_to(APP_DIR)), line, url))

    print("\n=== 模板 url_for 缺失端点（BuildError 风险）===")
    if not missing_ep:
        print("  无")
    for f, line, ep in missing_ep:
        print(f"  {f}:{line}  url_for('{ep}')")

    print("\n=== JS 硬编码路径未命中路由（404 风险）===")
    if not missing_js:
        print("  无")
    for f, line, url in missing_js:
        print(f"  {f}:{line}  '{url}'")


if __name__ == "__main__":
    sys.exit(main())