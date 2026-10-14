"""Servicio de copia segura: no sobrescribe ni elimina archivos existentes."""

import errno
import hashlib
import os
import shutil
from pathlib import Path

from backup_imagen.models import BackupConfig, BackupReport


class CopyService:
    """Copia imágenes a un destino preservando rutas relativas."""

    def __init__(self, config: BackupConfig) -> None:
        self._config = config

    def copy_one(self, source_file: Path, report: BackupReport) -> None:
        """Copia un archivo; registra el error y permite continuar con el siguiente."""
        try:
            relative = source_file.relative_to(self._config.source.resolve())
            target_directory = (
                self._config.destination / self._safe_device_name() / relative.parent
            )
            target_directory.mkdir(parents=True, exist_ok=True)
            target = self._available_target(target_directory / relative.name, source_file)
            if target is None:
                report.skipped_existing += 1
                return
            self._copy_atomically(source_file, target)
            report.copied += 1
        except (OSError, ValueError) as exc:
            report.failed += 1
            report.errors.append(f"{source_file}: {exc}")

    def _available_target(self, target: Path, source: Path) -> Path | None:
        if not target.exists():
            return target
        if self._same_content(target, source):
            return None

        stem, suffix = target.stem, target.suffix
        index = 1
        while True:
            candidate = target.with_name(f"{stem} (copia {index}){suffix}")
            if not candidate.exists():
                return candidate
            if self._same_content(candidate, source):
                return None
            index += 1

    def _copy_atomically(self, source: Path, target: Path) -> None:
        temporary = target.with_name(
            f".{target.name}.{os.getpid()}.backup-imagen-tmp"
        )
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=self._config.chunk_size)
                writer.flush()
                os.fsync(writer.fileno())

            # Un enlace duro publica el archivo completo sin reemplazar un destino
            # que haya aparecido concurrentemente. Algunos sistemas de archivos,
            # especialmente FAT32, no admiten enlaces duros.
            try:
                os.link(temporary, target)
                temporary.unlink()
            except OSError as exc:
                if target.exists():
                    raise FileExistsError(
                        f"El destino apareció durante la copia: {target}"
                    ) from exc
                unsupported = {
                    errno.EPERM,
                    errno.EXDEV,
                    errno.EOPNOTSUPP,
                    errno.ENOSYS,
                }
                if hasattr(errno, "ENOTSUP"):
                    unsupported.add(errno.ENOTSUP)
                if exc.errno not in unsupported:
                    raise
                self._publish_without_hard_links(temporary, target)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _publish_without_hard_links(self, temporary: Path, target: Path) -> None:
        """Alternativa exclusiva para sistemas de archivos sin enlaces duros."""
        try:
            with temporary.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=self._config.chunk_size)
                writer.flush()
                os.fsync(writer.fileno())
        except OSError:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _same_content(first: Path, second: Path) -> bool:
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

    def _safe_device_name(self) -> str:
        name = self._config.device_name.strip()
        invalid = '<>:"/\\|?*'
        safe = "".join(
            "_" if char in invalid or ord(char) < 32 else char for char in name
        )
        safe = safe.rstrip(" .")
        return safe or "DEVICE"
