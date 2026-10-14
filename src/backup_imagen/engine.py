"""Coordinación de descubrimiento y copia."""

from backup_imagen.copy_service import CopyService
from backup_imagen.image_scanner import ImageScanner
from backup_imagen.models import BackupConfig, BackupReport


class BackupEngine:
    """Ejecuta un respaldo de una raíz de origen a un destino."""

    def __init__(
        self,
        config: BackupConfig,
        scanner: ImageScanner | None = None,
        copier: CopyService | None = None,
    ) -> None:
        self._config = config
        self._scanner = scanner or ImageScanner()
        self._copier = copier or CopyService(config)

    def run(self) -> BackupReport:
        """Busca y copia imágenes accesibles, sin interrumpir por errores individuales."""
        source = self._config.source.resolve()
        destination = self._config.destination.resolve()
        if source == destination or source in destination.parents:
            raise ValueError("El destino no puede ser la carpeta de origen ni estar dentro de ella")

        report = BackupReport()
        for image_path in self._scanner.scan(source, excluded_root=destination):
            report.discovered += 1
            self._copier.copy_one(image_path, report)
        return report
