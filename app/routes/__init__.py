#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务路由 Blueprint 包。

将 app.py 中按业务域拆分的路由迁移到本包，每个业务域一个模块（如 unit.py）。
所有模块只依赖 flask / db / utils 等稳定模块，需要 app.py 内部定义时
在函数内部延迟导入（from app import ...），避免循环导入（参考 ai/routes.py 模式）。
"""