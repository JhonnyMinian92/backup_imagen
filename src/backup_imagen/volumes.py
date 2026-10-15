"""Descubrimiento y validación de volúmenes locales."""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

MIN_USB_BYTES = 28_000_000_000
MAX_USB_BYTES = 36_000_000_000


def source_roots() -> list[tuple[Path, str]]:
    """Devuelve raíces accesibles que se deben escanear y su nombre de respaldo."""
    if os.name == "nt":
        roots: list[tuple[Path, str]] = []
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetLogicalDrives.restype = ctypes.c_uint32
        kernel32.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
        kernel32.GetDriveTypeW.restype = ctypes.c_uint32
        mask = kernel32.GetLogicalDrives()
        for index in range(26):
            if not mask & (1 << index):
                continue
            letter = chr(ord("A") + index)
            root = Path(f"{letter}:\\")
            drive_type = kernel32.GetDriveTypeW(str(root))
            if drive_type in {2, 3}:  # DRIVE_REMOVABLE o DRIVE_FIXED
                roots.append((root, letter))
        return roots

    if os.name == "posix":
        # Recorrer / también descubre volúmenes montados bajo /media y /mnt.
        # El escáner excluye los pseudo-sistemas de archivos del kernel.
        return [(Path("/"), "root")]

    raise OSError(f"Detección de unidades no compatible con {os.name}")


def windows_volume_info(root: Path) -> tuple[str, int] | None:
    """Obtiene (sistema de archivos, capacidad total) para una unidad Windows."""
    if os.name != "nt":
        return None

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetVolumeInformationW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_wchar_p,
        ctypes.c_uint32,
    ]
    kernel32.GetVolumeInformationW.restype = ctypes.c_int
    kernel32.GetDiskFreeSpaceExW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_ulonglong),
        ctypes.POINTER(ctypes.c_ulonglong),
        ctypes.POINTER(ctypes.c_ulonglong),
    ]
    kernel32.GetDiskFreeSpaceExW.restype = ctypes.c_int
    file_system = ctypes.create_unicode_buffer(64)
    volume_name = ctypes.create_unicode_buffer(261)
    serial = ctypes.c_uint32()
    max_component = ctypes.c_uint32()
    flags = ctypes.c_uint32()
    ok = kernel32.GetVolumeInformationW(
        str(root),
        volume_name,
        len(volume_name),
        ctypes.byref(serial),
        ctypes.byref(max_component),
        ctypes.byref(flags),
        file_system,
        len(file_system),
    )
    if not ok:
        return None

    total = ctypes.c_ulonglong()
    free_available = ctypes.c_ulonglong()
    total_free = ctypes.c_ulonglong()
    ok = kernel32.GetDiskFreeSpaceExW(
        str(root),
        ctypes.byref(free_available),
        ctypes.byref(total),
        ctypes.byref(total_free),
    )
    if not ok:
        return None
    return file_system.value.upper(), int(total.value)


def _decode_mount_field(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def _posix_mount_info(path: Path) -> tuple[Path, str, str] | None:
    """Return the closest mount point, filesystem type, and source device."""
    mounts = Path("/proc/mounts")
    if not mounts.exists():
        return None
    resolved = path.resolve()
    candidates: list[tuple[int, Path, str, str]] = []
    try:
        for line in mounts.read_text(encoding="utf-8", errors="replace").splitlines():
            fields = line.split()
            if len(fields) < 3:
                continue
            mount_point = Path(_decode_mount_field(fields[1])).resolve()
            try:
                resolved.relative_to(mount_point)
            except ValueError:
                continue
            candidates.append(
                (len(str(mount_point)), mount_point, fields[2].lower(), _decode_mount_field(fields[0]))
            )
    except OSError:
        return None
    if not candidates:
        return None
    _, mount_point, filesystem, source = max(candidates, key=lambda item: item[0])
    return mount_point, filesystem, source


def _posix_filesystem(path: Path) -> str | None:
    mount_info = _posix_mount_info(path)
    return mount_info[1] if mount_info else None


def _is_ntfs_filesystem(filesystem: str, source: str) -> bool:
    """Recognize kernel NTFS mounts and verify ntfs-3g's generic FUSE type."""
    normalized = filesystem.lower()
    if normalized in {"ntfs", "ntfs3", "ntfs-3g", "fuse.ntfs-3g"}:
        return True
    if normalized != "fuseblk":
        return False

    blkid = shutil.which("blkid")
    if blkid is None:
        return False
    try:
        result = subprocess.run(
            [blkid, "-o", "value", "-s", "TYPE", source],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip().lower() in {"ntfs", "ntfs3"}


def _has_usb_sysfs_ancestor(device_path: Path) -> bool:
    return any(re.fullmatch(r"usb\d+", parent.name) for parent in (device_path, *device_path.parents))


def _is_usb_mount_source(source: str, sys_block_root: Path = Path("/sys/dev/block")) -> bool:
    """Require a block device whose sysfs topology contains a USB bus."""
    if not source.startswith("/dev/"):
        return False
    try:
        metadata = os.stat(source)
        if not stat.S_ISBLK(metadata.st_mode):
            return False
        device_path = (sys_block_root / f"{os.major(metadata.st_rdev)}:{os.minor(metadata.st_rdev)}").resolve(strict=True)
    except OSError:
        return False
    return _has_usb_sysfs_ancestor(device_path)


def posix_backup_volumes() -> set[Path]:
    """NTFS USB volumes of about 32 GB mounted as external media on Linux."""
    if os.name != "posix":
        return set()
    mounts = Path("/proc/mounts")
    if not mounts.exists():
        return set()

    found: set[Path] = set()
    try:
        lines = mounts.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return found
    external_prefixes = (Path("/media"), Path("/mnt"), Path("/run/media"))
    for line in lines:
        fields = line.split()
        if len(fields) < 3 or fields[2].lower() not in {
            "ntfs", "ntfs3", "ntfs-3g", "fuse.ntfs-3g", "fuseblk"
        }:
            continue
        source = _decode_mount_field(fields[0])
        root = Path(_decode_mount_field(fields[1]))
        if not any(root == prefix or prefix in root.parents for prefix in external_prefixes):
            continue
        if not _is_usb_mount_source(source):
            continue
        if not _is_ntfs_filesystem(fields[2], source):
            continue
        try:
            total_bytes = shutil.disk_usage(root).total
        except OSError:
            continue
        if MIN_USB_BYTES <= total_bytes <= MAX_USB_BYTES:
            found.add(root.resolve())
    return found


def validate_ntfs_32gb(root: Path) -> None:
    """Require the destination to be the root of an NTFS USB volume near 32 GB."""
    if not root.exists() or not root.is_dir():
        raise ValueError(f"No se encuentra el USB de destino: {root}")

    source = ""
    if os.name == "nt":
        drive_root = Path(root.anchor)
        if not drive_root.anchor or root.resolve() != drive_root.resolve():
            raise ValueError("El destino debe ser la raiz del USB, no una subcarpeta")
        info = windows_volume_info(drive_root)
        if info is None:
            raise OSError(f"No se pudo identificar el sistema de archivos de {drive_root}")
        file_system, total_bytes = info
        if not _windows_is_usb_storage(drive_root):
            raise ValueError("El destino debe ser un dispositivo USB conectado")
    else:
        mount_info = _posix_mount_info(root)
        if mount_info is None:
            raise ValueError("No se pudo identificar el punto de montaje del USB")
        mount_point, file_system, source = mount_info
        if root.resolve() != mount_point:
            raise ValueError("El destino debe ser la raiz del USB, no una subcarpeta")
        if not _is_usb_mount_source(source):
            raise ValueError("El destino debe ser un dispositivo USB conectado")
        total_bytes = shutil.disk_usage(root).total
        file_system = file_system.upper()

    if not _is_ntfs_filesystem(file_system, source if os.name != "nt" else ""):
        raise ValueError(f"El USB debe estar formateado en NTFS; se detecto {file_system or 'desconocido'}")
    if not MIN_USB_BYTES <= total_bytes <= MAX_USB_BYTES:
        actual_gb = total_bytes / 1_000_000_000
        raise ValueError(f"El USB debe tener 32 GB; se detectaron {actual_gb:.1f} GB")


def windows_backup_volumes() -> set[Path]:
    """Unidades NTFS de aproximadamente 32 GB conectadas en Windows."""
    if os.name != "nt":
        return set()

    found: set[Path] = set()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetLogicalDrives.restype = ctypes.c_uint32
    kernel32.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    kernel32.GetDriveTypeW.restype = ctypes.c_uint32
    mask = kernel32.GetLogicalDrives()
    for index in range(26):
        if not mask & (1 << index):
            continue
        letter = chr(ord("A") + index)
        root = Path(f"{letter}:\\")
        drive_type = kernel32.GetDriveTypeW(str(root))
        if drive_type not in {2, 3}:  # DRIVE_REMOVABLE o DRIVE_FIXED
            continue
        info = windows_volume_info(root)
        if info is None:
            continue
        file_system, total_bytes = info
        if file_system == "NTFS" and MIN_USB_BYTES <= total_bytes <= MAX_USB_BYTES:
            if not _windows_is_usb_storage(root):
                continue
            found.add(root)
    return found


def _windows_is_usb_storage(root: Path) -> bool:
    """Confirma el bus USB cuando Windows presenta la memoria como disco fijo."""
    letter = root.drive
    script = (
        "$logical = Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='"
        + letter
        + "'\"; "
        "$partition = Get-CimAssociatedInstance -InputObject $logical "
        "-Association Win32_LogicalDiskToPartition; "
        "$disk = Get-CimAssociatedInstance -InputObject $partition "
        "-Association Win32_DiskDriveToDiskPartition; "
        "$storageDisk = Get-Disk -Number $disk.Index -ErrorAction SilentlyContinue; "
        "if (($storageDisk.BusType -contains 'USB') -or "
        "($disk | Where-Object { $_.InterfaceType -eq 'USB' -or $_.PNPDeviceID -like 'USB*' })) "
        "{ 'USB' } else { 'NO' }"
    )
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if powershell is None:
        return False
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip().upper() == "USB"
