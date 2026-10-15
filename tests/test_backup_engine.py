from pathlib import Path

from backup_imagen.engine import BackupEngine
from backup_imagen.models import BackupConfig


def test_usb_validation_is_enabled_by_default(tmp_path: Path) -> None:
    config = BackupConfig(None, tmp_path)

    assert config.require_ntfs_32gb is True


def test_copies_supported_files_and_preserves_structure(tmp_path: Path) -> None:
    source = tmp_path / "source"
    usb = tmp_path / "usb"
    nested = source / "DCIM" / "Camera"
    nested.mkdir(parents=True)
    usb.mkdir()
    (nested / "photo.JPG").write_bytes(b"image-data")
    (nested / "notes.txt").write_text("not an image", encoding="utf-8")

    report = BackupEngine(BackupConfig(source, usb, require_ntfs_32gb=False)).run()

    target = usb / "backup" / "DCIM" / "Camera" / "photo.JPG"
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
    target_dir = usb / "backup"
    target_dir.mkdir()
    (target_dir / "photo.jpg").write_bytes(b"old-image")

    report = BackupEngine(BackupConfig(source, usb, require_ntfs_32gb=False)).run()

    assert (target_dir / "photo.jpg").read_bytes() == b"old-image"
    assert (target_dir / "photo (copia 1).jpg").read_bytes() == b"new-image"
    assert report.copied == 1


def test_skips_identical_existing_suffix_after_name_collision(tmp_path: Path) -> None:
    source = tmp_path / "source"
    usb = tmp_path / "usb"
    source.mkdir()
    usb.mkdir()
    (source / "photo.jpg").write_bytes(b"new-image")
    target_dir = usb / "backup"
    target_dir.mkdir()
    (target_dir / "photo.jpg").write_bytes(b"old-image")
    (target_dir / "photo (copia 1).jpg").write_bytes(b"new-image")

    report = BackupEngine(BackupConfig(source, usb, require_ntfs_32gb=False)).run()

    assert report.copied == 0
    assert report.skipped_existing == 1
    assert len(list(target_dir.iterdir())) == 2


def test_skips_same_content_without_creating_duplicate(tmp_path: Path) -> None:
    source = tmp_path / "source"
    usb = tmp_path / "usb"
    source.mkdir()
    target_dir = usb / "backup"
    target_dir.mkdir(parents=True)
    payload = b"identical-image"
    (source / "photo.png").write_bytes(payload)
    (target_dir / "photo.png").write_bytes(payload)

    report = BackupEngine(BackupConfig(source, usb, require_ntfs_32gb=False)).run()

    assert report.skipped_existing == 1
    assert list(target_dir.iterdir()) == [target_dir / "photo.png"]


def test_excludes_destination_when_it_is_under_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    usb = source / "USB"
    usb.mkdir(parents=True)
    (source / "picture.jpg").write_bytes(b"image")
    (usb / "old.jpg").write_bytes(b"old backup")

    report = BackupEngine(BackupConfig(source, usb, require_ntfs_32gb=False)).run()

    assert report.discovered == 1
    assert report.copied == 1
    assert not (usb / "backup" / "USB" / "old.jpg").exists()


def test_all_sources_keep_a_separate_root_under_backup(tmp_path: Path, monkeypatch) -> None:
    import backup_imagen.engine as engine_module

    drive_c = tmp_path / "drive-c"
    drive_d = tmp_path / "drive-d"
    usb = tmp_path / "usb"
    drive_c.mkdir()
    drive_d.mkdir()
    usb.mkdir()
    (drive_c / "photos").mkdir()
    (drive_d / "photos").mkdir()
    (drive_c / "photos" / "same.jpg").write_bytes(b"from-c")
    (drive_d / "photos" / "same.jpg").write_bytes(b"from-d")
    monkeypatch.setattr(
        engine_module,
        "source_roots",
        lambda: [(drive_c, "C"), (drive_d, "D"), (usb, "E")],
    )

    report = BackupEngine(BackupConfig(None, usb, require_ntfs_32gb=False)).run()

    assert report.discovered == 2
    assert report.copied == 2
    assert (usb / "backup" / "C" / "photos" / "same.jpg").read_bytes() == b"from-c"
    assert (usb / "backup" / "D" / "photos" / "same.jpg").read_bytes() == b"from-d"
    assert not (usb / "backup" / "E").exists()


def test_scan_access_errors_are_reported_separately(tmp_path: Path) -> None:
    class InaccessibleScanner:
        def scan(self, root, excluded_root=None, on_error=None):
            if on_error is not None:
                on_error(PermissionError("access denied"))
            return iter(())

    source = tmp_path / "source"
    usb = tmp_path / "usb"
    source.mkdir()
    usb.mkdir()

    report = BackupEngine(
        BackupConfig(source, usb, require_ntfs_32gb=False), scanner=InaccessibleScanner()
    ).run()

    assert report.discovered == 0
    assert report.failed == 0
    assert report.scan_errors == 1
    assert not report.succeeded
