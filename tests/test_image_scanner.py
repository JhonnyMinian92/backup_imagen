from pathlib import Path

from backup_imagen.image_scanner import ImageScanner


def test_matches_extensions_case_insensitively(tmp_path: Path) -> None:
    (tmp_path / "photo.HEIC").write_bytes(b"heic")
    (tmp_path / "photo.tiff").write_bytes(b"tiff")
    (tmp_path / "document.pdf").write_bytes(b"pdf")

    found = {path.name for path in ImageScanner().scan(tmp_path)}

    assert found == {"photo.HEIC", "photo.tiff", "document.pdf"}


def test_includes_requested_graphic_formats_and_excludes_json(tmp_path: Path) -> None:
    supported = [
        "icon.ico",
        "diagram.svg",
        "design.ai",
        "print.eps",
        "logo.cdr",
        "edit.psd",
        "large.psb",
        "scan.pdf",
    ]
    for name in supported:
        (tmp_path / name).write_bytes(b"graphic")
    (tmp_path / "animation.json").write_text('{"v":"5.0"}', encoding="utf-8")

    found = {path.name for path in ImageScanner().scan(tmp_path)}

    assert found == set(supported)


def test_includes_raw_camera_extensions(tmp_path: Path) -> None:
    raw_files = ["capture.raw", "capture.cr3", "capture.ari", "capture.r3d", "capture.rwz"]
    for name in raw_files:
        (tmp_path / name).write_bytes(b"raw image")

    found = {path.name for path in ImageScanner().scan(tmp_path)}

    assert found == set(raw_files)


def test_skips_destination_subtree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = source / "USB" / "backup"
    destination.mkdir(parents=True)
    (source / "photo.jpg").write_bytes(b"image")
    (destination / "previous.jpg").write_bytes(b"old")

    found = {path.name for path in ImageScanner().scan(source, excluded_root=destination)}

    assert found == {"photo.jpg"}
