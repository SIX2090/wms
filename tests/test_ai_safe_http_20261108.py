"""Offline redirect tests: no application import, database, or real network."""
import ast
import base64
import importlib.util
import json
import socket
import sqlite3
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path

import pytest
import requests
from flask import Flask, jsonify, request

_prior_sys_path = sys.path[:]
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
    from ai import providers, safe_http
    from ai.ops import fallback
    from ai.ops.fallback import FallbackChain, FallbackLevel
    import tencent_asr
finally:
    sys.path[:] = _prior_sys_path
    del _prior_sys_path


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('external IO forbidden')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)


class MemoryAdapter(requests.adapters.BaseAdapter):
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.options = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        self.options.append(kwargs)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        status, headers, body = result
        response = requests.Response()
        response.status_code = status
        response.headers.update(headers)
        response._content = body
        response._content_consumed = True
        response.url = request.url
        response.request = request
        return response

    def close(self):
        pass


def transport(monkeypatch, responses):
    session = requests.Session()
    session.trust_env = False
    adapter = MemoryAdapter(responses)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    monkeypatch.setattr(requests, 'post', session.post)
    return adapter


def test_collection_preserves_path_and_external_io_functions():
    original_path = sys.path[:]
    original_functions = (socket.socket.connect, socket.socket.connect_ex,
                          socket.getaddrinfo, sqlite3.connect, subprocess.Popen)
    spec = importlib.util.spec_from_file_location('synthetic_ai_redirect_collection', __file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert sys.path == original_path
    assert (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo,
            sqlite3.connect, subprocess.Popen) == original_functions


@pytest.mark.parametrize('status', [301, 302, 303, 307, 308])
@pytest.mark.parametrize('target', [
    'https://other.invalid/path', 'http://api.invalid/path',
    'https://api.invalid:444/path', '//other.invalid/path',
    'https://api.invalid@other.invalid/path',
])
def test_cross_origin_never_receives_sensitive_body(monkeypatch, status, target):
    adapter = transport(monkeypatch, [(status, {'Location': target}, b'')])
    with pytest.raises(safe_http.UnsafeRedirect, match='已停止') as caught:
        safe_http.post('https://api.invalid/start',
                       headers={'Authorization': 'Bearer synthetic', 'X-Token': 'synthetic'},
                       json={'data': 'synthetic-private-content'})
    assert len(adapter.requests) == 1
    assert 'synthetic' not in str(caught.value)


@pytest.mark.parametrize('status', [307, 308])
def test_same_origin_multihop_preserves_body(monkeypatch, status):
    adapter = transport(monkeypatch, [
        (status, {'Location': '/first'}, b''),
        (status, {'Location': 'https://api.invalid:443/final'}, b''),
        (200, {}, b'{}'),
    ])
    response = safe_http.post('https://api.invalid/start',
                              headers={'Authorization': 'Bearer synthetic'},
                              json={'data': 'synthetic'})
    assert response.status_code == 200
    assert len(adapter.requests) == 3
    assert all(req.method == 'POST' and req.body == adapter.requests[0].body for req in adapter.requests)
    assert all(req.headers['Authorization'] == 'Bearer synthetic' for req in adapter.requests)


@pytest.mark.parametrize('status', [301, 302, 303])
def test_same_origin_other_redirects_keep_requests_method_semantics(monkeypatch, status):
    adapter = transport(monkeypatch, [(status, {'Location': '/next'}, b''), (200, {}, b'{}')])
    assert safe_http.post('https://api.invalid/start', json={'data': 'synthetic'}).status_code == 200
    assert [request.method for request in adapter.requests] == ['POST', 'GET']
    assert adapter.requests[1].body is None


@pytest.mark.parametrize('url, location', [
    ('https://[::1]/start', 'https://[::1]:443/next'),
    ('https://api.invalid/start', '//API.INVALID:443/next'),
    ('https://例子.invalid/start', '/next'),
])
def test_same_origin_normalization(monkeypatch, url, location):
    adapter = transport(monkeypatch, [(307, {'Location': location}, b''), (200, {}, b'{}')])
    assert safe_http.post(url, json={'data': 'synthetic'}).status_code == 200
    assert len(adapter.requests) == 2


def test_baseline_requests_would_replay_body_cross_origin(monkeypatch):
    adapter = transport(monkeypatch, [(307, {'Location': 'https://other.invalid/'}, b''), (200, {}, b'{}')])
    requests.post('https://api.invalid/start', headers={'X-Token': 'synthetic'}, json={'data': 'synthetic'})
    assert len(adapter.requests) == 2
    assert adapter.requests[1].body == adapter.requests[0].body
    assert adapter.requests[1].headers['X-Token'] == 'synthetic'


def test_second_hop_cross_origin_stops_before_replay(monkeypatch):
    adapter = transport(monkeypatch, [(307, {'Location': '/first'}, b''),
                                     (308, {'Location': 'https://other.invalid/'}, b'')])
    with pytest.raises(safe_http.UnsafeRedirect):
        safe_http.post('https://api.invalid/start', json={'data': 'synthetic'})
    assert len(adapter.requests) == 2


def test_provider_redirect_is_nonretryable(monkeypatch, caplog):
    adapter = transport(monkeypatch, [(307, {'Location': 'https://other.invalid/'}, b'')])
    breaker = providers.CircuitBreaker()
    monkeypatch.setattr(providers, 'get_breaker', lambda mode: breaker)
    monkeypatch.setattr(providers.time, 'sleep', lambda seconds: pytest.fail('must not retry'))
    config = providers.OpenAICompatibleConfig(True, 'https://api.invalid/chat', 'model', 'synthetic-key', 10, 100)
    with pytest.raises(providers.LLMCallError) as caught:
        providers.call_llm(config, [{'role': 'user', 'content': 'synthetic-private'}])
    assert not caught.value.retryable
    assert len(adapter.requests) == 1
    assert breaker.stats['failures'] == 1
    assert 'synthetic-key' not in caplog.text and 'synthetic-private' not in caplog.text


def test_provider_security_stop_skips_secondary_and_uses_local(monkeypatch):
    adapter = transport(monkeypatch, [(307, {'Location': 'https://other.invalid/'}, b'')])
    monkeypatch.setattr(providers, 'get_breaker', lambda mode: providers.CircuitBreaker())
    monkeypatch.setattr(providers.time, 'sleep', lambda seconds: pytest.fail('must not retry'))
    chain = FallbackChain()
    chain.set_primary(providers.OpenAICompatibleConfig(True, 'https://api.invalid/chat', 'one', 'synthetic-key', 10, 100))
    chain.set_secondary(providers.OpenAICompatibleConfig(True, 'https://other-provider.invalid/chat', 'two', 'synthetic-key', 10, 100))
    chain.set_local_handler(lambda messages: 'local result')
    assert chain.execute([{'role': 'user', 'content': 'synthetic'}]) == ('local result', FallbackLevel.LOCAL_RULES)
    assert len(adapter.requests) == 1
    assert chain.get_stats()['primary_failure'] == 1
    assert chain.get_stats()['secondary_success'] == 0


@pytest.mark.parametrize('route_name', ['v2_llm_chat', 'v2_llm_intent'])
def test_v2_redirect_returns_controlled_error_without_remote_retry(monkeypatch, route_name):
    adapter = transport(monkeypatch, [(307, {'Location': 'https://other.invalid/'}, b'')])
    monkeypatch.setattr(providers, 'get_breaker', lambda mode: providers.CircuitBreaker())
    monkeypatch.setattr(providers.time, 'sleep', lambda seconds: pytest.fail('must not retry'))
    config = providers.OpenAICompatibleConfig(True, 'https://api.invalid/chat', 'model', 'synthetic-key', 10, 100)
    source = (Path(__file__).resolve().parents[1] / 'app/ai/v2_routes.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    route = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == route_name)
    route.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[route], type_ignores=[]))
    env = {
        'request': request, 'jsonify': jsonify, '_get_llm_config': lambda: config,
        '_resolve_debug_system_prompt': lambda payload, default: default,
        'call_llm_chat': providers.call_llm_chat, 'call_llm_intent': providers.call_llm_intent,
        'UnsafeLLMRedirect': providers.UnsafeLLMRedirect,
    }
    exec(compile(module, '<synthetic-v2-route>', 'exec'), env)
    app = Flask('synthetic-v2-route')
    with app.test_request_context('/', method='POST', json={'message': 'synthetic'}):
        response, status = env[route_name]()
        assert status == 502
        assert response.get_json()['status'] == 'error'
        assert '重定向' in response.get_json()['msg']
        with pytest.raises(safe_http.UnsafeRedirect):
            safe_http.post('https://api.invalid/fallback', json={'data': 'synthetic'})
    assert len(adapter.requests) == 1


def test_provider_vision_redirect_returns_error_and_releases_semaphore(monkeypatch):
    adapter = transport(monkeypatch, [(307, {'Location': 'https://other.invalid/'}, b'')])
    monkeypatch.setattr(providers, 'get_breaker', lambda mode: providers.CircuitBreaker())
    monkeypatch.setattr(providers.time, 'sleep', lambda seconds: pytest.fail('must not retry'))
    config = providers.OpenAICompatibleConfig(True, 'https://api.invalid/chat', 'model', 'synthetic-key', 10, 100, vision_enabled=True)
    app = Flask('synthetic-vision-route')
    with app.test_request_context('/'):
        reply, extracted, error = providers.call_llm_vision(config, 'synthetic', [])
        assert reply is None and extracted is None and '重定向' in error
        with pytest.raises(safe_http.UnsafeRedirect):
            safe_http.post('https://api.invalid/fallback', json={'data': 'synthetic'})
    assert len(adapter.requests) == 1
    acquired = 0
    try:
        for _ in range(2):
            assert providers._vision_semaphore.acquire(blocking=False)
            acquired += 1
    finally:
        for _ in range(acquired):
            providers._vision_semaphore.release()


def test_normal_provider_error_still_uses_secondary(monkeypatch):
    calls = []
    def fake_call(config, *args, **kwargs):
        calls.append(config.model)
        if len(calls) == 1:
            raise providers.LLMCallError('synthetic failure', retryable=False)
        return 'secondary result'
    monkeypatch.setattr(fallback, 'call_llm', fake_call)
    chain = FallbackChain()
    chain.set_primary(providers.OpenAICompatibleConfig(True, 'https://api.invalid/chat', 'one', 'synthetic', 10, 100))
    chain.set_secondary(providers.OpenAICompatibleConfig(True, 'https://api.invalid/chat', 'two', 'synthetic', 10, 100))
    assert chain.execute([{'role': 'user', 'content': 'synthetic'}]) == ('secondary result', FallbackLevel.SECONDARY)
    assert calls == ['one', 'two']


def test_request_security_stop_blocks_later_remote_fallback_only_in_same_request(monkeypatch):
    adapter = transport(monkeypatch, [(307, {'Location': 'https://other.invalid/'}, b''), (200, {}, b'{}')])
    synthetic_app = Flask('isolated-redirect-test')
    with synthetic_app.app_context():
        with synthetic_app.test_request_context('/'):
            with pytest.raises(safe_http.UnsafeRedirect):
                safe_http.post('https://api.invalid/start', json={'data': 'synthetic'})
            with pytest.raises(safe_http.UnsafeRedirect):
                safe_http.post('https://api.invalid/fallback', json={'data': 'synthetic'})
            assert len(adapter.requests) == 1
        with synthetic_app.test_request_context('/'):
            assert safe_http.post('https://api.invalid/new-request', json={'data': 'synthetic'}).status_code == 200
            assert len(adapter.requests) == 2


@pytest.mark.parametrize('first_status', [400, 429])
def test_provider_existing_fallbacks(monkeypatch, first_status):
    body = json.dumps({'choices': [{'message': {'content': 'synthetic reply'}}]}).encode()
    adapter = transport(monkeypatch, [(first_status, {}, b'{}'), (200, {}, body)])
    monkeypatch.setattr(providers, 'get_breaker', lambda mode: providers.CircuitBreaker())
    monkeypatch.setattr(providers.time, 'sleep', lambda seconds: None)
    config = providers.OpenAICompatibleConfig(True, 'https://api.invalid/chat', 'model', 'synthetic-key', 10, 100)
    result = providers.call_llm(config, [{'role': 'user', 'content': 'synthetic'}],
                                response_format={'type': 'json_object'})
    assert result == 'synthetic reply'
    assert len(adapter.requests) == 2
    if first_status == 400:
        assert 'response_format' in json.loads(adapter.requests[0].body)
        assert 'response_format' not in json.loads(adapter.requests[1].body)


def test_provider_timeout_still_retries(monkeypatch):
    body = json.dumps({'choices': [{'message': {'content': 'synthetic reply'}}]}).encode()
    adapter = transport(monkeypatch, [requests.Timeout('synthetic timeout'), (200, {}, body)])
    monkeypatch.setattr(providers, 'get_breaker', lambda mode: providers.CircuitBreaker())
    waits = []
    monkeypatch.setattr(providers.time, 'sleep', waits.append)
    config = providers.OpenAICompatibleConfig(True, 'https://api.invalid/chat', 'model', 'synthetic-key', 12, 100)
    assert providers.call_llm(config, [{'role': 'user', 'content': 'synthetic'}], max_retries=1) == 'synthetic reply'
    assert len(adapter.requests) == 2 and waits == [1]
    assert all(item['timeout'] == 12 for item in adapter.options)


def test_tencent_audio_cross_origin_stops(monkeypatch):
    adapter = transport(monkeypatch, [(308, {'Location': 'https://other.invalid/'}, b'')])
    with pytest.raises(tencent_asr.TencentAsrError) as caught:
        tencent_asr.sentence_recognition(b'synthetic-audio', 'synthetic-id', 'synthetic-key')
    assert len(adapter.requests) == 1
    assert 'synthetic-key' not in str(caught.value)
    assert 'synthetic-audio' not in str(caught.value)


def extracted_app_function(name, globals_dict, filename='app/app.py'):
    source = (Path(__file__).resolve().parents[1] / filename).read_text(encoding='utf-8-sig')
    tree = ast.parse(source)
    if name == 'generate':
        tree = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == '_ai_handle_chat_stream_request')
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(functions) == 1
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    exec(compile(module, '<isolated-app-function>', 'exec'), globals_dict)
    return globals_dict[name]


def test_vision_redirect_does_not_try_next_model(monkeypatch):
    adapter = transport(monkeypatch, [(307, {'Location': 'https://other.invalid/'}, b'')])
    env = {
        'requests': requests, 'safe_ai_post': safe_http.post, 'UnsafeRedirect': safe_http.UnsafeRedirect,
        'app': SimpleNamespace(logger=SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, error=lambda *a: None)),
        '_ai_llm_configured': lambda: True, '_ai_llm_vision_enabled': lambda: True,
        '_ai_context_value': lambda context, key: '', '_ai_llm_model': lambda **kw: 'first',
        '_ai_llm_max_tokens': lambda: 200, '_ai_llm_headers': lambda: {'Authorization': 'Bearer synthetic'},
        '_ai_llm_timeout_seconds': lambda: 10, '_ai_llm_endpoint': lambda: 'https://api.invalid/start',
        '_AI_MODEL_POOL': [('first', 'first', 1), ('second', 'second', 2)],
    }
    call = extracted_app_function('_ai_call_llm_vision', env)
    reply, extracted, error = call('synthetic', [{'data_url': 'data:image/png;base64,c3ludGhldGlj'}])
    assert reply is None and extracted is None and '已停止' in error
    assert len(adapter.requests) == 1


def test_tokenhub_asr_payload_and_redirect_failure(monkeypatch):
    success = json.dumps({'status': 'completed', 'output': {'text': 'synthetic result'}}).encode()
    adapter = transport(monkeypatch, [(200, {}, success),
                                     (307, {'Location': 'https://other.invalid/'}, b'')])
    env = {
        'requests': requests, 'safe_ai_post': safe_http.post, 'base64': base64,
        '_ai_llm_configured': lambda: True, '_asr_tokenhub_endpoint': lambda: 'https://api.invalid/asr',
        '_ai_llm_url_is_plaintext_remote': lambda url: False,
        '_ai_llm_headers': lambda: {'Authorization': 'Bearer synthetic-key'},
        '_ai_llm_timeout_seconds': lambda: 5,
        'app': SimpleNamespace(logger=SimpleNamespace(warning=lambda *a: None)),
    }
    call = extracted_app_function('_asr_call_tokenhub', env)
    assert call(b'synthetic-audio', 'wav') == ('synthetic result', '')
    body = json.loads(adapter.requests[0].body)
    assert body['data'] == base64.b64encode(b'synthetic-audio').decode()
    assert body['voice_encode_format'] == 'wav' and adapter.options[0]['timeout'] == 60
    text, error = call(b'synthetic-audio', 'wav')
    assert text is None and '连接失败' in error
    assert len(adapter.requests) == 2


def test_native_voice_llm_success_and_redirect_stop(monkeypatch):
    success = json.dumps({'choices': [{'message': {'content': 'synthetic result'}}]}).encode()
    adapter = transport(monkeypatch, [(200, {}, success),
                                     (308, {'Location': 'https://other.invalid/'}, b'')])
    fake_app = ModuleType('app')
    fake_app._ai_llm_configured = lambda: True
    fake_app._ai_llm_endpoint = lambda: 'https://api.invalid/chat'
    fake_app._ai_llm_headers = lambda: {'Authorization': 'Bearer synthetic'}
    fake_app._ai_llm_model = lambda: 'synthetic-model'
    fake_app._ai_llm_timeout_seconds = lambda: 9
    monkeypatch.setitem(sys.modules, 'app', fake_app)
    call = extracted_app_function('_voice_llm_chat', {'safe_ai_post': safe_http.post}, 'app/routes/native_api.py')
    assert call('synthetic prompt') == 'synthetic result'
    assert call('synthetic prompt') is None
    assert len(adapter.requests) == 2 and adapter.options[0]['timeout'] == 9


def test_streaming_same_origin_keeps_sse_and_timeout(monkeypatch):
    adapter = transport(monkeypatch, [
        (307, {'Location': '/stream'}, b''),
        (200, {'Content-Type': 'text/event-stream'},
         b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'),
    ])
    history = []
    env = {
        'requests': requests, 'safe_ai_post': safe_http.post, 'json': json,
        'payload_body': {'stream': True}, 'headers': {'Authorization': 'Bearer synthetic'},
        '_ai_llm_endpoint': lambda: 'https://api.invalid/start', '_ai_llm_timeout_seconds': lambda: 15,
        'sse_event': lambda kind, value: (kind, value), 'user_id': 1, 'chat_message': 'synthetic',
        '_ai_append_history': lambda *a: history.append(a),
        'app': SimpleNamespace(logger=SimpleNamespace(warning=lambda *a: None)),
    }
    generate = extracted_app_function('generate', env)
    assert list(generate()) == [('token', 'ok'), ('done', 'ok')]
    assert len(adapter.requests) == 2
    assert all(item['stream'] is True and item['timeout'] == 15 for item in adapter.options)
    assert len(history) == 2


def test_streaming_cross_origin_returns_error_without_leak_or_retry(monkeypatch):
    adapter = transport(monkeypatch, [(308, {'Location': 'https://other.invalid/'}, b'')])
    env = {
        'requests': requests, 'safe_ai_post': safe_http.post, 'json': json,
        'payload_body': {'stream': True}, 'headers': {'Authorization': 'Bearer synthetic'},
        '_ai_llm_endpoint': lambda: 'https://api.invalid/start', '_ai_llm_timeout_seconds': lambda: 15,
        'sse_event': lambda kind, value: (kind, value),
        'app': SimpleNamespace(logger=SimpleNamespace(warning=lambda *a: None)),
    }
    events = list(extracted_app_function('generate', env)())
    assert len(adapter.requests) == 1
    assert len(events) == 1 and events[0][0] == 'error' and '已停止' in events[0][1]
    assert 'synthetic' not in events[0][1]


def test_all_known_application_consumers_use_safe_post():
    expected = {
        'app/app.py': 11, 'app/ai/providers.py': 3,
        'app/routes/native_api.py': 1, 'app/tencent_asr.py': 1,
    }
    root = Path(__file__).resolve().parents[1]
    for filename, count in expected.items():
        tree = ast.parse((root / filename).read_text(encoding='utf-8-sig'))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'safe_ai_post']
        assert len(calls) == count, filename
