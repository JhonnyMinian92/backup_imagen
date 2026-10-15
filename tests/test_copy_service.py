from pathlib import Path

import pytest

from backup_imagen.copy_service import CopyService
from backup_imagen.engine import BackupEngine
from backup_imagen.models import BackupConfig


def test_fallback_never_deletes_an_existing_target(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    destination = tmp_path / "usb"
    source_root.mkdir()
    destination.mkdir()
    source = source_root / "photo.jpg"
    source.write_bytes(b"new image")
    config = BackupConfig(source_root, destination, require_ntfs_32gb=False)
    service = CopyService(config)

    temporary = destination / ".photo.jpg.tmp"
    temporary.write_bytes(b"new image")
    target = destination / "photo.jpg"
    target.write_bytes(b"existing backup")

    with pytest.raises(FileExistsError):
        service._rename_without_replace(temporary, target)

    assert target.read_bytes() == b"existing backup"


def test_copy_publishes_complete_file_and_removes_temporary_file(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    destination = tmp_path / "usb"
    source_root.mkdir()
    destination.mkdir()
    source = source_root / "photo.jpg"
    source.write_bytes(b"complete image payload")
    report = BackupEngine(
        BackupConfig(source_root, destination, require_ntfs_32gb=False)
    ).run()

    backup_root = destination / "backup"
    assert (backup_root / "photo.jpg").read_bytes() == b"complete image payload"
    assert not list(backup_root.glob("*.backup-imagen-tmp"))
    assert report.copied == 1
    assert report.failed == 0
