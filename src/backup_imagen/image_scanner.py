"""Descubrimiento recursivo de imágenes sin abrir ni modificar sus contenidos."""

from collections.abc import Iterator
from pathlib import Path

IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg", ".jpeg", ".jpe", ".png", ".gif", ".bmp", ".webp",
        ".heic", ".heif", ".tif", ".tiff", ".raw", ".dng",
        ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2",
        ".orf", ".rw2", ".raf", ".pef", ".3fr", ".iiq", ".kdc",
        ".dcr", ".mos", ".mrw", ".x3f", ".erf", ".mef", ".rwl",
        ".srw", ".jxr", ".wdp", ".avif",
    }
)


class ImageScanner:
    """Recorre una raíz y devuelve imágenes según su extensión."""

    def __init__(self, extensions: frozenset[str] = IMAGE_EXTENSIONS) -> None:
        self._extensions = frozenset(ext.lower() for ext in extensions)

    def scan(self, root: Path, excluded_root: Path | None = None) -> Iterator[Path]:
        """Produce rutas de archivos de imagen, sin seguir enlaces simbólicos."""
        if not root.exists():
            raise FileNotFoundError(f"No existe la carpeta de origen: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"El origen no es una carpeta: {root}")

        excluded = self._resolved_or_none(excluded_root)
        for current, directories, filenames in self._walk(root):
            current_path = Path(current)
            directories[:] = sorted(
                name
                for name in directories
                if not (current_path / name).is_symlink()
                and not self._is_excluded(current_path / name, excluded)
            )
            for filename in sorted(filenames):
                candidate = current_path / filename
                if candidate.is_symlink() or candidate.suffix.lower() not in self._extensions:
                    continue
                if self._is_excluded(candidate, excluded):
                    continue
                if candidate.is_file():
                    yield candidate

    @staticmethod
    def _walk(root: Path):
        import os

        return os.walk(root, topdown=True, followlinks=False)

    @staticmethod
    def _resolved_or_none(path: Path | None) -> Path | None:
        if path is None:
            return None
        try:
            return path.resolve()
        except OSError:
            return path.absolute()

    @classmethod
    def _is_excluded(cls, path: Path, excluded: Path | None) -> bool:
        if excluded is None:
            return False
        resolved = cls._resolved_or_none(path)
        if resolved is None:
            return False
        try:
            resolved.relative_to(excluded)
            return True
        except ValueError:
            return False
