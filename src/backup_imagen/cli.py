"""Interfaz de consola para respaldos manuales o automáticos."""

import argparse
import sys
from pathlib import Path

from backup_imagen.engine import BackupEngine
from backup_imagen.models import BackupConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backup-imagen",
        description="Respalda imágenes accesibles a la carpeta backup de un USB NTFS de 32 GB.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Carpeta de origen; si se omite, se recorren todas las unidades accesibles",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        help="Raíz montada del USB NTFS de 32 GB",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Espera la conexión de un USB NTFS de 32 GB y abre el respaldo automáticamente",
    )
    parser.add_argument(
        "--no-validate-usb",
        action="store_true",
        help="Omitir la validación de NTFS y capacidad (solo para desarrollo)",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.watch:
        if args.source is not None or args.destination is not None:
            parser.error("--watch no se combina con --source ni --destination")
        from backup_imagen.watcher import watch_for_usb

        try:
            watch_for_usb()
        except (OSError, RuntimeError) as exc:
            print(f"Error del monitor USB: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.destination is None:
        parser.error("indica --destination o usa --watch")

    try:
        config = BackupConfig(
            source=args.source,
            destination=args.destination,
            require_ntfs_32gb=not args.no_validate_usb,
        )
        print(f"Destino: {args.destination / 'backup'}", flush=True)
        report = BackupEngine(config, on_progress=lambda message: print(message, flush=True)).run()
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        if args.pause:
            try:
                input("\nPresiona Enter para cerrar esta ventana…")
            except EOFError:
                pass
        return 2

    print("\nResumen del respaldo")
    print(f"Imágenes encontradas: {report.discovered}")
    print(f"Copiadas:             {report.copied}")
    print(f"Omitidas:             {report.skipped_existing}")
    print(f"No procesadas:        {report.failed}")
    print(f"Errores de acceso:    {report.scan_errors}")
    for error in report.errors:
        print(f"  - {error}", file=sys.stderr)
    if args.pause:
        try:
            input("\nPresiona Enter para cerrar esta ventana…")
        except EOFError:
            pass
    return 0 if report.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
