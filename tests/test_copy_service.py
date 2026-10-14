from pathlib import Path

import pytest

from backup_imagen.copy_service import CopyService
from backup_imagen.models import BackupConfig


def test_fallback_never_deletes_an_existing_target(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    destination = tmp_path / "usb"
    source_root.mkdir()
    destination.mkdir()
    source = source_root / "photo.jpg"
    source.write_bytes(b"new image")
    config = BackupConfig(source_root, destination)
    service = CopyService(config)

    temporary = destination / ".photo.jpg.tmp"
    temporary.write_bytes(b"new image")
    target = destination / "photo.jpg"
    target.write_bytes(b"existing backup")

    with pytest.raises(FileExistsError):
        service._publish_without_hard_links(temporary, target)

    assert target.read_bytes() == b"existing backup"
