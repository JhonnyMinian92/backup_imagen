from pathlib import Path
from types import SimpleNamespace

from backup_imagen import volumes


def test_ntfs_filesystem_types_are_recognized() -> None:
    assert volumes._is_ntfs_filesystem("ntfs", "")
    assert volumes._is_ntfs_filesystem("NTFS3", "")
    assert volumes._is_ntfs_filesystem("fuse.ntfs-3g", "")
    assert not volumes._is_ntfs_filesystem("exfat", "")


def test_fuseblk_requires_blkid_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(volumes.shutil, "which", lambda _: "blkid")
    monkeypatch.setattr(
        volumes.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="ntfs\n"),
    )

    assert volumes._is_ntfs_filesystem("fuseblk", "/dev/sdb1")


def test_fuseblk_rejects_unconfirmed_filesystem(monkeypatch) -> None:
    monkeypatch.setattr(volumes.shutil, "which", lambda _: None)

    assert not volumes._is_ntfs_filesystem("fuseblk", "/dev/sdb1")


def test_detects_usb_topology_ancestor() -> None:
    assert volumes._has_usb_sysfs_ancestor(Path("/sys/devices/pci/usb2/2-1/block/sdb/sdb1"))
    assert not volumes._has_usb_sysfs_ancestor(Path("/sys/devices/pci/usb_storage/block/sdb"))


def test_decodes_proc_mount_octal_escapes() -> None:
    assert volumes._decode_mount_field("/media/My\\040USB") == "/media/My USB"
