# Build with: python -m PyInstaller --noconfirm PriceRobot.spec
from pathlib import Path

root = Path(SPECPATH)
a = Analysis(
    [str(root / "desktop_entry.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "assets"), "assets")],   # header photos (and the icon)
    hiddenimports=["xlrd"],   # imported only when an old .xls file is opened
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "pandas", "scipy", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="RobotDePrecios", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
    version=str(root / "windows_version.txt"),
    icon=str(root / "assets" / "app_icon.ico"),
)
