"""Punto de entrada para el monitor de Windows."""

from backup_imagen.watcher import watch_for_usb


def main() -> int:
    watch_for_usb()
    return 0
