"""Coordinación de descubrimiento y copia."""

from collections.abc import Callable
from pathlib import Path

from backup_imagen.copy_service import CopyService
from backup_imagen.image_scanner import ImageScanner
from backup_imagen.models import BackupConfig, BackupReport
from backup_imagen.volumes import source_roots, validate_ntfs_32gb


class BackupEngine:
    """Recorre una carpeta indicada o todas las unidades accesibles."""

    def __init__(
        self,
        config: BackupConfig,
        scanner: ImageScanner | None = None,
        copier: CopyService | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        self._config = config
        self._scanner = scanner or ImageScanner()
        self._copier = copier or CopyService(config)
        self._on_progress = on_progress

    def run(self) -> BackupReport:
        """Copia imágenes accesibles a ``USB/backup`` sin detenerse por fallos parciales."""
        destination = self._config.destination.resolve()
        if self._config.require_ntfs_32gb:
            validate_ntfs_32gb(destination)

        if self._config.source is not None:
            source = self._config.source.resolve()
            if source == destination or destination in source.parents:
                raise ValueError("El destino no puede ser la carpeta de origen ni contenerla")
            roots = [(source, None)]
        else:
            roots = [
                (root.resolve(), label)
                for root, label in source_roots()
                if root.resolve() != destination
            ]

        self._copier.prepare_backup_root(destination)

        report = BackupReport()
        if not roots:
            report.scan_errors += 1
            self._record_error(report, "No se encontraron unidades de origen accesibles")
            return report

        for root, root_label in roots:
            if self._on_progress is not None:
                self._on_progress(f"Escaneando {root}…")
            if not root.exists() or not root.is_dir():
                report.scan_errors += 1
                self._record_error(report, f"No se puede recorrer la unidad de origen: {root}")
                continue

            def record_scan_error(exc: OSError, *, source_root: Path = root) -> None:
                report.scan_errors += 1
                self._record_error(report, f"{source_root}: {exc}")

            try:
                for image_path in self._scanner.scan(
                    root,
                    excluded_root=destination,
                    on_error=record_scan_error,
                ):
                    report.discovered += 1
                    self._copier.copy_one(image_path, root, report, root_label)
                    if self._on_progress is not None and report.discovered % 100 == 0:
                        self._on_progress(
                            f"Encontradas {report.discovered}; copiadas {report.copied}; "
                            f"omitidas {report.skipped_existing}; sin procesar {report.failed}; "
                            f"errores de acceso {report.scan_errors}"
                        )
            except (OSError, ValueError) as exc:
                report.scan_errors += 1
                self._record_error(report, f"{root}: {exc}")
        return report

    @staticmethod
    def _record_error(report: BackupReport, message: str) -> None:
        if len(report.errors) < 100:
            report.errors.append(message)
