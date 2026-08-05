# -*- coding: utf-8 -*-
"""pytest 会话级环境固定。

根因（BUG-2026-08-05-002）：pytest 按字母序收集测试模块时，
test_get_default_warehouse.py 等先于 test_material_delete_missing_ai_table.py
导入 app 模块且未设置 DATABASE_URL，app 被缓存为文件库配置；
后续模块再设置内存库 env 已无效，guarded_drop_all 拒绝 drop_all。

conftest.py 先于一切测试模块导入，在此固定内存库环境，
使 app 首次导入即使用 sqlite:///:memory:，与导入顺序无关。
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
