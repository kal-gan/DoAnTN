# -*- mode: python ; coding: utf-8 -*-
"""
FireSmokeMonitor.spec
Cấu hình PyInstaller cho ứng dụng Fire/Smoke Detection.

Build:
    pyinstaller FireSmokeMonitor.spec --clean --noconfirm

Sau khi build xong, sản phẩm nằm trong: dist/FireSmokeMonitor/
File chạy:                 dist/FireSmokeMonitor/FireSmokeMonitor.exe

Lưu ý đóng gói:
- ``models/best.pt`` được gom theo exe (read-only).
- ``alerts/``, ``app_data.db``, ``.app_key`` KHÔNG nhúng — sẽ được tạo runtime
  cạnh exe (giữ dữ liệu người dùng tách khỏi binary).
- Build ra **thư mục** (onedir) thay vì onefile vì:
    * PyTorch + ultralytics ~2GB, onefile khởi động cực chậm (giải nén ra temp).
    * Antivirus ít cảnh báo hơn.
"""

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)
import os

block_cipher = None
PROJECT_ROOT = os.path.abspath(".")

# --- Dữ liệu đi kèm ----------------------------------------------------------
datas = []

# CHÚ Ý: best.pt KHÔNG nhúng vào bundle (PyInstaller v6 sẽ chôn vào _internal/
# khiến đường dẫn tương đối "models/best.pt" trong code không tìm thấy).
# Thay vào đó, sau khi build, chạy build_release.ps1 để copy ra cạnh exe.
if os.path.isfile(os.path.join(PROJECT_ROOT, "yolov8n.pt")):
    datas.append(("yolov8n.pt", "."))

# Ultralytics đi kèm các file config YAML, font, ... cần thu gom
datas += collect_data_files("ultralytics")
# Metadata để ultralytics đọc version qua importlib.metadata
datas += copy_metadata("ultralytics")
datas += copy_metadata("torch")
datas += copy_metadata("numpy")
datas += copy_metadata("opencv-python")

# --- Hidden imports ----------------------------------------------------------
hiddenimports = []
hiddenimports += collect_submodules("ultralytics")
hiddenimports += collect_submodules("torch")
hiddenimports += [
    "PIL._tkinter_finder",
    "cv2",
    "cryptography.hazmat.backends.openssl",
    "bcrypt",
    "sqlite3",
    "email.mime.multipart",
    "email.mime.text",
    "email.mime.image",
    "smtplib",
]

# --- Loại trừ để giảm kích thước --------------------------------------------
excludes = [
    "matplotlib.tests",
    "numpy.tests",
    "scipy.tests",
    "PyQt5", "PyQt6", "PySide2", "PySide6",  # không dùng Qt
    "notebook", "IPython", "jupyter",
    "tensorflow", "keras",
]

a = Analysis(
    ["app.py"],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FireSmokeMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # KHÔNG dùng UPX với torch (gây lỗi runtime)
    console=False,             # Tkinter GUI -> ẩn console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="app.ico" if os.path.isfile(os.path.join(PROJECT_ROOT, "app.ico")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FireSmokeMonitor",
)
