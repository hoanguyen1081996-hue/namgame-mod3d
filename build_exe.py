# -*- coding: utf-8 -*-
"""Kịch bản đóng gói Mod3D_Standalone.exe độc lập bằng PyInstaller (tích hợp Auto-Updater)."""

import json
from pathlib import Path
import shutil
import tempfile
import PyInstaller.__main__

from auto_updater import DEFAULT_UPDATE_CONFIG


def build() -> Path:
    proj_dir = Path(__file__).resolve().parent
    work_dir = Path(tempfile.gettempdir()) / "mod3d_pyinstaller_build"
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)

    upd_cfg_file = proj_dir / "update_config.json"
    if not upd_cfg_file.exists():
        upd_cfg_file.write_text(
            json.dumps(DEFAULT_UPDATE_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    excludes = [
        "tkinter",
        "unittest",
        "pydoc",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "PIL",
        "pytest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtSql",
        "PySide6.QtTest",
    ]

    args = [
        str(proj_dir / "gui.py"),
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name=Mod3D_Standalone",
        f"--icon={proj_dir / 'app_icon.ico'}",
        f"--paths={proj_dir}",
        f"--add-data={proj_dir / 'data'};data",
        f"--add-data={proj_dir / 'app_icon.png'};.",
        f"--add-data={proj_dir / '_guard_catalog.json'};.",
        f"--add-data={upd_cfg_file};.",
        f"--distpath={proj_dir}",
        f"--workpath={work_dir}",
        f"--specpath={work_dir}",
    ]
    for mod in excludes:
        args.append(f"--exclude-module={mod}")

    PyInstaller.__main__.run(args)
    out_exe = proj_dir / "Mod3D_Standalone.exe"
    print(f"\n[BUILD OK] Đã xuất tệp: {out_exe}")
    return out_exe


if __name__ == "__main__":
    build()
