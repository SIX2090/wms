from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ai.tools.registry import get_ai_tool_spec, validate_ai_tool_input


ToolHandler = Callable[[str, dict[str, Any] | None], Any]


def dispatch_registered_tool(
    tool_name: str,
    message: str,
    context: dict[str, Any] | None,
    dispatchers: Mapping[str, ToolHandler],
    logger: Any | None = None,
    manual_confirmation: bool = False,
) -> Any | None:
    spec = get_ai_tool_spec(tool_name)
    handler = dispatchers.get(tool_name)
    if not spec or not handler:
        return None
    if spec.confirmation_required and not manual_confirmation:
        if logger is not None:
            logger.warning('AI tool requires manual confirmation before dispatch: %s', tool_name)
        return None
    validation = validate_ai_tool_input(tool_name, context or {})
    if not validation.valid:
        if logger is not None:
            logger.warning(
                'AI tool input rejected: %s errors=%s',
                tool_name,
                '; '.join(validation.errors),
            )
        return None
    if spec.handler_name and spec.handler_name != handler.__name__:
        if logger is not None:
            logger.warning(
                'AI tool handler mismatch: %s registry=%s runtime=%s',
                tool_name,
                spec.handler_name,
                handler.__name__,
            )
        return None
    return handler(message, context)
