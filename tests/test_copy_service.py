from pathlib import Path

import pytest

import backup_imagen.copy_service as copy_service_module
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


def test_linux_without_renameat2_fails_closed(tmp_path: Path, monkeypatch) -> None:
    temporary = tmp_path / "temporary"
    target = tmp_path / "target"
    temporary.write_bytes(b"new backup")

    class LibcWithoutRenameat2:
        pass

    monkeypatch.setattr(copy_service_module.os, "name", "posix")
    monkeypatch.setattr(copy_service_module.sys, "platform", "linux")
    monkeypatch.setattr(
        "ctypes.CDLL",
        lambda *args, **kwargs: LibcWithoutRenameat2(),
    )

    with pytest.raises(OSError) as error:
        CopyService._rename_without_replace(temporary, target)

    assert error.value.errno == copy_service_module.errno.ENOTSUP
    assert temporary.read_bytes() == b"new backup"
    assert not target.exists()


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


def test_copy_rejects_source_symlinks(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    destination = tmp_path / "usb"
    source_root.mkdir()
    destination.mkdir()
    actual = source_root / "actual.jpg"
    actual.write_bytes(b"image")
    link = source_root / "linked.jpg"
    try:
        link.symlink_to(actual)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are not available")

    report = BackupEngine(
        BackupConfig(source_root, destination, require_ntfs_32gb=False)
    ).run()

    assert report.discovered == 1
    assert report.copied == 1
    assert (destination / "backup" / "actual.jpg").read_bytes() == b"image"
    assert not (destination / "backup" / "linked.jpg").exists()
    CopyService(BackupConfig(source_root, destination, require_ntfs_32gb=False)).copy_one(
        link, source_root, report
    )
    assert report.failed == 1


def test_copy_rejects_parent_symlink_escaping_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    outside = tmp_path / "outside"
    destination = tmp_path / "usb"
    source_root.mkdir()
    outside.mkdir()
    destination.mkdir()
    external_photo = outside / "photo.jpg"
    external_photo.write_bytes(b"outside image")
    link_directory = source_root / "linked"
    try:
        link_directory.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are not available")

    report = BackupEngine(
        BackupConfig(source_root, destination, require_ntfs_32gb=False)
    ).run()
    CopyService(BackupConfig(source_root, destination, require_ntfs_32gb=False)).copy_one(
        link_directory / external_photo.name, source_root, report
    )

    assert report.failed == 1
    assert not (destination / "backup" / "linked" / "photo.jpg").exists()
