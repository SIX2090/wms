"""阶段1：统一 LLM Provider 模块。

封装 OpenAI 兼容接口调用，提供：
- 错误处理（HTTP 错误 / 超时 / JSON 解析失败）
- 超时控制（可配置，默认 30s）
- 自动重试（指数退避，最多 2 次）
- 熔断器（连续失败 N 次后自动降级）
- 降级机制（LLM 不可用时返回 None，由调用方回退到本地规则）
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# ---- 熔断器 ----

@dataclass
class CircuitBreaker:
    """简单熔断器：连续失败达到阈值后自动打开，冷却期后尝试半开。

    线程安全：所有状态读写都通过 _lock 保护。
    """

    failure_threshold: int = 3
    cooldown_seconds: int = 60
    _failures: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)
    _state: str = field(default='closed', repr=False)  # closed / open / half_open
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == 'open':
                if time.time() - self._last_failure_time >= self.cooldown_seconds:
                    self._state = 'half_open'
                    self._failures = 0
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = 'closed'

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()
            if self._failures >= self.failure_threshold:
                self._state = 'open'
                logger.warning('LLM circuit breaker OPEN after %d failures', self._failures)

    def allow_request(self) -> bool:
        return self.state != 'open'

    @property
    def stats(self) -> dict:
        return {
            'state': self.state,
            'failures': self._failures,
            'threshold': self.failure_threshold,
            'cooldown': self.cooldown_seconds,
        }


# ---- 全局熔断器实例 ----

_intent_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
_chat_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
_vision_breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=120)


def get_breaker(mode: str) -> CircuitBreaker:
    """获取指定模式的熔断器。"""
    if mode == 'intent':
        return _intent_breaker
    elif mode == 'vision':
        return _vision_breaker
    return _chat_breaker


# ---- 配置 ----

@dataclass(frozen=True)
class OpenAICompatibleConfig:
    """OpenAI 兼容配置。"""

    enabled: bool
    endpoint: str
    model: str
    api_key: str
    timeout_seconds: int
    max_tokens: int
    vision_enabled: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.endpoint and self.model and self.api_key)

    @property
    def safe_endpoint(self) -> bool:
        parsed = urlparse(self.endpoint)
        if parsed.scheme == 'https':
            return True
        return parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}

    def headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def redacted(self) -> dict[str, object]:
        return {
            'enabled': self.enabled,
            'endpoint': self.endpoint,
            'model': self.model,
            'api_key': '***' if self.api_key else '',
            'timeout_seconds': self.timeout_seconds,
            'max_tokens': self.max_tokens,
            'vision_enabled': self.vision_enabled,
            'configured': self.configured,
            'safe_endpoint': self.safe_endpoint,
        }


# 思考模型默认开启深度推理，推理过程会消耗大量 token。
# 如果 max_tokens 太小，推理吃光额度后 content 为空。
# 对这些模型自动把 max_tokens 提到安全下限（只上调、不下调）。
_THINKING_MODEL_MIN_TOKENS = 2048
_THINKING_MODEL_KEYWORDS = (
    'deepseek-v4', 'deepseek_v4', 'glm-5', 'glm_5',
)


def _is_thinking_model(model: str) -> bool:
    m = (model or '').lower()
    return any(kw in m for kw in _THINKING_MODEL_KEYWORDS)


def _effective_max_tokens(config: OpenAICompatibleConfig) -> int:
    """对思考模型自动把 max_tokens 提到安全下限（只上调、不下调）。"""
    val = config.max_tokens or 0
    if _is_thinking_model(config.model) and val < _THINKING_MODEL_MIN_TOKENS:
        return _THINKING_MODEL_MIN_TOKENS
    return val


def build_chat_payload(
    config: OpenAICompatibleConfig,
    messages: list[dict[str, object]],
    *,
    temperature: float = 0.2,
    stream: bool = False,
    response_format: Optional[dict] = None,
) -> dict[str, object]:
    """构建聊天请求载荷。"""
    payload: dict[str, object] = {
        'model': config.model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': _effective_max_tokens(config),
        'stream': stream,
    }
    if response_format:
        payload['response_format'] = response_format
    return payload


# ---- 统一 LLM 调用 ----

class LLMCallError(Exception):
    """LLM 调用异常。"""

    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def call_llm(
    config: OpenAICompatibleConfig,
    messages: list[dict[str, object]],
    *,
    temperature: float = 0.2,
    timeout_override: Optional[int] = None,
    max_retries: int = 2,
    mode: str = 'chat',
    response_format: Optional[dict] = None,
) -> Optional[str]:
    """统一 LLM 调用入口。

    Args:
        config: LLM 配置
        messages: 消息列表
        temperature: 温度参数
        timeout_override: 覆盖默认超时
        max_retries: 最大重试次数（0=不重试）
        mode: 调用模式（intent/chat/vision），用于选择熔断器
        response_format: 响应格式（如 {'type': 'json_object'}）

    Returns:
        模型回复文本，失败返回 None
    """
    if not config.configured:
        return None

    breaker = get_breaker(mode)
    if not breaker.allow_request():
        logger.warning('LLM circuit breaker open (%s mode), skipping call', mode)
        return None

    timeout = timeout_override or config.timeout_seconds
    payload = build_chat_payload(config, messages, temperature=temperature, response_format=response_format)
    headers = config.headers()

    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                config.endpoint,
                headers=headers,
                json=payload,
                timeout=timeout,
            )

            if response.status_code == 429:
                # Rate limit - retry with backoff
                if attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    logger.info('LLM rate limited, retrying in %ds (attempt %d/%d)', wait, attempt + 1, max_retries)
                    time.sleep(wait)
                    continue
                raise LLMCallError('Rate limited (429)', status_code=429, retryable=True)

            if response.status_code == 400:
                # 某些模型不支持 response_format，去掉重试
                if response_format and attempt == 0:
                    payload_no_format = {k: v for k, v in payload.items() if k != 'response_format'}
                    response = requests.post(
                        config.endpoint,
                        headers=headers,
                        json=payload_no_format,
                        timeout=timeout,
                    )
                else:
                    raise LLMCallError(
                        f'Bad request: {response.text[:200]}',
                        status_code=400,
                        retryable=False,
                    )

            response.raise_for_status()
            data = response.json()
            content = (((data.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip()

            # 思考模型可能因 max_tokens 不足返回空 content。
            # 已自动上调到 2048，若仍为空则关闭推理模式重试一次。
            if not content and _is_thinking_model(config.model) and attempt == 0:
                logger.info('Thinking model returned empty content, retrying with thinking disabled')
                payload_no_think = {k: v for k, v in payload.items() if k != 'thinking'}
                payload_no_think['thinking'] = {'type': 'disabled'}
                response = requests.post(
                    config.endpoint,
                    headers=headers,
                    json=payload_no_think,
                    timeout=timeout,
                )
                if response.status_code == 200:
                    data2 = response.json()
                    content = (((data2.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip()

            breaker.record_success()
            return content if content else None

        except requests.exceptions.Timeout as exc:
            last_error = exc
            logger.warning('LLM timeout (attempt %d/%d): %s', attempt + 1, max_retries + 1, exc)
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue

        except requests.exceptions.ConnectionError as exc:
            last_error = exc
            logger.warning('LLM connection error (attempt %d/%d): %s', attempt + 1, max_retries + 1, exc)
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue

        except LLMCallError as exc:
            if not exc.retryable:
                breaker.record_failure()
                raise
            last_error = exc
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue

        except Exception as exc:
            last_error = exc
            logger.warning('LLM unexpected error (attempt %d/%d): %s', attempt + 1, max_retries + 1, exc)
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue

    # All retries exhausted
    breaker.record_failure()
    logger.error('LLM call failed after %d attempts: %s', max_retries + 1, last_error)
    return None


# ---- 便捷函数 ----

def call_llm_intent(
    config: OpenAICompatibleConfig,
    system_prompt: str,
    user_message: str,
) -> Optional[dict]:
    """调用 LLM 进行意图解析，返回解析后的 dict 或 None。"""
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_message[:1000]},
    ]
    content = call_llm(
        config, messages,
        temperature=0,
        timeout_override=min(max(config.timeout_seconds, 2), 6),
        mode='intent',
        response_format={'type': 'json_object'},
    )
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning('LLM intent response is not valid JSON: %s', content[:200])
        return None


def call_llm_chat(
    config: OpenAICompatibleConfig,
    system_prompt: str,
    user_message: str,
    max_reply_length: int = 1200,
) -> Optional[str]:
    """调用 LLM 进行普通对话，返回回复文本或 None。"""
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_message[:1000]},
    ]
    content = call_llm(
        config, messages,
        temperature=0.4,
        mode='chat',
    )
    if not content:
        return None
    return content[:max_reply_length]


def call_llm_vision(
    config: OpenAICompatibleConfig,
    system_prompt: str,
    user_content: list[dict],
    max_reply_length: int = 1400,
) -> tuple[Optional[str], Optional[dict], Optional[str]]:
    """调用 LLM 进行视觉识别，返回 (reply, extracted, error)。"""
    if not config.configured:
        return None, None, '请先启用大模型并保存 API Key'
    if not config.vision_enabled:
        return None, None, '系统设置里没有启用图片识别'

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_content},
    ]
    content = call_llm(
        config, messages,
        temperature=0.2,
        timeout_override=max(config.timeout_seconds, 60),
        mode='vision',
    )
    if not content:
        return None, None, '模型未返回内容'

    # 尝试解析末尾的 JSON 代码块
    extracted = None
    import re
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if match:
        try:
            extracted = json.loads(match.group(1).strip())
            content = content[:match.start()].strip()
        except json.JSONDecodeError:
            pass

    return content[:max_reply_length] if content else None, extracted, None


# ---- 状态查询 ----

def get_all_breakers_status() -> dict[str, dict]:
    """获取所有熔断器状态。"""
    return {
        'intent': _intent_breaker.stats,
        'chat': _chat_breaker.stats,
        'vision': _vision_breaker.stats,
    }


def reset_breakers() -> None:
    """重置所有熔断器。"""
    for breaker in (_intent_breaker, _chat_breaker, _vision_breaker):
        breaker._failures = 0
        breaker._state = 'closed'
        breaker._last_failure_time = 0.0
