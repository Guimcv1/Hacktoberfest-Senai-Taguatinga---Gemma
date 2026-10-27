from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.document_files import (
    UnsafeDocumentPathError,
    absolute_pdf_path,
    delete_pdf,
    relative_pdf_path,
    write_pdf,
)

VALID_SECRET = "a-valid-random-secret-with-more-than-32-chars"


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, jwt_secret=VALID_SECRET, document_storage_dir=str(tmp_path))


def test_relative_path_uses_ids_not_filename() -> None:
    path = relative_pdf_path("11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222")
    assert path == "11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.pdf"
    assert ".." not in path


def test_rejects_path_traversal(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(UnsafeDocumentPathError):
        absolute_pdf_path(settings, "../secret.pdf")
    with pytest.raises(UnsafeDocumentPathError):
        relative_pdf_path("../etc", "passwd")


def test_write_and_delete_stay_inside_storage_root(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    document_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    relative = write_pdf(settings, user_id, document_id, b"%PDF-1.4 test")
    stored = tmp_path / relative
    assert stored.is_file()
    assert stored.resolve().is_relative_to(tmp_path.resolve())
    delete_pdf(settings, relative)
    assert not stored.exists()
