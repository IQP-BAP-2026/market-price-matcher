"""Paths and child commands shared by source and standalone desktop builds."""
import os
from pathlib import Path
import sys
import tempfile

APP_FOLDER_NAME = "Robot de Precios"   # %LOCALAPPDATA%\Robot de Precios (app) and Documents\Robot de Precios (results)
CACHE_FOLDER_NAME = "caché"           # disposable data; safe to delete
RESULTS_FOLDER_NAME = "resultados"    # default results folder when running from source


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def data_directory():
    override = os.environ.get("BAP_ROBOT_DATA_DIR")
    if override:
        path = Path(override).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    if not is_frozen():
        return Path(__file__).resolve().parent
    # Never save user data in PyInstaller's temporary extraction directory. The installer puts the
    # executable in %LOCALAPPDATA%\Robot de Precios, so settings, caches and logs sit beside it there.
    portable = Path(sys.executable).resolve().parent
    try:
        with tempfile.TemporaryFile(dir=portable):
            pass
        return portable
    except OSError:
        path = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP_FOLDER_NAME
        path.mkdir(parents=True, exist_ok=True)
        return path


DATA_DIR = data_directory()


def cache_file(name, root=None):
    """Keep disposable data together; retain usable caches from older versions."""
    root = Path(root) if root is not None else DATA_DIR
    folder = root / CACHE_FOLDER_NAME
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / name
    legacy = root / name
    if legacy.is_file() and not destination.exists() and not any(Path(str(legacy) + suffix).exists() for suffix in ("-wal", "-shm")):
        try:
            legacy.replace(destination)
        except OSError:
            pass  # An older process may still have the disposable cache open.
    return destination


def documents_folder():
    """The user's real Documents folder (it may be moved, e.g. into OneDrive), or None if unknown."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            import uuid

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                            ("Data4", ctypes.c_ubyte * 8)]

            raw = uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}").bytes_le   # FOLDERID_Documents
            folder_id = GUID.from_buffer_copy(raw)
            buffer = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(buffer)) == 0:
                try:
                    return Path(buffer.value)
                finally:
                    ctypes.windll.ole32.CoTaskMemFree(buffer)
        except Exception:
            pass
    home = Path.home() / "Documents"
    return home if home.is_dir() else None


def output_directory():
    """Where results are saved by default: Documents\\Robot de Precios for the installed app;
    the project's resultados/ folder when running from source (or when a data folder is forced)."""
    if is_frozen() and not os.environ.get("BAP_ROBOT_DATA_DIR"):
        documents = documents_folder()
        if documents is not None:
            path = documents / APP_FOLDER_NAME
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except OSError:
                pass
    return DATA_DIR / RESULTS_FOLDER_NAME


OUTPUT_DIR = output_directory()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def worker_command():
    if is_frozen():
        return [sys.executable, "--worker"]
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return [str(executable), "-u", str(Path(__file__).resolve().with_name("robot_launcher.py"))]
