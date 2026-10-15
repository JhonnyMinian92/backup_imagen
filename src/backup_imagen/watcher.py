"""Monitor de unidades USB para iniciar la consola al conectar el destino."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from backup_imagen.volumes import posix_backup_volumes, windows_backup_volumes


def _console_python() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        console = executable.with_name("python.exe")
        if console.exists():
            return str(console)
    return sys.executable


def launch_backup(destination: Path) -> subprocess.Popen[bytes]:
    """Abre una consola nueva que valida el USB y recorre el equipo."""
    command = [
        _console_python(),
        "-m",
        "backup_imagen",
        "--destination",
        str(destination),
        "--pause",
    ]
    if os.name == "nt":
        return subprocess.Popen(
            command,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
        )

    for terminal, prefix in (
        ("x-terminal-emulator", ["-e"]),
        ("gnome-terminal", ["--"]),
        ("konsole", ["-e"]),
        ("xterm", ["-e"]),
    ):
        terminal_path = shutil.which(terminal)
        if terminal_path:
            return subprocess.Popen([terminal_path, *prefix, *command], close_fds=True)
    raise RuntimeError("No se encontró una aplicación de terminal para mostrar el resumen")


def _connected_backup_volumes() -> set[Path]:
    if os.name == "nt":
        return windows_backup_volumes()
    if os.name == "posix":
        return posix_backup_volumes()
    return set()


def _acquire_windows_singleton() -> int | None:
    """Evita dos monitores al instalarlo y al iniciar sesión."""
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, 0, "Local\\BackupImagenUsbWatcher")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return int(handle)


def watch_for_usb(poll_interval: float = 2.0) -> None:
    """Espera unidades NTFS de 32 GB nuevas y lanza una consola por conexión."""
    if not math.isfinite(poll_interval) or poll_interval <= 0:
        raise ValueError("poll_interval debe ser un número finito mayor que cero")
    if os.name != "nt" and not sys.platform.startswith("linux"):
        raise RuntimeError(f"El monitor automático no está disponible en {os.name}")

    if os.name == "nt" and _acquire_windows_singleton() is None:
        return

    # Si el monitor se inicia con el USB ya conectado también respalda; al volver
    # a conectar una memoria, la ausencia intermedia permite un nuevo disparo.
    present: set[Path] = set()
    while True:
        time.sleep(poll_interval)
        current = _connected_backup_volumes()
        for destination in sorted(current - present):
            try:
                launch_backup(destination)
            except (OSError, RuntimeError) as exc:
                print(f"No se pudo abrir el respaldo para {destination}: {exc}", file=sys.stderr)
        present = current
