"""Paths and child commands shared by source and standalone desktop builds."""
import os
from pathlib import Path
import sys
import tempfile


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
    # Never save user data in PyInstaller's temporary extraction directory.
    portable = Path(sys.executable).resolve().parent
    try:
        with tempfile.TemporaryFile(dir=portable):
            pass
        return portable
    except OSError:
        path = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "BAP Price Robot"
        path.mkdir(parents=True, exist_ok=True)
        return path


DATA_DIR = data_directory()


def cache_file(name, root=None):
    """Keep disposable data together; retain usable caches from older versions."""
    root = Path(root) if root is not None else DATA_DIR
    folder = root / "cache"
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / name
    legacy = root / name
    if legacy.is_file() and not destination.exists() and not any(Path(str(legacy) + suffix).exists() for suffix in ("-wal", "-shm")):
        try:
            legacy.replace(destination)
        except OSError:
            pass  # An older process may still have the disposable cache open.
    return destination


OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def worker_command():
    if is_frozen():
        return [sys.executable, "--worker"]
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return [str(executable), "-u", str(Path(__file__).resolve().with_name("robot_launcher.py"))]
