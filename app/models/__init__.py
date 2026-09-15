#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模型包（ARCH-MODELS-01，2026-09-15）。

从 app/app.py 的 90 个模型类中迁出 64 个核心业务模型，按域分模块：
- core.py: 用户 / 认证 / 审计 / 系统配置
- master_data.py: 主数据（物料 / 供应商 / 客户 / 仓库 / 部门 / 合同…）
- print.py: 打印域
- documents.py: 出入库及业务单据
- inventory.py: 库存事实
- wechat.py: 微信分享

AI 相关 26 个模型仍留守 app/app.py，待 ARCH-MODELS-02 迁入 ai.py。
app.py 以 ``from models import (...)`` 门面导入，保持全部既有调用点不变。
"""

from models.core import *  # noqa: F401,F403
from models.master_data import *  # noqa: F401,F403
from models.print import *  # noqa: F401,F403
from models.documents import *  # noqa: F401,F403
from models.inventory import *  # noqa: F401,F403
from models.wechat import *  # noqa: F401,F403
