"""Descubrimiento recursivo de imágenes sin abrir ni modificar sus contenidos."""

import os
import stat
from collections.abc import Callable, Iterator
from pathlib import Path

IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg", ".jpeg", ".jpe", ".jfif", ".jif", ".jfi", ".png", ".gif", ".bmp", ".dib", ".webp",
        ".heic", ".heics", ".heif", ".heifs", ".hif", ".tif", ".tiff", ".raw", ".dng", ".ico",
        ".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sraf", ".sr2",
        ".orf", ".rw2", ".raf", ".pef", ".3fr", ".iiq", ".kdc",
        ".dcr", ".mos", ".mrw", ".x3f", ".erf", ".mef", ".rwl",
        ".srw", ".ari", ".bay", ".cap", ".dcs", ".drf", ".eip",
        ".fff", ".gpr", ".k25", ".mdc", ".obm", ".ptx", ".pxn",
        ".r3d", ".rwz", ".avif", ".avifs", ".svg", ".svgz", ".ai", ".eps", ".epsf", ".epsi",
        ".cdr", ".psd", ".psb", ".pdf",
    }
)


class ImageScanner:
    """Recorre una raíz y devuelve imágenes según su extensión."""

    def __init__(self, extensions: frozenset[str] = IMAGE_EXTENSIONS) -> None:
        self._extensions = frozenset(ext.lower() for ext in extensions)

    def scan(
        self,
        root: Path,
        excluded_root: Path | None = None,
        on_error: Callable[[OSError], None] | None = None,
    ) -> Iterator[Path]:
        """Produce archivos admitidos y comunica errores de recorrido al llamador."""
        try:
            root = Path(root).resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"No se pudo resolver la carpeta de origen {root}: {exc}") from exc
        if not root.exists():
            raise FileNotFoundError(f"No existe la carpeta de origen: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"El origen no es una carpeta: {root}")

        excluded = self._resolved_or_none(excluded_root)
        for current, directories, filenames in self._walk(root, on_error):
            current_path = Path(current).resolve(strict=False)
            if root == Path("/") and current_path == root:
                directories[:] = [
                    name for name in directories if name not in {"proc", "sys", "dev"}
                ]
            elif root == Path("/") and current_path == Path("/run"):
                # Desktop Linux commonly mounts removable media under /run/media.
                # Keep that mount subtree but avoid traversing transient runtime files.
                directories[:] = [name for name in directories if name == "media"]
                filenames.clear()
            directories[:] = sorted(
                name
                for name in directories
                if not self._is_link_or_junction(current_path / name)
                and not self._is_excluded(current_path / name, excluded)
            )
            for filename in sorted(filenames):
                candidate = current_path / filename
                if candidate.is_symlink() or candidate.suffix.lower() not in self._extensions:
                    continue
                if self._is_excluded(candidate, excluded):
                    continue
                try:
                    if candidate.is_file():
                        yield candidate
                except OSError as exc:
                    if on_error is not None:
                        on_error(exc)

    @staticmethod
    def _walk(root: Path, on_error: Callable[[OSError], None] | None = None):
        import os

        return os.walk(root, topdown=True, onerror=on_error, followlinks=False)

    @staticmethod
    def _resolved_or_none(path: Path | None) -> Path | None:
        if path is None:
            return None
        try:
            return path.resolve()
        except RuntimeError as exc:
            raise ValueError(f"La ruta contiene un enlace cíclico: {path}") from exc
        except OSError:
            return path.absolute()

    @staticmethod
    def _is_link_or_junction(path: Path) -> bool:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        # Path.is_junction() was added in Python 3.12, while this project supports
        # Python 3.10+. On older Windows versions, inspect the reparse-point bit
        # directly so junctions cannot make os.walk leave the source tree or loop.
        if os.name == "nt":
            try:
                attributes = path.lstat().st_file_attributes
            except (AttributeError, OSError):
                return False
            reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            return bool(attributes & reparse_point)
        return False

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
