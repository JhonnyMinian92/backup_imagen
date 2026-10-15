"""Servicio de copia segura: no sobrescribe ni elimina archivos existentes."""

import errno
import hashlib
import logging
import os
import shutil
import stat
import sys
import uuid
from pathlib import Path

from backup_imagen.models import BackupConfig, BackupReport

logger = logging.getLogger(__name__)


class CopyService:
    """Copia imágenes a un destino preservando rutas relativas."""

    def __init__(self, config: BackupConfig) -> None:
        self._config = config
        try:
            self._destination = config.destination.resolve()
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"No se pudo resolver el destino {config.destination}: {exc}") from exc

    def prepare_backup_root(self, destination: Path | None = None) -> Path:
        """Crea ``backup`` y rechaza rutas redirigidas fuera del USB."""
        root = (destination or self._destination).resolve()
        self._ensure_directory_chain(root, ("backup",))
        return root / "backup"

    def copy_one(
        self,
        source_file: Path,
        source_root: Path,
        report: BackupReport,
        root_label: str | None = None,
    ) -> None:
        """Copia un archivo; registra el error y permite continuar con el siguiente."""
        try:
            source_root = Path(source_root).resolve(strict=False)
            source_file = Path(source_file).absolute()
            if self._is_reparse_point(source_file):
                raise ValueError("No se copian enlaces ni puntos de reanálisis del origen")
            resolved_source = source_file.resolve(strict=True)
            relative = source_file.relative_to(source_root)
            try:
                resolved_source.relative_to(source_root)
            except ValueError as exc:
                raise ValueError("El archivo de origen resuelve fuera de la carpeta de origen") from exc
            target_parts = ["backup"]
            if root_label:
                target_parts.append(self._safe_root_label(root_label))
            target_parts.extend(part for part in relative.parent.parts if part not in {"", "."})
            target_directory = self._ensure_directory_chain(self._destination, target_parts)
            target = self._available_target(target_directory / relative.name, resolved_source)
            while target is not None:
                try:
                    self._copy_atomically(resolved_source, target)
                    report.copied += 1
                    return
                except FileExistsError:
                    target = self._available_target(target_directory / relative.name, resolved_source)
            report.skipped_existing += 1
        except (OSError, RuntimeError, ValueError) as exc:
            report.failed += 1
            self._record_error(report, f"{source_file}: {exc}")

    def _available_target(self, target: Path, source: Path) -> Path | None:
        if not self._path_exists(target):
            return target
        if self._same_content(target, source):
            return None

        stem, suffix = target.stem, target.suffix
        index = 1
        while True:
            candidate = target.with_name(f"{stem} (copia {index}){suffix}")
            if not self._path_exists(candidate):
                return candidate
            if self._same_content(candidate, source):
                return None
            index += 1

    def _copy_atomically(self, source: Path, target: Path) -> None:
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.backup-imagen-tmp")
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=self._config.chunk_size)
                writer.flush()
                os.fsync(writer.fileno())

            try:
                os.link(temporary, target)
            except OSError as link_error:
                if self._path_exists(target):
                    raise FileExistsError(f"Destination appeared during copy: {target}") from link_error
                self._rename_without_replace(temporary, target)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("No se pudo eliminar el archivo temporal %s: %s", temporary, exc)

    @staticmethod
    def _rename_without_replace(temporary: Path, target: Path) -> None:
        """Atomically publish a file without replacing an existing destination."""
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.MoveFileExW.argtypes = [
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_uint32,
            ]
            kernel32.MoveFileExW.restype = ctypes.c_bool
            if kernel32.MoveFileExW(str(temporary), str(target), 0):
                return
            error_code = ctypes.get_last_error()
            if error_code in {183, 80}:  # ERROR_ALREADY_EXISTS / ERROR_FILE_EXISTS
                raise FileExistsError(f"Destination already exists: {target}")
            raise OSError(error_code, ctypes.FormatError(error_code), str(target))
        if sys.platform.startswith("linux"):
            import ctypes

            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2", None)
            if renameat2 is None:
                raise OSError(errno.ENOTSUP, "renameat2 is unavailable", str(target))
            renameat2.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameat2.restype = ctypes.c_int
            result = renameat2(
                -100,
                os.fsencode(temporary),
                -100,
                os.fsencode(target),
                1,
            )
            if result != 0:
                error_code = ctypes.get_errno()
                if error_code in {errno.EEXIST, errno.EISDIR}:
                    raise FileExistsError(f"Destination already exists: {target}")
                raise OSError(error_code, os.strerror(error_code), str(target))
            return
        raise OSError(errno.ENOTSUP, "No safe no-replace rename is available", str(target))

    def _ensure_directory_chain(self, root: Path, parts: tuple[str, ...] | list[str]) -> Path:
        root = root.resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Destination is not a directory: {root}")
        root_device = root.stat().st_dev
        current = root
        for part in parts:
            if part in {"", ".", ".."} or Path(part).is_absolute() or Path(part).name != part:
                raise ValueError(f"Invalid destination path component: {part!r}")
            current = current / part
            try:
                current.mkdir()
            except FileExistsError:
                pass
            metadata = current.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or self._is_reparse_point(current):
                raise ValueError(f"Destination contains an unsafe directory: {current}")
            resolved = current.resolve(strict=True)
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Destination path escapes the USB volume: {current}") from exc
            if metadata.st_dev != root_device:
                raise ValueError(f"Destination path crosses into another volume: {current}")
        return current

    @staticmethod
    def _is_reparse_point(path: Path) -> bool:
        if path.is_symlink():
            return True
        is_junction = getattr(os.path, "isjunction", None)
        if is_junction is not None and is_junction(path):
            return True
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
            kernel32.GetFileAttributesW.restype = ctypes.c_uint32
            attributes = kernel32.GetFileAttributesW(str(path))
            return attributes != 0xFFFFFFFF and bool(attributes & 0x400)
        return False

    @classmethod
    def _path_exists(cls, path: Path) -> bool:
        return path.exists() or path.is_symlink() or cls._is_reparse_point(path)

    @staticmethod
    def _same_content(first: Path, second: Path) -> bool:
        if CopyService._is_reparse_point(first):
            return False
        if not first.is_file() or first.stat().st_size != second.stat().st_size:
            return False
        return CopyService._sha256(first) == CopyService._sha256(second)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _record_error(report: BackupReport, message: str) -> None:
        if len(report.errors) < 100:
            report.errors.append(message)

    def _safe_root_label(self, label: str) -> str:
        name = label.strip()
        invalid = '<>:"/\\|?*'
        safe = "".join(
            "_" if char in invalid or ord(char) < 32 else char for char in name
        )
        safe = safe.rstrip(" .")
        return safe or "origen"
