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

# BUG-2026-08-07-002：pytest 全量跑时 3 个 golden 测试收集报
# "'app' is not a package"。根因：其他测试模块先 sys.path.insert(APP_DIR)
# 并 `import app`（命中 app/app.py 模块，无 __path__），此后
# `from app.fix_db_columns import ...` / `from app.ai... import ...`
# 包语义导入失败。单跑时 /workspace 在 sys.path，app 以 namespace 包
# 加载故可过——结果依赖导入顺序，属测试隔离缺陷。
#
# 修复：conftest 抢先以模块语义导入 app（与所有业务测试一致），
# 再补 __path__ 指向 APP_DIR，使 `import app.ai.xxx` /
# `import app.fix_db_columns` 也能沿该路径解析，两种语义共存。
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = _ROOT / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import app as _wms_app  # noqa: E402

if not hasattr(_wms_app, "__path__"):
    _wms_app.__path__ = [str(_APP_DIR)]
