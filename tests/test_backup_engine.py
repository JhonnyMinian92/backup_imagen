from pathlib import Path

from backup_imagen.engine import BackupEngine
from backup_imagen.models import BackupConfig


def test_copies_supported_files_and_preserves_structure(tmp_path: Path) -> None:
    source = tmp_path / "source"
    usb = tmp_path / "usb"
    nested = source / "DCIM" / "Camera"
    nested.mkdir(parents=True)
    usb.mkdir()
    (nested / "photo.JPG").write_bytes(b"image-data")
    (nested / "notes.txt").write_text("not an image", encoding="utf-8")

    report = BackupEngine(BackupConfig(source, usb, "ANDROID-01")).run()

    target = usb / "ANDROID-01" / "DCIM" / "Camera" / "photo.JPG"
    assert target.read_bytes() == b"image-data"
    assert report.discovered == 1
    assert report.copied == 1
    assert report.failed == 0


def test_does_not_overwrite_existing_backup(tmp_path: Path) -> None:
    source = tmp_path / "source"
    usb = tmp_path / "usb"
    source.mkdir()
    usb.mkdir()
    (source / "photo.jpg").write_bytes(b"new-image")
    target_dir = usb / "PC-01"
    target_dir.mkdir()
    (target_dir / "photo.jpg").write_bytes(b"old-image")

    report = BackupEngine(BackupConfig(source, usb, "PC-01")).run()

    assert (target_dir / "photo.jpg").read_bytes() == b"old-image"
    assert (target_dir / "photo (copia 1).jpg").read_bytes() == b"new-image"
    assert report.copied == 1


def test_skips_same_content_without_creating_duplicate(tmp_path: Path) -> None:
    source = tmp_path / "source"
    usb = tmp_path / "usb"
    source.mkdir()
    target_dir = usb / "DEVICE"
    target_dir.mkdir(parents=True)
    payload = b"identical-image"
    (source / "photo.png").write_bytes(payload)
    (target_dir / "photo.png").write_bytes(payload)

    report = BackupEngine(BackupConfig(source, usb)).run()

    assert report.skipped_existing == 1
    assert list(target_dir.iterdir()) == [target_dir / "photo.png"]


def test_excludes_destination_when_it_is_under_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    usb = source / "USB"
    usb.mkdir(parents=True)
    (source / "picture.jpg").write_bytes(b"image")
    (usb / "old.jpg").write_bytes(b"old backup")

    report = BackupEngine(BackupConfig(source, usb)).run()

    assert report.discovered == 1
    assert report.copied == 1
    assert not (usb / "DEVICE" / "USB" / "old.jpg").exists()
