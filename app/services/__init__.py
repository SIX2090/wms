# -*- coding: utf-8 -*-
# services 包：业务服务层（P2-3 库存三账写入收敛首发）。
# 生产布局下 app/ 目录即 sys.path 包根（app.py 为顶层模块），
# 本包以顶级包 `services` 导入（与 routes/models 平级），
# 禁止 `from app.services ...`（BUG-2026-09-06-003：app 非包，必然 ModuleNotFoundError）。
