from pathlib import Path

from backup_imagen.image_scanner import ImageScanner


def test_matches_extensions_case_insensitively(tmp_path: Path) -> None:
    (tmp_path / "photo.HEIC").write_bytes(b"heic")
    (tmp_path / "photo.tiff").write_bytes(b"tiff")
    (tmp_path / "document.pdf").write_bytes(b"pdf")

    found = {path.name for path in ImageScanner().scan(tmp_path)}

    assert found == {"photo.HEIC", "photo.tiff"}


def test_skips_destination_subtree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = source / "USB" / "backup"
    destination.mkdir(parents=True)
    (source / "photo.jpg").write_bytes(b"image")
    (destination / "previous.jpg").write_bytes(b"old")

    found = {path.name for path in ImageScanner().scan(source, excluded_root=destination)}

    assert found == {"photo.jpg"}
