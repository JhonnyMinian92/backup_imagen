"""Interfaz de consola."""

import argparse
import sys
from pathlib import Path

from backup_imagen.engine import BackupEngine
from backup_imagen.models import BackupConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backup-imagen",
        description="Copia imágenes a una memoria USB sin sobrescribir respaldos existentes.",
    )
    parser.add_argument("--source", required=True, type=Path, help="Carpeta de origen")
    parser.add_argument("--destination", required=True, type=Path, help="Carpeta de destino en el USB")
    parser.add_argument("--device-name", default="DEVICE", help="Etiqueta del dispositivo de origen")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        config = BackupConfig(
            source=args.source,
            destination=args.destination,
            device_name=args.device_name,
        )
        report = BackupEngine(config).run()
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nResumen del respaldo")
    print(f"Imágenes detectadas: {report.discovered}")
    print(f"Copiadas:            {report.copied}")
    print(f"Ya existentes:       {report.skipped_existing}")
    print(f"Errores:             {report.failed}")
    for error in report.errors:
        print(f"  - {error}", file=sys.stderr)
    return 0 if report.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
