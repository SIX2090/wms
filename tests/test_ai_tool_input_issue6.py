"""Issue #6: rejected input must never reach a business handler."""
from unittest.mock import Mock, patch
import json

import pytest
import app as app_module
from ai.orchestrator import dispatch_registered_tool
from ai.query_tools import AI_QUERY_TOOLS, AI_QUERY_TOOLS_PROMPT, validate_tool_call
from ai.schemas import validate_json_schema_payload


@pytest.mark.parametrize('quantity', [True, False, -1, -0.01, 1_000_000_001, float('nan'), float('inf'), -float('inf'), '2', [], {}])
def test_query_quantity_rejected_before_handler(quantity):
    payload = {'tool': 'check_sufficiency', 'params': {'material_name': 'copper', 'required_qty': quantity}}
    assert validate_tool_call(payload)[0] is None
    _assert_rejected_dispatch(payload)


@pytest.mark.parametrize('payload', [
    [], False, 0, '', None,
    {'tool': 'unknown', 'params': {}},
    {'tool': [], 'params': {}},
    {'tool': 'query_stock', 'params': []},
    {'tool': 'query_stock', 'params': False},
    {'tool': 'query_stock', 'params': {'material_name': 'copper', 'extra': 1}},
    {'tool': 'query_flow', 'params': {'material_name': 'copper', 'extra': 1}},
    {'tool': 'check_sufficiency', 'params': {'material_name': 'copper', 'extra': 1}},
    {'tool': 'query_stock', 'params': {'material_name': 'copper'}, 'extra': 1},
    {'tool': 'query_stock', 'params': {'material_name': '  '}},
])
def test_invalid_query_never_calls_handler(payload):
    assert validate_tool_call(payload)[0] is None
    _assert_rejected_dispatch(payload)


def _assert_rejected_dispatch(payload):
    with patch.object(app_module, '_ai_capability_allowed', return_value=True), \
         patch.object(app_module, '_voice_llm_chat', return_value=json.dumps(payload)), \
         patch('ai.query_memory.memory_examples_text', return_value=''), \
         patch('ai.query_memory.record_query_memory') as memory, \
         patch.object(app_module, '_ai_stock_query_response') as stock, \
         patch.object(app_module, '_ai_flow_query_response') as flow:
        assert app_module._ai_tool_call_dispatch_response('check copper stock') is None
    stock.assert_not_called()
    flow.assert_not_called()
    memory.assert_not_called()


@pytest.mark.parametrize('quantity', [0, 0.01, 1, 1_000_000_000, None])
def test_query_quantity_boundaries_and_optional_null(quantity):
    payload = {'tool': 'check_sufficiency', 'params': {'material_name': 'copper', 'required_qty': quantity}}
    assert validate_tool_call(payload) == ('check_sufficiency', payload['params'])
    with patch.object(app_module, '_ai_capability_allowed', return_value=True), \
         patch.object(app_module, '_voice_llm_chat', return_value=json.dumps(payload)), \
         patch('ai.query_memory.memory_examples_text', return_value=''), \
         patch('ai.query_memory.record_query_memory'), \
         patch.object(app_module, '_ai_stock_query_response', return_value='ok') as handler:
        assert app_module._ai_tool_call_dispatch_response('check copper stock') == 'ok'
    handler.assert_called_once()
    if quantity is not None:
        assert f'需要数量：{quantity}' in handler.call_args.args[0]


def test_query_optional_strings_keep_null_compatibility():
    params = {'material_name': 'copper', 'spec': None, 'color': '', 'brand': None}
    assert validate_tool_call({'tool': 'query_stock', 'params': params}) == ('query_stock', params)


@pytest.mark.parametrize('context', [False, 0, '', [], [1], True, 1, 'bad', {'unexpected': 1}, {'limit': True}, {'limit': 0}])
def test_orchestrator_invalid_context_never_calls_handler(context):
    handler = Mock(__name__='_ai_warehouse_insights_response')
    assert dispatch_registered_tool('warehouse_insights', 'query', context, {'warehouse_insights': handler}) is None
    handler.assert_not_called()


@pytest.mark.parametrize('context', [None, {}, {'limit': 1}])
def test_orchestrator_validates_exact_executed_object(context):
    handler = Mock(__name__='_ai_warehouse_insights_response', return_value='ok')
    from ai.tools.registry import validate_ai_tool_input
    with patch('ai.orchestrator.validate_ai_tool_input', wraps=validate_ai_tool_input) as validate:
        assert dispatch_registered_tool('warehouse_insights', 'query', context, {'warehouse_insights': handler}) == 'ok'
    executed = handler.call_args.args[1]
    assert executed is validate.call_args.args[1]
    assert executed == ({} if context is None else context)
    if context is not None:
        assert executed is context


@pytest.mark.parametrize('name', ['unknown', None, [], {}])
def test_orchestrator_unknown_or_invalid_name_never_calls_handler(name):
    handler = Mock(__name__='_ai_warehouse_insights_response')
    assert dispatch_registered_tool(name, 'query', {}, {'unknown': handler, 'warehouse_insights': handler}) is None
    handler.assert_not_called()


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_shared_schema_rejects_non_json_numbers(value):
    assert not validate_json_schema_payload({'type': 'number', 'minimum': 0}, value).valid


def test_query_permission_denial_skips_llm_and_handlers():
    with patch.object(app_module, '_ai_capability_allowed', return_value=False), \
         patch.object(app_module, '_voice_llm_chat') as llm, \
         patch.object(app_module, '_ai_stock_query_response') as handler:
        assert app_module._ai_tool_call_dispatch_response('check copper stock') is None
    llm.assert_not_called()
    handler.assert_not_called()


def test_orchestrator_confirmation_still_required():
    handler = Mock(__name__='draft_handler')
    assert dispatch_registered_tool('out_order_draft', 'query', {'warehouse_id': 1, 'items': [{'material_id': 1, 'quantity': 1}]}, {'out_order_draft': handler}) is None
    handler.assert_not_called()


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_registered_draft_nonfinite_quantity_never_calls_handler(value):
    handler = Mock(__name__='draft_handler')
    payload = {'warehouse_id': 1, 'items': [{'material_id': 1, 'quantity': value}]}
    assert dispatch_registered_tool('out_order_draft', 'query', payload, {'out_order_draft': handler}, manual_confirmation=True) is None
    handler.assert_not_called()


def test_orchestrator_handler_mismatch_never_calls_handler():
    handler = Mock(__name__='wrong_handler')
    assert dispatch_registered_tool('warehouse_insights', 'query', {}, {'warehouse_insights': handler}) is None
    handler.assert_not_called()


def test_prompt_exposes_the_validated_schemas():
    for spec in AI_QUERY_TOOLS.values():
        assert json.dumps(spec['input_schema'], ensure_ascii=False) in AI_QUERY_TOOLS_PROMPT
