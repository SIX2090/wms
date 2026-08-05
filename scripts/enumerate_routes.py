#!/usr/bin/env python3
"""枚举 WMS 全部路由（method + path + endpoint），导出 JSON 供按钮端点测试使用。"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))
# 直接读取 run_server 的启动方式，导入 app 对象
import app as appmod
from app import app

rules = []
for rule in app.url_map.iter_rules():
    if rule.rule.startswith('/static'):
        continue
    rules.append({
        'path': rule.rule,
        'methods': sorted(rule.methods - {'HEAD', 'OPTIONS'}),
        'endpoint': rule.endpoint,
    })
out = os.path.join(os.path.dirname(__file__), '_routes.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(rules, f, ensure_ascii=False, indent=1)
print(f'共 {len(rules)} 条路由 -> {out}')
get = [r for r in rules if 'GET' in r['methods']]
post = [r for r in rules if 'POST' in r['methods']]
print(f'GET: {len(get)}, POST: {len(post)}')