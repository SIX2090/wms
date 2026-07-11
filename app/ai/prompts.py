from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


CURRENT_PROMPT_VERSION = 'legacy-v1'


@dataclass(frozen=True)
class AIPromptSpec:
    version: str
    purpose: str
    system_prompt: str


AI_PROMPTS = MappingProxyType({
    'legacy-v1': AIPromptSpec(
        version='legacy-v1',
        purpose='Compatibility prompt for the existing WMS assistant and local tool fallback.',
        system_prompt=(
            'You are a WMS business copilot. Prefer deterministic local tools for stock, '
            'documents, drafts, audits, and navigation. Never auto-submit, approve, complete, '
            'delete, or directly mutate inventory.'
        ),
    ),
})


def get_prompt_spec(version: str | None = None) -> AIPromptSpec:
    prompt_version = version or CURRENT_PROMPT_VERSION
    return AI_PROMPTS.get(prompt_version) or AI_PROMPTS[CURRENT_PROMPT_VERSION]
