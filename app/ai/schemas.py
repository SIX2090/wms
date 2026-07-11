from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SchemaValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()


def validate_json_schema_payload(schema: Mapping[str, Any] | None, payload: Any) -> SchemaValidationResult:
    """Validate a payload against the small JSON Schema subset used by AI tools."""
    errors: list[str] = []
    _validate_node(schema or {}, payload, '$', errors)
    return SchemaValidationResult(valid=not errors, errors=tuple(errors))


def _validate_node(schema: Mapping[str, Any], value: Any, path: str, errors: list[str]) -> None:
    expected_type = schema.get('type')
    if expected_type and not _matches_type(expected_type, value):
        errors.append(f'{path}: expected {expected_type}')
        return

    enum_values = schema.get('enum')
    if enum_values is not None and value not in enum_values:
        errors.append(f'{path}: value is not in enum')

    if expected_type == 'object' or isinstance(value, dict):
        if not isinstance(value, dict):
            return
        properties = schema.get('properties') or {}
        required = schema.get('required') or ()
        additional = schema.get('additionalProperties', True)

        for key in required:
            if key not in value:
                errors.append(f'{path}.{key}: required')

        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is None:
                if additional is False:
                    errors.append(f'{path}.{key}: additional property is not allowed')
                continue
            if isinstance(child_schema, Mapping):
                _validate_node(child_schema, item, f'{path}.{key}', errors)
        return

    if expected_type == 'array' or isinstance(value, list):
        if not isinstance(value, list):
            return
        min_items = schema.get('minItems')
        max_items = schema.get('maxItems')
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f'{path}: expected at least {min_items} items')
        if isinstance(max_items, int) and len(value) > max_items:
            errors.append(f'{path}: expected at most {max_items} items')
        item_schema = schema.get('items')
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate_node(item_schema, item, f'{path}[{index}]', errors)
        return

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get('minimum')
        maximum = schema.get('maximum')
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f'{path}: below minimum {minimum}')
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f'{path}: above maximum {maximum}')


def _matches_type(expected_type: Any, value: Any) -> bool:
    if isinstance(expected_type, (list, tuple)):
        return any(_matches_type(item, value) for item in expected_type)
    return {
        'object': isinstance(value, dict),
        'array': isinstance(value, list),
        'string': isinstance(value, str),
        'integer': isinstance(value, int) and not isinstance(value, bool),
        'number': isinstance(value, (int, float)) and not isinstance(value, bool),
        'boolean': isinstance(value, bool),
        'null': value is None,
    }.get(str(expected_type), True)
