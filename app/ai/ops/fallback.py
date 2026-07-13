"""阶段5：LLM熔断回退增强模块。

在阶段1 CircuitBreaker 基础上增强：
- 多级回退链（主模型→备用模型→本地规则）
- 回退原因记录
- 回退统计
- 手动切换模型
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# 延迟导入 providers（依赖 requests）
try:
    from ..providers import CircuitBreaker, OpenAICompatibleConfig, call_llm, get_breaker
    _HAS_PROVIDERS = True
except ImportError:
    _HAS_PROVIDERS = False
    # 提供占位符以便模块可以加载
    class CircuitBreaker:
        pass
    class OpenAICompatibleConfig:
        pass
    def call_llm(*args, **kwargs):
        return None
    def get_breaker(*args, **kwargs):
        return None


class FallbackLevel(str, Enum):
    """回退级别。"""
    PRIMARY = 'primary'  # 主模型
    SECONDARY = 'secondary'  # 备用模型
    LOCAL_RULES = 'local_rules'  # 本地规则
    STATIC_RESPONSE = 'static_response'  # 静态回复


@dataclass
class FallbackRecord:
    """回退记录。"""
    timestamp: datetime
    from_level: FallbackLevel
    to_level: FallbackLevel
    reason: str
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'from_level': self.from_level.value,
            'to_level': self.to_level.value,
            'reason': self.reason,
            'latency_ms': round(self.latency_ms, 1),
        }


class FallbackChain:
    """多级回退链。"""

    def __init__(self):
        self._primary_config: Optional[OpenAICompatibleConfig] = None
        self._secondary_config: Optional[OpenAICompatibleConfig] = None
        self._local_handler: Optional[Callable] = None
        self._fallback_records: list[FallbackRecord] = []
        self._stats = {
            'primary_success': 0,
            'primary_failure': 0,
            'secondary_success': 0,
            'secondary_failure': 0,
            'local_fallback': 0,
        }

    def set_primary(self, config: OpenAICompatibleConfig) -> None:
        """设置主模型配置。"""
        self._primary_config = config

    def set_secondary(self, config: OpenAICompatibleConfig) -> None:
        """设置备用模型配置。"""
        self._secondary_config = config

    def set_local_handler(self, handler: Callable) -> None:
        """设置本地规则处理器。"""
        self._local_handler = handler

    def execute(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        timeout: Optional[int] = None,
        mode: str = 'chat',
    ) -> tuple[Optional[str], FallbackLevel]:
        """执行回退链调用。

        Returns:
            (response_text, fallback_level)
        """
        import time

        # 尝试主模型
        if self._primary_config and self._primary_config.configured:
            start = time.time()
            try:
                result = call_llm(
                    self._primary_config, messages,
                    temperature=temperature,
                    timeout_override=timeout,
                    mode=mode,
                )
                latency = (time.time() - start) * 1000
                if result:
                    self._stats['primary_success'] += 1
                    return result, FallbackLevel.PRIMARY
                else:
                    self._stats['primary_failure'] += 1
                    self._fallback_records.append(FallbackRecord(
                        timestamp=datetime.now(),
                        from_level=FallbackLevel.PRIMARY,
                        to_level=FallbackLevel.SECONDARY if self._secondary_config else FallbackLevel.LOCAL_RULES,
                        reason='primary returned empty',
                        latency_ms=latency,
                    ))
            except Exception as e:
                latency = (time.time() - start) * 1000
                self._stats['primary_failure'] += 1
                self._fallback_records.append(FallbackRecord(
                    timestamp=datetime.now(),
                    from_level=FallbackLevel.PRIMARY,
                    to_level=FallbackLevel.SECONDARY if self._secondary_config else FallbackLevel.LOCAL_RULES,
                    reason=f'primary error: {str(e)[:100]}',
                    latency_ms=latency,
                ))

        # 尝试备用模型
        if self._secondary_config and self._secondary_config.configured:
            start = time.time()
            try:
                result = call_llm(
                    self._secondary_config, messages,
                    temperature=temperature,
                    timeout_override=timeout,
                    mode=mode,
                )
                latency = (time.time() - start) * 1000
                if result:
                    self._stats['secondary_success'] += 1
                    return result, FallbackLevel.SECONDARY
                else:
                    self._stats['secondary_failure'] += 1
            except Exception as e:
                latency = (time.time() - start) * 1000
                self._stats['secondary_failure'] += 1
                logger.warning('Secondary model failed: %s', e)

        # 回退到本地规则
        if self._local_handler:
            self._stats['local_fallback'] += 1
            self._fallback_records.append(FallbackRecord(
                timestamp=datetime.now(),
                from_level=FallbackLevel.SECONDARY if self._secondary_config else FallbackLevel.PRIMARY,
                to_level=FallbackLevel.LOCAL_RULES,
                reason='all models failed, using local rules',
            ))
            try:
                result = self._local_handler(messages)
                return result, FallbackLevel.LOCAL_RULES
            except Exception as e:
                logger.error('Local handler failed: %s', e)

        return None, FallbackLevel.LOCAL_RULES

    def get_stats(self) -> dict[str, Any]:
        """获取回退统计。"""
        total = sum(self._stats.values())
        return {
            **self._stats,
            'total_calls': total,
            'primary_success_rate': round(
                self._stats['primary_success'] / total * 100, 1
            ) if total > 0 else 0,
            'fallback_rate': round(
                (self._stats['secondary_success'] + self._stats['local_fallback']) / total * 100, 1
            ) if total > 0 else 0,
            'recent_fallbacks': [r.to_dict() for r in self._fallback_records[-20:]],
        }

    def reset_stats(self) -> None:
        """重置统计。"""
        self._stats = {
            'primary_success': 0,
            'primary_failure': 0,
            'secondary_success': 0,
            'secondary_failure': 0,
            'local_fallback': 0,
        }
        self._fallback_records.clear()


# 全局回退链实例
_fallback_chain = FallbackChain()


def get_fallback_chain() -> FallbackChain:
    """获取全局回退链实例。"""
    return _fallback_chain
