#!/usr/bin/env python3
"""Apply BUG-001 and BUG-002 fix to app.py."""
import io
import sys

PATH = r"C:\Users\Administrator\Desktop\wms\app\app.py"

with io.open(PATH, "r", encoding="utf-8") as f:
    text = f.read()

old = (
    "    if wants_json_error_response():\n"
    "        return jsonify({'status': 'error', 'msg': '请求的资源不存在'}), 404\n"
    "    _404_path = os.path.join(app.template_folder, '404.html')\n"
    "    return render_template('404.html') if os.path.exists(_404_path) else ('页面不存在', 404)\n"
    "\n"
    "@app.errorhandler(CSRFError)"
)

new = (
    "    if wants_json_error_response():\n"
    "        return jsonify({'status': 'error', 'msg': '请求的资源不存在'}), 404\n"
    "    return render_template('404.html'), 404\n"
    "\n"
    "@app.errorhandler(405)\n"
    "def method_not_allowed(e):\n"
    "    \"\"\"405错误处理\"\"\"\n"
    "    if wants_json_error_response():\n"
    "        return jsonify({'status': 'error', 'msg': '请求方式不被允许'}), 405\n"
    "    return render_template('405.html'), 405\n"
    "\n"
    "@app.errorhandler(CSRFError)"
)

if old not in text:
    idx = text.find("页面不存在")
    print("OLD block NOT FOUND. 页面不存在 at index:", idx)
    if idx >= 0:
        print(repr(text[max(0, idx-100):idx+50]))
    sys.exit(1)

count = text.count(old)
print("Found old block", count, "time(s)")
text = text.replace(old, new)

with io.open(PATH, "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("OK: file updated")
