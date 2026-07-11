from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class OpenAICompatibleConfig:
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


def build_chat_payload(
    config: OpenAICompatibleConfig,
    messages: list[dict[str, object]],
    *,
    temperature: float = 0.2,
    stream: bool = False,
) -> dict[str, object]:
    return {
        'model': config.model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': config.max_tokens,
        'stream': stream,
    }
