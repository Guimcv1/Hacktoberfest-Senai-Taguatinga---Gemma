"""Identificadores opcionais: string vazia, null e placeholders de cliente não contam como ID."""

from __future__ import annotations

from pydantic import Field

_BLANK_IDS = {"", "null", "undefined", "none"}


def optional_id(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in _BLANK_IDS:
        return None
    return stripped


def optional_id_field(description: str) -> Field:
    return Field(
        default=None,
        description=description,
        json_schema_extra={"default": None},
    )
