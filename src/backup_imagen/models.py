"""Modelos de dominio para el motor de respaldo."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BackupConfig:
    """Configuración de una operación de respaldo.

    ``source`` puede quedar vacío para recorrer todas las unidades accesibles del
    equipo. ``destination`` siempre es la raíz montada del USB.
    """

    source: Path | None
    destination: Path
    chunk_size: int = 1024 * 1024
    require_ntfs_32gb: bool = True

    def __post_init__(self) -> None:
        if self.chunk_size < 4096:
            raise ValueError("chunk_size debe ser al menos 4096 bytes")


@dataclass(slots=True)
class BackupReport:
    """Resumen de los resultados de una operación."""

    discovered: int = 0
    copied: int = 0
    skipped_existing: int = 0
    failed: int = 0
    scan_errors: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        """Indica si no se registraron errores."""
        return self.failed == 0 and self.scan_errors == 0
