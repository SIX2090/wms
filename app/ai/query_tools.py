# -*- coding: utf-8 -*-
"""WMS AI 助手 Tool 注册表（阶段二：Tool Calling + 结构化 JSON 输出）。

依据：开源 WMS/ERP AI 助手调研（OdooPilot / Spring AI @Tool / SAP WM MCP /
ERPNext Copilot）——把现有查询逻辑封装为带描述的 Tool，LLM 输出结构化
调用意图 {"tool": "...", "params": {...}}，应用层校验后执行。

设计约束（AGENTS.md / 开发计划阶段二）：
- 只读：AI 助手仅提供查询类工具，不开放创建/修改单据（写操作留二期确认门控）
- 校验：tool 名必须在注册表内，参数使用统一 JSON Schema 校验，非法输出回退机械路径
- 复用：工具实现直接指向 app 层已验证的现有函数，不重写查询逻辑
"""

from __future__ import annotations

import json

from ai.schemas import validate_json_schema_payload
from ai.tools.registry import NON_NEGATIVE_QUANTITY


_OPTIONAL_TEXT = {'type': ['string', 'null']}


def _query_schema(properties):
    return {
        'type': 'object',
        'additionalProperties': False,
        'required': ['material_name'],
        'properties': {
            'material_name': {'type': 'string', 'minLength': 1, 'pattern': r'[\s\S]*\S[\s\S]*'},
            **properties,
        },
    }

# ---------------------------------------------------------------------------
# Tool 定义（描述供 LLM 理解何时选择该工具及如何填参）
# ---------------------------------------------------------------------------
AI_QUERY_TOOLS = {
    'query_stock': {
        'description': (
            '查询物料当前库存。适用：用户问某物料的库存/存量/还有多少/'
            '有没有货/剩多少。params: {"material_name": 物料名称(必填，如"铜排"), '
            '"spec": 规格型号(可选，如"6*10"), "color": 颜色(可选), '
            '"brand": 品牌(可选)}'
        ),
        'handler': '_ai_stock_query_response',
        'input_schema': _query_schema({'spec': _OPTIONAL_TEXT, 'color': _OPTIONAL_TEXT, 'brand': _OPTIONAL_TEXT}),
    },
    'query_flow': {
        'description': (
            '查询物料出入库流水。适用：用户问某物料最近/某段时间进了多少、'
            '出库多少、用了多少、领了多少、流水明细、几笔记录。'
            'params: {"material_name": 物料名称(必填), "time_range": 时间范围'
            '(可选，如"最近7天/今天/昨天/本周/上周/本月/上月")}'
        ),
        'handler': '_ai_flow_query_response',
        'input_schema': _query_schema({'time_range': _OPTIONAL_TEXT}),
    },
    'check_sufficiency': {
        'description': (
            '判断物料库存够不够用。适用：用户问某物料"够不够用/还够吗/'
            '能不能撑到月底"。params: {"material_name": 物料名称(必填), '
            '"required_qty": 需要数量(可选数字)}'
        ),
        'handler': '_ai_stock_query_response',
        'input_schema': _query_schema({
            'required_qty': {**NON_NEGATIVE_QUANTITY, 'type': ['number', 'null']},
        }),
    },
}

# LLM 可见的工具清单文本（注入 prompt）
AI_QUERY_TOOLS_PROMPT = '\n'.join(
    f"- {name}: {spec['description']}\n  JSON Schema: {json.dumps(spec['input_schema'], ensure_ascii=False)}"
    for name, spec in AI_QUERY_TOOLS.items()
)


def validate_tool_call(data):
    """校验 LLM 输出的工具调用结构。

    返回 (tool_name, params) 或 (None, error_reason)。只做结构校验，
    不做业务查询；业务匹配仍由现有函数完成。
    """
    if not isinstance(data, dict):
        return None, '输出不是 JSON 对象'
    tool_name = data.get('tool')
    if not tool_name or not isinstance(tool_name, str):
        return None, '缺少 tool 字段'
    spec = AI_QUERY_TOOLS.get(tool_name)
    if spec is None:
        return None, f'未知工具: {tool_name}'
    envelope = validate_json_schema_payload({
        'type': 'object',
        'additionalProperties': False,
        'properties': {'tool': {'type': 'string'}, 'params': {'type': ['object', 'null']}},
    }, data)
    if not envelope.valid:
        return None, '调用结构错误: ' + '; '.join(envelope.errors)
    params = data.get('params')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return None, 'params 不是对象'
    # 必填参数
    for key in spec['input_schema']['required']:
        val = params.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            return None, f'缺少必填参数 {key}'
    validation = validate_json_schema_payload(spec['input_schema'], params)
    if not validation.valid:
        return None, '参数类型或取值错误: ' + '; '.join(validation.errors)
    return tool_name, params


def build_tool_call_prompt(message, memory_text=''):
    """构建让 LLM 选择工具并填参的 prompt（含 Schema 摘要与工具清单）。

    memory_text：P4 查询记忆注入的 few-shot 示例（可为空串）。
    """
    from ai.schema_meta import get_schema_meta
    memory_block = f'\n{memory_text}\n' if memory_text else ''
    return f"""你是 WMS 仓库管理系统的查询调度器。根据用户问题选择一个工具并提取参数。

【系统数据说明】
{get_schema_meta('all')}
{memory_block}
【可用工具】
{AI_QUERY_TOOLS_PROMPT}

【用户问题】
{message}

【输出要求】
只输出 JSON，不要其他内容，格式：
{{"tool": "工具名", "params": {{"参数名": "值"}}}}
如果用户问题不属于任何工具（如闲聊、写操作请求），输出：
{{"tool": "none"}}"""
