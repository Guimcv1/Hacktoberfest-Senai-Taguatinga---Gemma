"""Armazenamento local dos PDFs originais, isolado por usuário."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger("studybuddy")

_SAFE_ID = re.compile(r"^[0-9a-fA-F-]{8,36}$")


class UnsafeDocumentPathError(ValueError):
    pass


def relative_pdf_path(user_id: str, document_id: str) -> str:
    if not _SAFE_ID.fullmatch(user_id) or not _SAFE_ID.fullmatch(document_id):
        raise UnsafeDocumentPathError("Identificador de documento inválido.")
    return f"{user_id}/{document_id}.pdf"


def storage_root(settings: Settings) -> Path:
    return Path(settings.document_storage_dir).expanduser().resolve()


def absolute_pdf_path(settings: Settings, relative_path: str) -> Path:
    root = storage_root(settings)
    relative = Path(relative_path.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise UnsafeDocumentPathError("Caminho de armazenamento inválido.")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise UnsafeDocumentPathError("Caminho de armazenamento inválido.") from None
    return path


def write_pdf(settings: Settings, user_id: str, document_id: str, content: bytes) -> str:
    relative = relative_pdf_path(user_id, document_id)
    path = absolute_pdf_path(settings, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative


def read_pdf(settings: Settings, relative_path: str) -> Path:
    path = absolute_pdf_path(settings, relative_path)
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    return path


def delete_pdf(settings: Settings, relative_path: str | None) -> None:
    if not relative_path:
        return
    try:
        path = absolute_pdf_path(settings, relative_path)
    except UnsafeDocumentPathError:
        logger.warning("Ignorando caminho de PDF inválido na exclusão.")
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Não foi possível remover o arquivo original do documento.")
