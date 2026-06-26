#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模型导出模块
从app.py导出所有数据库模型和db实例
"""

# 为了避免循环导入，只在需要时从 app 导入
# 其他模块应该直接从 app 导入需要的类

# 导出 db 实例
from app import db
