"""阶段1：导航与帮助工具模块。

从 app.py 中抽离的导航相关函数：
- skill_catalog: AI技能清单
- system_api_catalog: 系统API清单
- usage_help: 使用帮助
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def skill_catalog() -> list[dict[str, str]]:
    """AI技能清单。

    Returns:
        技能列表，每项包含 name/description/category
    """
    from app.ai.tools.registry import get_all_tools

    skills = []
    for tool in get_all_tools():
        skills.append({
            'name': tool.get('name', ''),
            'description': tool.get('description', ''),
            'category': tool.get('category', 'general'),
        })

    return skills


def system_api_catalog() -> list[dict[str, str]]:
    """系统API清单。

    Returns:
        API路由列表，每项包含 method/rule/endpoint
    """
    from flask import current_app

    routes = []
    try:
        for rule in current_app.url_map.iter_rules():
            if rule.endpoint.startswith('static'):
                continue
            methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
            routes.append({
                'method': methods,
                'rule': rule.rule,
                'endpoint': rule.endpoint,
            })
    except Exception as exc:
        logger.warning('system_api_catalog failed: %s', exc)

    routes.sort(key=lambda x: x['rule'])
    return routes


def usage_help(topic: str = '') -> dict[str, str]:
    """使用帮助。

    Args:
        topic: 帮助主题（可选）

    Returns:
        包含 title/content/steps 的字典
    """
    help_content = {
        'title': 'WMS系统使用帮助',
        'content': '欢迎使用仓库管理系统AI助手。我可以帮你：',
        'steps': [
            '查询物料库存和流水',
            '生成领料单/入库单/调拨单草稿',
            '分析库存健康和采购情况',
            '识别送货单并生成入库草稿',
            '解答系统操作问题',
        ],
    }

    if topic:
        help_content['title'] = f'关于「{topic}」的帮助'
        help_content['content'] = f'以下是关于「{topic}」的操作指引：'

    return help_content
