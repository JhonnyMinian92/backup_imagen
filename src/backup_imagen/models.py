"""Modelos de dominio para el motor de respaldo."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BackupConfig:
    """Configuración inmutable de una operación de respaldo."""

    source: Path
    destination: Path
    device_name: str = "DEVICE"
    chunk_size: int = 1024 * 1024

    def __post_init__(self) -> None:
        if self.chunk_size < 4096:
            raise ValueError("chunk_size debe ser al menos 4096 bytes")
        if not self.device_name.strip():
            raise ValueError("device_name no puede estar vacío")


@dataclass(slots=True)
class BackupReport:
    """Resumen de los resultados de una operación."""

    discovered: int = 0
    copied: int = 0
    skipped_existing: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        """Indica si no se registraron errores."""
        return self.failed == 0
