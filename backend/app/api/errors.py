"""Erros de validação no formato público da API, sem ecoar os valores enviados."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}
_MESSAGES = {
    "missing": "Campo obrigatório.",
    "string_too_short": "Deve ter pelo menos {min_length} caractere(s).",
    "string_too_long": "Deve ter no máximo {max_length} caractere(s).",
    "string_type": "Deve ser um texto.",
    "int_parsing": "Deve ser um número inteiro.",
    "int_type": "Deve ser um número inteiro.",
    "greater_than_equal": "Deve ser maior ou igual a {ge}.",
    "less_than_equal": "Deve ser menor ou igual a {le}.",
    "json_invalid": "JSON inválido.",
    "dict_type": "Deve ser um objeto JSON.",
    "model_attributes_type": "Deve ser um objeto JSON.",
}


def public_validation_errors(errors: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for error in errors:
        error_type = str(error.get("type", "value_error"))
        items.append({"field": _field(error, error_type), "type": error_type, "message": _message(error, error_type)})
    return items


def _field(error: Mapping[str, Any], error_type: str) -> str:
    location = [str(part) for part in error.get("loc", ())]
    if error_type == "json_invalid":
        return "body"
    if location and location[0] in _LOCATION_PREFIXES:
        return ".".join(location[1:]) or location[0]
    return ".".join(location)


def _message(error: Mapping[str, Any], error_type: str) -> str:
    context = error.get("ctx") or {}
    if error_type == "value_error":
        if isinstance(context.get("error"), Exception):
            return str(context["error"])
        if "reason" in context:
            return "Endereço de e-mail inválido."
        return "Valor inválido."
    template = _MESSAGES.get(error_type)
    if template is None:
        return "Valor inválido."
    try:
        return template.format(**context)
    except (KeyError, IndexError, ValueError):
        return "Valor inválido."
