"""Single executable entry point for the desktop UI and its background worker."""
import json
import os
from pathlib import Path
import sys
import traceback


def worker_output():
    """Windowed bootloaders set sys.stdout=None, even when a pipe is inherited."""
    if sys.stdout is None and sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        import msvcrt
        get_handle = ctypes.windll.kernel32.GetStdHandle
        get_handle.argtypes = [wintypes.DWORD]
        get_handle.restype = wintypes.HANDLE
        handle = get_handle(wintypes.DWORD(-11))
        if handle and handle != ctypes.c_void_p(-1).value:
            descriptor = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
            sys.stdout = os.fdopen(descriptor, "w", encoding="utf-8", errors="replace", buffering=1)
    if sys.stdout is None:
        from app_runtime import DATA_DIR
        sys.stdout = open(DATA_DIR / "worker.log", "a", encoding="utf-8", buffering=1)
    sys.stderr = sys.stdout


def self_test(report):
    """Offline packaging check, including the real frozen child-process route."""
    import subprocess
    import tkinter as tk
    import requests
    import openpyxl
    import xlrd        # old .xls input files
    import certifi
    import table_files
    from app_runtime import DATA_DIR, worker_command
    import price_robot_ui
    from store_parsers import available_stores
    # Import optional-on-use desktop modules so missing packaging hooks fail here.
    import candidate_review_ui
    import candidate_store
    import excel_export
    import price_review_ui
    price_robot_ui.load_code_defaults()
    root = tk.Tk()
    root.withdraw()
    try:
        app = price_robot_ui.App(root)
        root.update_idletasks()
        result = subprocess.run(worker_command() + ["--list-stores"], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", timeout=60,
                                creationflags=price_robot_ui.no_window_flags())
        if result.returncode or any(store not in result.stdout for store in available_stores()):
            raise RuntimeError(f"Worker smoke test failed: {result.returncode}: {result.stdout}")
        Path(report).write_text(json.dumps({"ok": True, "frozen": bool(getattr(sys, "frozen", False)),
            "data_directory": str(DATA_DIR), "tk": root.tk.call("info", "patchlevel"),
            "requests": requests.__version__, "openpyxl": openpyxl.__version__,
            "certificates_present": Path(certifi.where()).is_file(), "stores": available_stores(),
            "worker_output": result.stdout}, indent=2), encoding="utf-8")
    finally:
        root.destroy()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        del sys.argv[1]
        worker_output()
        import robot_launcher
        robot_launcher.main()
    elif len(sys.argv) > 2 and sys.argv[1] == "--self-test":
        report = Path(sys.argv[2]).resolve()
        try:
            self_test(report)
        except Exception:
            report.write_text(json.dumps({"ok": False, "error": traceback.format_exc()}, indent=2), encoding="utf-8")
            raise
    else:
        import price_robot_ui
        price_robot_ui.main()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        from app_runtime import DATA_DIR
        with open(DATA_DIR / "ui_errors.log", "a", encoding="utf-8") as stream:
            stream.write(traceback.format_exc() + "\n")
        if "--self-test" not in sys.argv and sys.stdout is None:
            import tkinter.messagebox
            tkinter.messagebox.showerror("Robot de Precios", f"No se pudo iniciar / Could not start.\n{DATA_DIR / 'ui_errors.log'}")
        raise
