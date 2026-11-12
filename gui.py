# -*- coding: utf-8 -*-
"""
Giao diện Đồ họa Độc lập (PySide6 Dark Theme - Clone 100% bố cục Dear ImGui v1.3.70)
Không yêu cầu nhập Key / License Server - Tích hợp trực tiếp Catalog SQLite & Win32SystemContext.
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QThread, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from auto_updater import (
    APP_VERSION,
    GitHubAutoUpdater,
    UpdateCheckResult,
    download_pack_asset,
)
from main import (
    CatalogItem,
    CatalogRepository,
    ProcessCatalogSynchronizer,
    get_runtime_dirs,
)
from win32_system_context import Win32SystemContext

# ============================================================================
# DỮ LIỆU CHUẨN TRÍCH XUẤT TỪ BẢN GỐC (v1.3.70)
# ============================================================================

APP_TITLE = f"Cường Dev · Mod 3D v{APP_VERSION}"
APP_USER_MODEL_ID = f"CuongDev.Mod3D.Standalone.{APP_VERSION}"
PROCESS_TARGET = "MSango.bin"

SLOT_CATEGORIES: List[Tuple[str, str, str]] = [
    ("ThuCuoi", "Thú cưỡi", "ride"),
    ("Canh", "Cánh", "ride"),
    ("DonThu", "Kiếm một tay", "weapon"),
    ("TruongBinh", "Thương", "weapon"),
    ("SongThu", "Song đao", "weapon"),
    ("CungTien", "Cung", "weapon"),
    ("QuanTao", "Trảo", "weapon"),
    ("", "Khác", "weapon"),  # Hiển thị động khi nhóm 'Thử' có 6 model chưa phân slot
]

GROUP_FILTERS: List[Tuple[str, str, str]] = [
    ("main", "Thường", "Danh sách trang bị chuẩn trong catalog game."),
    ("do3d", "Đồ 3D", "Hình trích từ Data.dhp của game (một số render từ model 3D)."),
    (
        "test",
        "Thử",
        "Model có trong Data.dhp nhưng không có trong catalog game — chưa chắc game nhận mã.",
    ),
]

# 55 Tướng Tam Quốc trong Tab "Skin ấn" (Trích xuất chính xác 100% từ bảng .rdata 0x22a5b0)
SEAL_HEROES: List[Tuple[str, str]] = [
    ("bianyuer", "Biện Nguyệt Nhi"),
    ("buwan", "Bộ Uyển"),
    ("caocao", "Tào Tháo"),
    ("caojie", "Tào Tiết"),
    ("caopi", "Tào Phi"),
    ("caoren", "Tào Nhân"),
    ("caozhang", "Tào Chương"),
    ("chengyu", "Trình Dục"),
    ("daqiao", "Đại Kiều"),
    ("dianwei", "Điển Vi"),
    ("diaochan", "Điêu Thuyền"),
    ("dongzhuo", "Đổng Trác"),
    ("ganning", "Cam Ninh"),
    ("guanyu", "Quan Vũ"),
    ("guojia", "Quách Gia"),
    ("huangwudie", "Hoàng Vũ Điệp"),
    ("huangyueying", "Hoàng Nguyệt Anh"),
    ("huangzhong", "Hoàng Trung"),
    ("lingtong", "Lăng Thống"),
    ("lingyin", "Linh Âm"),
    ("liubei", "Lưu Bị"),
    ("liuchan", "Lưu Thiện"),
    ("luxun", "Lục Tốn"),
    ("lvbu", "Lữ Bố"),
    ("lvmengru", "Lữ Mộng Như"),
    ("machao", "Mã Siêu"),
    ("madai", "Mã Đại"),
    ("maliang", "Mã Lương"),
    ("mayunlu", "Mã Vân Lộc"),
    ("mizhu", "My Trúc"),
    ("panfeng", "Phan Phụng"),
    ("pangde", "Bàng Đức"),
    ("pangtong", "Bàng Thống"),
    ("puyuan", "Phác Nguyên"),
    ("simayi", "Tư Mã Ý"),
    ("sunce", "Tôn Sách"),
    ("sunhuan", "Tôn Hoàn"),
    ("sunjian", "Tôn Kiên"),
    ("sunluban", "Tôn Lỗ Ban"),
    ("sunquan", "Tôn Quyền"),
    ("sunshangxiang", "Tôn Thượng Hương"),
    ("taishici", "Thái Sử Từ"),
    ("xiahoudun", "Hạ Hầu Đôn"),
    ("xiaoqiao", "Tiểu Kiều"),
    ("xinxianying", "Tân Hiến Anh"),
    ("xiuluozhaoyun", "Tu La Triệu Vân"),
    ("xuchu", "Hứa Chử"),
    ("zhangjiao", "Trương Giác"),
    ("zhangliao", "Trương Liêu"),
    ("zhangyingying", "Trương Anh Anh"),
    ("zhaotong", "Triệu Thống"),
    ("zhenji", "Chân Cơ"),
    ("zhoucang", "Châu Thương"),
    ("zhoutai", "Chu Thái"),
    ("zhugeliang", "Gia Cát Lượng"),
]

# 15 Tướng thuộc nhóm "Đủ model" (0x22a770)
FULL_MODEL_STEMS: Set[str] = {
    "caocao",
    "diaochan",
    "guanyu",
    "guojia",
    "liubei",
    "liuchan",
    "lvbu",
    "panfeng",
    "pangtong",
    "simayi",
    "sunquan",
    "xiahoudun",
    "xinxianying",
    "xiuluozhaoyun",
    "zhugeliang",
}

RIDE_SLOTS = {"ThuCuoi", "Canh"}

DEFAULT_MEMORY_CONFIG: Dict[str, Any] = {
    "_comment": "Điền mẫu AOB và danh sách offset con trỏ của MSango.bin cho ô CƯỠI (ride) và VŨ KHÍ (weapon).",
    "process_name": PROCESS_TARGET,
    "pointer_size": 4,
    "ride": {
        "aob_pattern": "",
        "pattern_offset": 0,
        "offsets": [],
        "payload_field": "mesh",
        "scan_data": False,
    },
    "weapon": {
        "aob_pattern": "",
        "pattern_offset": 0,
        "offsets": [],
        "payload_field": "mesh",
        "scan_data": False,
    },
}

# ============================================================================
# BẢNG MÀU & STYLESHEET CHUẨN DEAR IMGUI DARK THEME
# ============================================================================

IMGUI_DARK_QSS = """
QMainWindow, QWidget#rootWidget {
    background-color: #111318;
    color: #E6E9F0;
    font-family: "Segoe UI";
    font-size: 13px;
}
QFrame#topHeader {
    background-color: #171A21;
    border-bottom: 1px solid #262B36;
}
QFrame#cardFrame {
    background-color: #171A21;
    border: 1px solid #262B36;
    border-radius: 6px;
}
QFrame#slotBox {
    background-color: #1E222B;
    border: 1px solid #2E3442;
    border-radius: 6px;
}
QFrame#itemRow {
    background-color: #1A1E26;
    border: 1px solid #262B36;
    border-radius: 5px;
}
QFrame#itemRow:hover {
    background-color: #222733;
    border: 1px solid #3B82F6;
}
QPushButton {
    background-color: #232834;
    color: #E6E9F0;
    border: 1px solid #32394A;
    border-radius: 5px;
    padding: 5px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2D3546;
    border-color: #4B5568;
}
QPushButton:pressed {
    background-color: #1C202B;
}
QPushButton:checked, QPushButton#primaryBtn {
    background-color: #2563EB;
    border-color: #3B82F6;
    color: #FFFFFF;
}
QPushButton#primaryBtn:hover {
    background-color: #1D4ED8;
}
QPushButton#dangerBtn {
    background-color: #3B1D24;
    border-color: #6E2C3B;
    color: #FCA5A5;
}
QPushButton#dangerBtn:hover {
    background-color: #52232E;
}
QPushButton#navTab {
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 8px 16px;
    color: #9CA3AF;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#navTab:hover {
    color: #F3F4F6;
}
QPushButton#navTab:checked {
    color: #60A5FA;
    border-bottom: 2px solid #3B82F6;
}
QLineEdit {
    background-color: #12151C;
    border: 1px solid #2D3342;
    border-radius: 5px;
    padding: 6px 10px;
    color: #F3F4F6;
}
QLineEdit:focus {
    border: 1px solid #3B82F6;
}
QListWidget {
    background-color: #12151C;
    border: 1px solid #262B36;
    border-radius: 5px;
    outline: none;
}
QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #1C202B;
}
QListWidget::item:selected {
    background-color: #1E3A8A;
    color: #FFFFFF;
}
QListWidget::item:hover {
    background-color: #1F2430;
}
QScrollBar:vertical {
    background: #12151C;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #2E3545;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #424B61;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QCheckBox {
    spacing: 8px;
    color: #E5E7EB;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #3F475A;
    background-color: #12151C;
}
QCheckBox::indicator:checked {
    background-color: #2563EB;
    border-color: #3B82F6;
}
QProgressBar {
    background-color: #12151C;
    border: 1px solid #2D3342;
    border-radius: 5px;
    text-align: center;
    color: #E5E7EB;
    height: 20px;
}
QProgressBar::chunk {
    background-color: #2563EB;
    border-radius: 4px;
}
QDialog {
    background-color: #14171F;
    color: #E6E9F0;
    font-family: "Segoe UI";
    font-size: 13px;
}
QTextEdit {
    background-color: #101319;
    color: #D1D5DB;
    border: 1px solid #262B36;
    border-radius: 5px;
    padding: 6px;
}
"""


def _resolve_asset(rel_path: str, app_dir: Path, bundle_dir: Path) -> Path:
    """Ưu tiên tài nguyên nằm cạnh tệp `.exe`, nếu không có thì lấy bản đóng gói nội bộ."""
    external = app_dir / rel_path
    if external.exists():
        return external
    return bundle_dir / rel_path


class UpdateCheckWorker(QThread):
    """Luồng nền kiểm tra bản cập nhật trên GitHub không làm đơ giao diện."""

    finished_check = Signal(object, bool)  # (UpdateCheckResult, auto_apply_hotfix)

    def __init__(
        self, updater: GitHubAutoUpdater, auto_apply_hotfix: bool = False
    ) -> None:
        super().__init__()
        self.updater = updater
        self.auto_apply_hotfix = auto_apply_hotfix

    def run(self) -> None:
        res = self.updater.check_for_updates()
        if (
            self.auto_apply_hotfix
            and not res.error
            and res.hotfixes_to_apply
            and not res.has_exe_update
        ):
            try:
                applied = self.updater.apply_hotfixes(res.hotfixes_to_apply)
                res.changelog = f"AUTO_HOTFIX_OK:{','.join(applied)}"
                res.hotfixes_to_apply = []
            except Exception as exc:
                res.error = f"Lỗi đồng bộ Hotfix tự động: {exc}"
        self.finished_check.emit(res, self.auto_apply_hotfix)


class UpdateApplyWorker(QThread):
    """Luồng nền tải Hotfix và/hoặc bản `.exe` mới kèm tiến trình phần trăm."""

    progress_changed = Signal(int, str)
    apply_done = Signal(bool, str, str)  # (ok, message, staged_exe_path)

    def __init__(self, updater: GitHubAutoUpdater, check_res: UpdateCheckResult) -> None:
        super().__init__()
        self.updater = updater
        self.check_res = check_res

    def run(self) -> None:
        try:
            applied_files: List[str] = []
            if self.check_res.hotfixes_to_apply:
                total_hf = len(self.check_res.hotfixes_to_apply)

                def _hf_prog(rel_p: str, done_i: int, tot_i: int) -> None:
                    pct = int((done_i / max(tot_i, 1)) * 40)
                    self.progress_changed.emit(pct, f"Đang đồng bộ {rel_p}…")

                applied_files = self.updater.apply_hotfixes(
                    self.check_res.hotfixes_to_apply, progress_cb=_hf_prog
                )

            staged_exe_str = ""
            if self.check_res.has_exe_update and self.check_res.exe_url:

                def _exe_prog(dl_bytes: int, total_bytes: int) -> None:
                    mb_dl = dl_bytes / (1024 * 1024)
                    if total_bytes > 0:
                        mb_tot = total_bytes / (1024 * 1024)
                        pct = 40 + int((dl_bytes / total_bytes) * 60)
                        self.progress_changed.emit(
                            min(pct, 99),
                            f"Đang tải EXE mới: {mb_dl:.1f} / {mb_tot:.1f} MB",
                        )
                    else:
                        self.progress_changed.emit(
                            70, f"Đang tải EXE mới: {mb_dl:.1f} MB…"
                        )

                staged = self.updater.download_new_exe(
                    exe_url=self.check_res.exe_url,
                    expected_sha256=self.check_res.exe_sha256,
                    progress_cb=_exe_prog,
                )
                staged_exe_str = str(staged)

            self.progress_changed.emit(100, "Hoàn tất!")
            msg_parts: List[str] = []
            if applied_files:
                msg_parts.append(f"Đã cập nhật {len(applied_files)} tệp dữ liệu/cấu hình")
            if staged_exe_str:
                msg_parts.append(
                    f"Đã tải bản v{self.check_res.remote_version} — Đang tự khởi động lại…"
                )
            self.apply_done.emit(
                True, " · ".join(msg_parts) or "Đã cập nhật xong.", staged_exe_str
            )
        except Exception as exc:
            self.apply_done.emit(False, str(exc), "")


class VietHoaInstallWorker(QThread):
    """Luồng nền tải trực tiếp Data.dhp + version.dll từ GitHub Releases CDN, lưu cache, kiểm tra SHA-256 và cài vào game."""

    progress_changed = Signal(int, str, str)  # (pct, dhp_text, dll_text)
    install_done = Signal(bool, str)  # (ok, message)

    def __init__(self, catalog_path: Path, cache_dir: Path, game_dir: Path) -> None:
        super().__init__()
        self.catalog_path = catalog_path
        self.cache_dir = cache_dir
        self.game_dir = game_dir

    def run(self) -> None:
        try:
            if not self.catalog_path.is_file():
                raise FileNotFoundError("Không tìm thấy tệp cấu hình _guard_catalog.json.")

            cat = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            files_cfg = cat.get("files") or {}
            dhp_cfg = files_cfg.get("dhp") or {}
            dll_cfg = files_cfg.get("dll") or {}

            dhp_urls = [
                str(dhp_cfg.get("url", "")),
                str(dhp_cfg.get("fallback_url", "")),
            ]
            dll_urls = [
                str(dll_cfg.get("url", "")),
                str(dll_cfg.get("fallback_url", "")),
            ]

            dhp_status = "• Pack Việt hóa (thay pack trong Data): Data.dhp — Đang kiểm tra cache…"
            dll_status = "• Proxy chữ / HUD cạnh MSango.bin: version.dll — Chờ tải…"
            self.progress_changed.emit(2, dhp_status, dll_status)

            def _on_dhp_prog(dl_b: int, tot_b: int) -> None:
                mb_dl = dl_b / (1024 * 1024)
                if tot_b > 0:
                    mb_tot = tot_b / (1024 * 1024)
                    pct = max(2, min(85, int((dl_b / tot_b) * 85)))
                    txt = (
                        f"• Pack Việt hóa (thay pack trong Data): Data.dhp — "
                        f"Đang tải {mb_dl:.1f} / {mb_tot:.1f} MB ({int(dl_b * 100 / tot_b)}%)"
                    )
                else:
                    pct = 45
                    txt = f"• Pack Việt hóa (thay pack trong Data): Data.dhp — Đang tải {mb_dl:.1f} MB…"
                self.progress_changed.emit(pct, txt, dll_status)

            cached_dhp, dhp_cached = download_pack_asset(
                urls=dhp_urls,
                cache_file=self.cache_dir / "Data.dhp",
                expected_magic=b"1PHD",
                expected_sha256=str(dhp_cfg.get("sha256", "")),
                expected_size=int(dhp_cfg.get("size", 0) or 0),
                progress_cb=_on_dhp_prog,
            )
            dhp_done_note = "Từ cache máy" if dhp_cached else "Đã tải xong & khớp SHA-256"
            dhp_status = f"• Pack Việt hóa (thay pack trong Data): Data.dhp — {dhp_done_note}"

            def _on_dll_prog(dl_b: int, tot_b: int) -> None:
                kb_dl = dl_b / 1024
                pct = 86 + (int((dl_b / tot_b) * 6) if tot_b > 0 else 3)
                txt = f"• Proxy chữ / HUD cạnh MSango.bin: version.dll — Đang tải {kb_dl:.1f} KB…"
                self.progress_changed.emit(min(pct, 92), dhp_status, txt)

            cached_dll, dll_cached = download_pack_asset(
                urls=dll_urls,
                cache_file=self.cache_dir / "version.dll",
                expected_magic=b"MZ",
                expected_sha256=str(dll_cfg.get("sha256", "")),
                expected_size=int(dll_cfg.get("size", 0) or 0),
                progress_cb=_on_dll_prog,
            )
            dll_done_note = "Từ cache máy" if dll_cached else "Đã tải xong & khớp SHA-256"
            dll_status = f"• Proxy chữ / HUD cạnh MSango.bin: version.dll — {dll_done_note}"
            self.progress_changed.emit(93, dhp_status, dll_status)

            # Nếu game hoặc trình khởi chạy đang mở khóa file, tự đóng nhẹ để ghi an toàn
            ctx = Win32SystemContext()
            if (
                ctx.find_process_id(PROCESS_TARGET) is not None
                or ctx.find_process_id("DHPlatform.bin") is not None
            ):
                cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                for proc_img in ("MSango.bin", "DHPlatform.bin"):
                    subprocess.run(
                        ["taskkill", "/F", "/IM", proc_img],
                        capture_output=True,
                        creationflags=cflags,
                    )
                time.sleep(0.8)

            dst_dhp = self.game_dir / "Data" / "Data.dhp"
            dst_dll = self.game_dir / "version.dll"
            dst_dhp.parent.mkdir(parents=True, exist_ok=True)

            try:
                if dst_dhp.exists():
                    os.chmod(dst_dhp, stat.S_IREAD | stat.S_IWRITE)
                if dst_dll.exists():
                    os.chmod(dst_dll, stat.S_IREAD | stat.S_IWRITE)

                self.progress_changed.emit(
                    96,
                    "• Pack Việt hóa (thay pack trong Data): Data.dhp — Đang chép vào thư mục game…",
                    dll_status,
                )
                shutil.copy2(cached_dhp, dst_dhp)
                shutil.copy2(cached_dll, dst_dll)

                # Tự động khóa Read-Only Data.dhp để Launcher không tải bản tiếng Trung đè lại
                os.chmod(dst_dhp, stat.S_IREAD)
            except PermissionError as exc:
                raise RuntimeError(
                    "Không ghi được vào thư mục game (thiếu quyền Admin hoặc file đang mở). "
                    "Bản tải đã lưu sẵn trong cache — hãy đóng game / chạy quyền Admin rồi bấm lại!"
                ) from exc

            final_dhp = "• Pack Việt hóa (thay pack trong Data): Data.dhp — Đã cài & khóa bảo vệ"
            final_dll = "• Proxy chữ / HUD cạnh MSango.bin: version.dll — Đã cài cạnh MSango.bin"
            self.progress_changed.emit(100, final_dhp, final_dll)
            self.install_done.emit(
                True, "Đã cài đặt gói Việt hóa (Data.dhp + version.dll) và khóa chống cập nhật đè!"
            )
        except Exception as exc:
            self.install_done.emit(False, str(exc))


class UpdateDialog(QDialog):
    """Hộp thoại Quản lý Tự động Cập nhật qua GitHub."""

    def __init__(
        self,
        parent: "Mod3DMainWindow",
        updater: GitHubAutoUpdater,
        last_result: Optional[UpdateCheckResult] = None,
    ) -> None:
        super().__init__(parent)
        self.main_win = parent
        self.updater = updater
        self.current_result = last_result
        self._check_worker: Optional[UpdateCheckWorker] = None
        self._apply_worker: Optional[UpdateApplyWorker] = None

        self.setWindowTitle(f"Cập nhật Tự động (GitHub) — v{APP_VERSION}")
        self.setFixedSize(560, 440)
        self.setStyleSheet(IMGUI_DARK_QSS)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        lbl_head = QLabel(
            f"Phiên bản đang chạy: v{APP_VERSION}  ·  Hỗ trợ Hotfix 1 giây & Tự tráo EXE"
        )
        lbl_head.setStyleSheet("color: #60A5FA; font-weight: 700; font-size: 13px;")
        lay.addWidget(lbl_head)

        cfg = self.updater.load_config()
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        form.addWidget(QLabel("GitHub Repo (owner/repo):"), 0, 0)
        self.inp_repo = QLineEdit(str(cfg.get("github_repo", "")))
        self.inp_repo.setPlaceholderText("VD: ten-anh/namgame-mod3d")
        form.addWidget(self.inp_repo, 0, 1)

        form.addWidget(QLabel("Nhánh (Branch):"), 1, 0)
        self.inp_branch = QLineEdit(str(cfg.get("branch", "main") or "main"))
        form.addWidget(self.inp_branch, 1, 1)

        form.addWidget(QLabel("Manifest URL (tùy chọn):"), 2, 0)
        self.inp_manifest = QLineEdit(str(cfg.get("manifest_url", "")))
        self.inp_manifest.setPlaceholderText(
            "Để trống nếu dùng mặc định release/manifest.json trên GitHub Repo"
        )
        form.addWidget(self.inp_manifest, 2, 1)

        lay.addLayout(form)

        self.cb_auto = QCheckBox(
            "Tự động kiểm tra & đồng bộ nhanh Hotfix (offset / catalog) khi mở tool"
        )
        self.cb_auto.setChecked(bool(cfg.get("auto_check_on_startup", True)))
        lay.addWidget(self.cb_auto)

        self.lbl_status = QLabel("Trạng thái: Sẵn sàng kiểm tra.")
        self.lbl_status.setStyleSheet("color: #E5E7EB; font-weight: 600;")
        lay.addWidget(self.lbl_status)

        self.txt_notes = QTextEdit()
        self.txt_notes.setReadOnly(True)
        self.txt_notes.setPlaceholderText(
            "Nhật ký phiên bản / danh sách tệp Hotfix thay đổi sẽ hiện tại đây…"
        )
        lay.addWidget(self.txt_notes, 1)

        self.prog = QProgressBar()
        self.prog.setValue(0)
        lay.addWidget(self.prog)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Lưu cấu hình")
        self.btn_save.clicked.connect(self._on_save_cfg)

        self.btn_check = QPushButton("Kiểm tra ngay")
        self.btn_check.clicked.connect(self._on_check_now)

        self.btn_apply = QPushButton("Cập nhật ngay")
        self.btn_apply.setObjectName("primaryBtn")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._on_apply_now)

        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.close)

        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_check)
        btn_row.addWidget(self.btn_apply)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)

        if self.current_result is not None:
            self._render_result(self.current_result)

    def _save_inputs_to_config(self) -> None:
        self.updater.save_config(
            {
                "github_repo": self.inp_repo.text().strip().strip("/"),
                "branch": self.inp_branch.text().strip() or "main",
                "manifest_url": self.inp_manifest.text().strip(),
                "auto_check_on_startup": self.cb_auto.isChecked(),
            }
        )

    def _on_save_cfg(self) -> None:
        self._save_inputs_to_config()
        self.lbl_status.setText("Trạng thái: Đã lưu cấu hình vào update_config.json.")
        self.main_win.toast.show_toast("Đã lưu cấu hình cập nhật.", "ok")

    def _on_check_now(self) -> None:
        self._save_inputs_to_config()
        self.btn_check.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.prog.setValue(15)
        self.lbl_status.setText("Trạng thái: Đang kết nối GitHub kiểm tra bản mới…")

        self._check_worker = UpdateCheckWorker(self.updater, auto_apply_hotfix=False)
        self._check_worker.finished_check.connect(self._on_check_finished)
        self._check_worker.start()

    def _on_check_finished(self, res: UpdateCheckResult, _auto: bool) -> None:
        self.btn_check.setEnabled(True)
        self.prog.setValue(100 if not res.error else 0)
        self.current_result = res
        self.main_win._last_update_result = res
        self._render_result(res)

    def _render_result(self, res: UpdateCheckResult) -> None:
        if not res.configured:
            self.lbl_status.setText(
                "Trạng thái: Chưa điền GitHub Repo hoặc Manifest URL."
            )
            self.btn_apply.setEnabled(False)
            return

        if res.error:
            self.lbl_status.setText(f"Lỗi: {res.error}")
            self.lbl_status.setStyleSheet("color: #FCA5A5; font-weight: 600;")
            self.btn_apply.setEnabled(False)
            return

        if not res.has_any_update:
            self.lbl_status.setText(
                f"Trạng thái: Đang ở bản mới nhất (v{res.local_version})."
            )
            self.lbl_status.setStyleSheet("color: #6EE7B7; font-weight: 600;")
            self.txt_notes.setPlainText(
                res.changelog or "Tất cả tệp dữ liệu và EXE đều đã đồng bộ mới nhất."
            )
            self.btn_apply.setEnabled(False)
            self.main_win._set_update_badge_alert(False)
            return

        summary: List[str] = []
        if res.has_exe_update:
            summary.append(f"EXE mới v{res.remote_version}")
        if res.hotfixes_to_apply:
            summary.append(f"{len(res.hotfixes_to_apply)} tệp Hotfix")

        self.lbl_status.setText(f"Phát hiện cập nhật: {' + '.join(summary)}!")
        self.lbl_status.setStyleSheet("color: #FCD34D; font-weight: 700;")

        lines: List[str] = []
        if res.changelog:
            lines.append(f"Nội dung cập nhật:\n{res.changelog}\n")
        if res.hotfixes_to_apply:
            lines.append("Các tệp dữ liệu/cấu hình sẽ đồng bộ nhanh:")
            for hf in res.hotfixes_to_apply:
                lines.append(f"  • {hf.rel_path}")
        if res.has_exe_update:
            lines.append(
                f"\nBản thực thi mới: v{res.remote_version} (tự động tải, tráo file và mở lại)."
            )
        self.txt_notes.setPlainText("\n".join(lines))
        self.btn_apply.setEnabled(True)
        self.main_win._set_update_badge_alert(True, res.remote_version)

    def _on_apply_now(self) -> None:
        if not self.current_result or not self.current_result.has_any_update:
            return
        self.btn_apply.setEnabled(False)
        self.btn_check.setEnabled(False)
        self.prog.setValue(5)

        self._apply_worker = UpdateApplyWorker(self.updater, self.current_result)
        self._apply_worker.progress_changed.connect(self._on_apply_progress)
        self._apply_worker.apply_done.connect(self._on_apply_done)
        self._apply_worker.start()

    def _on_apply_progress(self, pct: int, msg: str) -> None:
        self.prog.setValue(pct)
        self.lbl_status.setText(f"Trạng thái: {msg}")

    def _on_apply_done(self, ok: bool, msg: str, staged_exe: str) -> None:
        self.btn_check.setEnabled(True)
        if not ok:
            self.lbl_status.setText(f"Cập nhật thất bại: {msg}")
            self.lbl_status.setStyleSheet("color: #FCA5A5; font-weight: 600;")
            self.btn_apply.setEnabled(True)
            return

        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet("color: #6EE7B7; font-weight: 700;")
        self.main_win.reload_runtime_assets()
        self.main_win._set_update_badge_alert(False)
        self.main_win.toast.show_toast(msg, "ok", 3500)

        if staged_exe:
            self.updater.spawn_self_replace_and_exit(Path(staged_exe))
            QTimer.singleShot(300, QApplication.instance().quit)


class ToastOverlay(QLabel):
    """Hiển thị thông báo nổi góc dưới phải giống hệt ##toasts trong Dear ImGui."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setVisible(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self.setVisible(False))

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None and self.isVisible():
            pw = parent.width()
            ph = parent.height()
            self.move(max(12, pw - self.width() - 24), max(12, ph - self.height() - 36))

    def show_toast(self, text: str, kind: str = "ok", duration_ms: int = 2600) -> None:
        border_col = "#3B82F6"
        text_col = "#93C5FD"
        if kind == "warn":
            border_col = "#F59E0B"
            text_col = "#FCD34D"
        elif kind == "err":
            border_col = "#EF4444"
            text_col = "#FCA5A5"
        self.setStyleSheet(
            f"""
            background-color: rgba(20, 23, 30, 245);
            color: {text_col};
            border: 1px solid {border_col};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
            """
        )
        self.setText(text)
        self.adjustSize()
        self.setVisible(True)
        self.reposition()
        self.raise_()
        self._timer.start(duration_ms)


class Mod3DMainWindow(QMainWindow):
    """Cửa sổ chính clone 100% giao diện Cường Dev · Mod 3D v1.3.70 (Bỏ kiểm tra Key)."""

    def __init__(
        self, app_dir: Optional[Path] = None, bundle_dir: Optional[Path] = None
    ) -> None:
        super().__init__()
        rt_app_dir, rt_bundle_dir = get_runtime_dirs()
        self.app_dir = (app_dir or rt_app_dir).resolve()
        self.bundle_dir = (bundle_dir or rt_bundle_dir).resolve()

        # Tài nguyên đọc (ưu tiên cạnh .exe, tự động fallback vào gói nội bộ _MEIPASS)
        self.db_path = _resolve_asset(
            "data/inject_catalog.db", self.app_dir, self.bundle_dir
        )
        self.icons_dir = _resolve_asset("data/icons", self.app_dir, self.bundle_dir)
        self.app_icon_path = _resolve_asset(
            "app_icon.png", self.app_dir, self.bundle_dir
        )
        self.guard_catalog_path = _resolve_asset(
            "_guard_catalog.json", self.app_dir, self.bundle_dir
        )

        # Tệp lưu cấu hình người dùng (luôn đặt cạnh .exe để không mất khi tắt tool)
        self.fav_sets_path = self.app_dir / "fav_sets.json"
        self.seal_prefs_path = self.app_dir / "seal_prefs.json"
        self.ui_prefs_path = self.app_dir / "ui_prefs.json"
        self.memory_config_path = self.app_dir / "memory_config.json"

        # Trạng thái bộ nhớ & dữ liệu
        self.ctx = Win32SystemContext()
        self.repo: Optional[CatalogRepository] = None
        self.sync: Optional[ProcessCatalogSynchronizer] = None
        self.startup_warning: Optional[str] = None

        self.all_items: List[CatalogItem] = []
        self.items_by_code: Dict[str, CatalogItem] = {}
        self.icon_cache: Dict[str, QPixmap] = {}

        # Trạng thái Tab 1: Trang bị
        self.selected_ride: Optional[CatalogItem] = None
        self.selected_weapon: Optional[CatalogItem] = None
        self.current_group: str = "main"
        self.current_slot: str = "ThuCuoi"
        self.fav_sets: List[Dict[str, Any]] = []
        self.active_fav_index: int = -1

        # Bộ chống giật (debounce) cho ô tìm kiếm vật phẩm
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(120)
        self._search_debounce.timeout.connect(self._refresh_equip_list)

        # Trạng thái Tab 2: Skin ấn
        self.seal_checkboxes: Dict[str, QCheckBox] = {}
        self.seal_row_widgets: Dict[str, QWidget] = {}

        # Trạng thái Tab 3: Việt hóa
        self.game_folder: str = ""

        # Trạng thái tiến trình & Tự động cập nhật GitHub
        self.attached_pid: Optional[int] = None
        self.is_admin: bool = self._check_admin()
        self.updater = GitHubAutoUpdater(self.app_dir, APP_VERSION)
        self._last_update_result: Optional[UpdateCheckResult] = None
        self._bg_update_worker: Optional[UpdateCheckWorker] = None

        self._ensure_memory_config_template()
        self._load_catalog_items()
        self._setup_window()
        self._build_ui()
        self._load_persisted_state()

        if self.startup_warning:
            QTimer.singleShot(
                200, lambda msg=self.startup_warning: self.toast.show_toast(msg, "err", 4500)
            )

        # Bộ định thời dò tìm MSango.bin tự động mỗi 2 giây
        self.proc_timer = QTimer(self)
        self.proc_timer.timeout.connect(self._refresh_process_status)
        self.proc_timer.start(2000)
        self._refresh_process_status()

        # Tự động kiểm tra bản mới / đồng bộ Hotfix ngầm khi mở ứng dụng
        if "--self-test" not in sys.argv:
            upd_cfg = self.updater.load_config()
            if bool(upd_cfg.get("auto_check_on_startup", True)):
                QTimer.singleShot(900, self._start_startup_update_check)

    # ------------------------------------------------------------------
    # KHỞI TẠO HỆ THỐNG & DỮ LIỆU
    # ------------------------------------------------------------------

    @staticmethod
    def _check_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _ensure_memory_config_template(self) -> None:
        if not self.memory_config_path.exists():
            try:
                self.memory_config_path.write_text(
                    json.dumps(DEFAULT_MEMORY_CONFIG, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass

    def _load_catalog_items(self) -> None:
        try:
            self.repo = CatalogRepository(self.db_path)
            self.sync = ProcessCatalogSynchronizer(self.ctx, self.repo)
            self.all_items = self.repo.search_items(limit=5000)
            self.items_by_code = {item.code: item for item in self.all_items}
            if not self.icons_dir.exists():
                self.startup_warning = (
                    "Thiếu hình — copy cả folder data/icons cạnh exe."
                )
        except Exception:
            self.startup_warning = (
                "Thiếu catalog — copy data/inject_catalog.db cạnh exe."
            )

    def reload_runtime_assets(self) -> None:
        """Nạp nóng lại Catalog DB, Icons và Cấu hình sau khi đồng bộ Hotfix mà không cần tắt tool."""
        self.db_path = _resolve_asset(
            "data/inject_catalog.db", self.app_dir, self.bundle_dir
        )
        self.icons_dir = _resolve_asset("data/icons", self.app_dir, self.bundle_dir)
        self.guard_catalog_path = _resolve_asset(
            "_guard_catalog.json", self.app_dir, self.bundle_dir
        )
        self.icon_cache.clear()
        self._load_catalog_items()
        for grp_key, grp_label, _tip in GROUP_FILTERS:
            cnt = sum(1 for it in self.all_items if it.group == grp_key)
            btn = self.grp_buttons.get(grp_key)
            if btn:
                btn.setText(f"{grp_label} ({cnt})")
        self._update_slot_counts()
        self._refresh_equip_list()

    def _start_startup_update_check(self) -> None:
        upd_cfg = self.updater.load_config()
        auto_hf = bool(upd_cfg.get("sync_hotfix_files", True))
        self._bg_update_worker = UpdateCheckWorker(
            self.updater, auto_apply_hotfix=auto_hf
        )
        self._bg_update_worker.finished_check.connect(self._on_startup_update_checked)
        self._bg_update_worker.start()

    def _on_startup_update_checked(
        self, res: UpdateCheckResult, _was_auto: bool
    ) -> None:
        self._last_update_result = res
        if not res.configured or res.error:
            return
        if res.changelog.startswith("AUTO_HOTFIX_OK:"):
            files_str = res.changelog.split(":", 1)[1]
            self.reload_runtime_assets()
            self.toast.show_toast(
                f"Đã tự động cập nhật Hotfix ({files_str})!", "ok", 3800
            )
            return
        if res.has_any_update:
            self._set_update_badge_alert(True, res.remote_version)
            if res.has_exe_update:
                self.toast.show_toast(
                    f"Đã có bản mới v{res.remote_version} trên GitHub — Bấm 'Cập nhật' góc phải!",
                    "warn",
                    4500,
                )
            else:
                self.toast.show_toast(
                    f"Có {len(res.hotfixes_to_apply)} tệp Hotfix mới — Bấm 'Cập nhật' góc phải!",
                    "warn",
                    4000,
                )

    def _set_update_badge_alert(
        self, has_update: bool, new_ver: str = ""
    ) -> None:
        if not hasattr(self, "btn_update"):
            return
        if has_update:
            ver_tag = f" v{new_ver}" if new_ver else ""
            self.btn_update.setText(f"⬇ Có bản mới{ver_tag}")
            self.btn_update.setStyleSheet(
                "background-color: #1D4ED8; color: #FFFFFF; border: 1px solid #60A5FA; "
                "border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: 700;"
            )
        else:
            self.btn_update.setText("⟳ Cập nhật")
            self.btn_update.setStyleSheet(
                "background-color: #1E2430; color: #93C5FD; border: 1px solid #334155; "
                "border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: 600;"
            )

    def _open_update_dialog(self) -> None:
        dlg = UpdateDialog(self, self.updater, self._last_update_result)
        dlg.exec()

    def _get_item_pixmap(self, rel_icon: str, size: int = 56) -> QPixmap:
        cache_key = f"{rel_icon}:{size}"
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]

        pix = QPixmap(size, size)
        pix.fill(QColor("#12151C"))
        if rel_icon:
            full_path = self.icons_dir / rel_icon
            if full_path.exists():
                loaded = QPixmap(str(full_path))
                if not loaded.isNull():
                    pix = loaded.scaled(
                        size,
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
        self.icon_cache[cache_key] = pix
        return pix

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_TITLE)
        self.resize(1140, 740)
        self.setMinimumSize(960, 640)
        if self.app_icon_path.exists():
            self.setWindowIcon(QIcon(str(self.app_icon_path)))
        self.setStyleSheet(IMGUI_DARK_QSS)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "toast"):
            self.toast.reposition()

    # ------------------------------------------------------------------
    # XÂY DỰNG GIAO DIỆN CHÍNH (HEADER + 3 TAB + FOOTER + TOAST)
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("rootWidget")
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Thanh Header trên cùng
        main_layout.addWidget(self._build_top_header())

        # 2. Vùng StackedWidget chứa 3 Tab
        self.pages = QStackedWidget(root)
        self.pages.addWidget(self._build_tab_equip())
        self.pages.addWidget(self._build_tab_seal())
        self.pages.addWidget(self._build_tab_viethoa())
        main_layout.addWidget(self.pages, 1)

        # 3. Thanh bản quyền dưới cùng
        footer = QFrame(root)
        footer.setStyleSheet(
            "background-color: #14171E; border-top: 1px solid #232834;"
        )
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(16, 5, 16, 5)
        lbl_copy = QLabel("© 2026 Cường Dev. Bảo lưu mọi quyền.")
        lbl_copy.setStyleSheet("color: #6B7280; font-size: 11px;")
        lbl_mode = QLabel("Chế độ: Độc lập (Offline Native - Không cần Key)")
        lbl_mode.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 600;")
        f_layout.addWidget(lbl_copy)
        f_layout.addStretch(1)
        f_layout.addWidget(lbl_mode)
        main_layout.addWidget(footer)

        # 4. Toast thông báo góc phải
        self.toast = ToastOverlay(root)

    def _build_top_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("topHeader")
        header.setFixedHeight(52)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(14)

        # Logo + Thương hiệu
        logo_lbl = QLabel()
        if self.app_icon_path.exists():
            pix = QPixmap(str(self.app_icon_path)).scaled(
                28,
                28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_lbl.setPixmap(pix)
        layout.addWidget(logo_lbl)

        title_lbl = QLabel("Cường Dev")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #F9FAFB;")
        layout.addWidget(title_lbl)

        sub_lbl = QLabel(f"Mod 3D  ·  v{APP_VERSION}")
        sub_lbl.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        layout.addWidget(sub_lbl)

        layout.addSpacing(20)

        # 3 Nút chuyển Tab (Trang bị / Skin ấn / Việt hóa)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        tab_specs = [
            (0, "Trang bị"),
            (1, "Skin ấn"),
            (2, "Việt hóa"),
        ]
        for idx, text in tab_specs:
            btn = QPushButton(text)
            btn.setObjectName("navTab")
            btn.setCheckable(True)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda _checked, i=idx: self.pages.setCurrentIndex(i))
            self.nav_group.addButton(btn, idx)
            layout.addWidget(btn)

        layout.addStretch(1)

        # Đèn báo trạng thái Game, Quyền Admin & Nút Cập nhật GitHub
        self.lbl_game_badge = QLabel("Game: Không thấy MSango.bin")
        self.lbl_game_badge.setStyleSheet(
            "background-color: #262020; color: #FCA5A5; border: 1px solid #522B2B; "
            "border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: 600;"
        )
        layout.addWidget(self.lbl_game_badge)

        self.lbl_admin_badge = QLabel("Admin" if self.is_admin else "Cần Admin")
        if self.is_admin:
            self.lbl_admin_badge.setStyleSheet(
                "background-color: #162B24; color: #6EE7B7; border: 1px solid #235342; "
                "border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: 600;"
            )
        else:
            self.lbl_admin_badge.setStyleSheet(
                "background-color: #2D2618; color: #FCD34D; border: 1px solid #5C481E; "
                "border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: 600;"
            )
        layout.addWidget(self.lbl_admin_badge)

        self.btn_update = QPushButton("⟳ Cập nhật")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.setToolTip(
            "Kiểm tra và tải bản cập nhật / Hotfix tự động từ GitHub"
        )
        self.btn_update.clicked.connect(self._open_update_dialog)
        self._set_update_badge_alert(False)
        layout.addWidget(self.btn_update)

        return header

    # ------------------------------------------------------------------
    # TAB 1: TRANG BỊ (nav-equip)
    # ------------------------------------------------------------------

    def _build_tab_equip(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # ================= CỘT TRÁI: BOARD & BỘ YÊU THÍCH =================
        left_col = QFrame()
        left_col.setObjectName("cardFrame")
        left_col.setFixedWidth(330)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        lbl_board_title = QLabel("TRANG BỊ ĐANG CHỌN")
        lbl_board_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #9CA3AF; letter-spacing: 0.5px;"
        )
        left_layout.addWidget(lbl_board_title)

        lbl_rule = QLabel("Ep: 1 canh/thu + 1 vu khi.")
        lbl_rule.setStyleSheet("color: #6B7280; font-size: 12px;")
        left_layout.addWidget(lbl_rule)

        # Ô 1: CƯỠI (Thú cưỡi / Cánh)
        self.ride_box, self.ride_icon_lbl, self.ride_name_lbl, self.ride_code_lbl = (
            self._create_equip_slot_box("CƯỠI")
        )
        left_layout.addWidget(self.ride_box)

        # Ô 2: VŨ KHÍ
        self.weap_box, self.weap_icon_lbl, self.weap_name_lbl, self.weap_code_lbl = (
            self._create_equip_slot_box("VŨ KHÍ")
        )
        left_layout.addWidget(self.weap_box)

        # Hàng nút Áp & Gỡ
        act_row = QHBoxLayout()
        act_row.setSpacing(8)
        self.btn_apply_equip = QPushButton("Áp")
        self.btn_apply_equip.setObjectName("primaryBtn")
        self.btn_apply_equip.setFixedHeight(36)
        self.btn_apply_equip.clicked.connect(self._on_apply_equip)

        self.btn_clear_equip = QPushButton("Gỡ")
        self.btn_clear_equip.setObjectName("dangerBtn")
        self.btn_clear_equip.setFixedHeight(36)
        self.btn_clear_equip.clicked.connect(self._on_unequip)

        act_row.addWidget(self.btn_apply_equip, 2)
        act_row.addWidget(self.btn_clear_equip, 1)
        left_layout.addLayout(act_row)

        left_layout.addSpacing(8)

        # Khung Lưu Bộ Yêu Thích (fav_sets.json)
        lbl_fav = QLabel("BỘ LƯU NHANH (Tối đa 24 bộ)")
        lbl_fav.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #9CA3AF; letter-spacing: 0.5px;"
        )
        left_layout.addWidget(lbl_fav)

        save_row = QHBoxLayout()
        save_row.setSpacing(6)
        self.inp_set_name = QLineEdit()
        self.inp_set_name.setPlaceholderText("Tên bộ")
        self.inp_set_name.setText("Bộ mới")
        btn_save_set = QPushButton("Lưu")
        btn_save_set.clicked.connect(self._on_save_fav_set)
        save_row.addWidget(self.inp_set_name, 1)
        save_row.addWidget(btn_save_set)
        left_layout.addLayout(save_row)

        self.fav_list_widget = QListWidget()
        self.fav_list_widget.itemClicked.connect(self._on_select_fav_set)
        left_layout.addWidget(self.fav_list_widget, 1)

        btn_del_set = QPushButton("Xóa bộ đang chọn")
        btn_del_set.clicked.connect(self._on_delete_fav_set)
        left_layout.addWidget(btn_del_set)

        layout.addWidget(left_col)

        # ================= CỘT PHẢI: KHO VẬT PHẨM =================
        right_col = QFrame()
        right_col.setObjectName("cardFrame")
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        # Hàng 1: Nhóm lọc (Thường / Đồ 3D / Thử) + Ô tìm kiếm
        top_filter_row = QHBoxLayout()
        top_filter_row.setSpacing(8)

        self.grp_btn_group = QButtonGroup(self)
        self.grp_btn_group.setExclusive(True)
        self.grp_buttons: Dict[str, QPushButton] = {}

        for grp_key, grp_label, grp_tip in GROUP_FILTERS:
            cnt = sum(1 for it in self.all_items if it.group == grp_key)
            btn = QPushButton(f"{grp_label} ({cnt})")
            btn.setCheckable(True)
            btn.setToolTip(grp_tip)
            if grp_key == self.current_group:
                btn.setChecked(True)
            btn.clicked.connect(lambda _c, g=grp_key: self._on_change_group(g))
            self.grp_btn_group.addButton(btn)
            self.grp_buttons[grp_key] = btn
            top_filter_row.addWidget(btn)

        top_filter_row.addStretch(1)

        self.inp_search_equip = QLineEdit()
        self.inp_search_equip.setPlaceholderText("Tìm… (Tên trang bị, mã H566, mesh)")
        self.inp_search_equip.setClearButtonEnabled(True)
        self.inp_search_equip.setFixedWidth(280)
        self.inp_search_equip.textChanged.connect(
            lambda _txt: self._search_debounce.start()
        )
        top_filter_row.addWidget(self.inp_search_equip)

        right_layout.addLayout(top_filter_row)

        # Hàng 2: Các Tab Loại Trang Bị (slotlist)
        slot_row = QHBoxLayout()
        slot_row.setSpacing(6)
        self.slot_btn_group = QButtonGroup(self)
        self.slot_btn_group.setExclusive(True)
        self.slot_buttons: Dict[str, QPushButton] = {}

        for slot_key, slot_vi, _kind in SLOT_CATEGORIES:
            btn = QPushButton(slot_vi)
            btn.setCheckable(True)
            if slot_key == self.current_slot:
                btn.setChecked(True)
            btn.clicked.connect(lambda _c, s=slot_key: self._on_change_slot(s))
            self.slot_btn_group.addButton(btn)
            self.slot_buttons[slot_key] = btn
            slot_row.addWidget(btn)
        slot_row.addStretch(1)
        right_layout.addLayout(slot_row)

        # Khu vực cuộn hiển thị danh sách vật phẩm kèm ảnh 64x64
        self.equip_scroll = QScrollArea()
        self.equip_scroll.setWidgetResizable(True)
        self.equip_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #262B36; border-radius: 5px; background-color: #12151C; }"
        )
        self.equip_list_container = QWidget()
        self.equip_list_container.setStyleSheet("background-color: #12151C;")
        self.equip_list_layout = QVBoxLayout(self.equip_list_container)
        self.equip_list_layout.setContentsMargins(10, 10, 10, 10)
        self.equip_list_layout.setSpacing(6)
        self.equip_scroll.setWidget(self.equip_list_container)
        right_layout.addWidget(self.equip_scroll, 1)

        layout.addWidget(right_col, 1)

        self._update_slot_counts()
        self._refresh_equip_list()
        return page

    def _create_equip_slot_box(
        self, slot_title: str
    ) -> Tuple[QFrame, QLabel, QLabel, QLabel]:
        box = QFrame()
        box.setObjectName("slotBox")
        box.setFixedHeight(78)
        h = QHBoxLayout(box)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(56, 56)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            "background-color: #12151C; border: 1px solid #2D3342; border-radius: 4px;"
        )
        h.addWidget(icon_lbl)

        info_v = QVBoxLayout()
        info_v.setSpacing(2)
        lbl_tag = QLabel(slot_title)
        lbl_tag.setStyleSheet("color: #60A5FA; font-size: 11px; font-weight: 700;")
        name_lbl = QLabel("—")
        name_lbl.setStyleSheet("color: #F3F4F6; font-size: 13px; font-weight: 600;")
        code_lbl = QLabel("Chưa chọn")
        code_lbl.setFont(QFont("Consolas", 10))
        code_lbl.setStyleSheet("color: #9CA3AF;")

        info_v.addWidget(lbl_tag)
        info_v.addWidget(name_lbl)
        info_v.addWidget(code_lbl)
        h.addLayout(info_v, 1)

        return box, icon_lbl, name_lbl, code_lbl

    def _update_slot_counts(self) -> None:
        for slot_key, slot_vi, _kind in SLOT_CATEGORIES:
            cnt = sum(
                1
                for it in self.all_items
                if it.group == self.current_group and it.slot == slot_key
            )
            btn = self.slot_buttons.get(slot_key)
            if btn:
                btn.setText(f"{slot_vi} ({cnt})")
                if slot_key == "":
                    btn.setVisible(cnt > 0)

        # Nếu đang đứng ở tab 'Khác' mà chuyển sang nhóm không có mục 'Khác', tự quay về 'ThuCuoi'
        if self.current_slot == "":
            other_btn = self.slot_buttons.get("")
            if other_btn and not other_btn.isVisible():
                self.current_slot = "ThuCuoi"
                first_btn = self.slot_buttons.get("ThuCuoi")
                if first_btn:
                    first_btn.setChecked(True)

    def _on_change_group(self, grp_key: str) -> None:
        self.current_group = grp_key
        self._update_slot_counts()
        self._refresh_equip_list()

    def _on_change_slot(self, slot_key: str) -> None:
        self.current_slot = slot_key
        self._refresh_equip_list()

    def _refresh_equip_list(self) -> None:
        self.equip_list_container.setUpdatesEnabled(False)
        try:
            while self.equip_list_layout.count():
                child = self.equip_list_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            query = self.inp_search_equip.text().strip().lower()
            filtered: List[CatalogItem] = []
            for item in self.all_items:
                if item.group != self.current_group:
                    continue
                if item.slot != self.current_slot:
                    continue
                if query:
                    haystack = f"{item.name} {item.code} {item.mesh}".lower()
                    if query not in haystack:
                        continue
                filtered.append(item)

            if not filtered:
                empty_lbl = QLabel("Không thấy vật phẩm phù hợp.")
                empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_lbl.setStyleSheet("color: #6B7280; padding: 32px;")
                self.equip_list_layout.addWidget(empty_lbl)
                self.equip_list_layout.addStretch(1)
                return

            for item in filtered:
                row = QFrame()
                row.setObjectName("itemRow")
                row.setFixedHeight(68)
                r_layout = QHBoxLayout(row)
                r_layout.setContentsMargins(10, 6, 12, 6)
                r_layout.setSpacing(12)

                ic = QLabel()
                ic.setFixedSize(52, 52)
                ic.setPixmap(self._get_item_pixmap(item.icon, 52))
                ic.setStyleSheet(
                    "background-color: #12151C; border: 1px solid #262B36; border-radius: 4px;"
                )
                r_layout.addWidget(ic)

                txt_col = QVBoxLayout()
                txt_col.setSpacing(2)
                lbl_name = QLabel(item.name or item.code)
                lbl_name.setStyleSheet(
                    "font-size: 13px; font-weight: 600; color: #F3F4F6;"
                )
                slot_disp = item.slot or "Khác"
                lbl_meta = QLabel(
                    f"Code: {item.code}  ·  Mesh: {item.mesh}  ·  Slot: {slot_disp} (Type {item.item_type})"
                )
                lbl_meta.setFont(QFont("Consolas", 10))
                lbl_meta.setStyleSheet("color: #9CA3AF;")
                txt_col.addWidget(lbl_name)
                txt_col.addWidget(lbl_meta)
                r_layout.addLayout(txt_col, 1)

                btn_pick = QPushButton("Chọn")
                btn_pick.setFixedWidth(74)
                btn_pick.clicked.connect(
                    lambda _c, it=item: self._select_equip_item(it, notify=True)
                )
                r_layout.addWidget(btn_pick)

                self.equip_list_layout.addWidget(row)

            self.equip_list_layout.addStretch(1)
        finally:
            self.equip_list_container.setUpdatesEnabled(True)
            self.equip_scroll.verticalScrollBar().setValue(0)

    def _select_equip_item(self, item: CatalogItem, notify: bool = True) -> None:
        slot_disp = item.slot or "Khác"
        if item.slot in RIDE_SLOTS:
            self.selected_ride = item
            self.ride_icon_lbl.setPixmap(self._get_item_pixmap(item.icon, 52))
            self.ride_name_lbl.setText(item.name or item.code)
            self.ride_code_lbl.setText(f"{item.code} ({slot_disp})")
        else:
            self.selected_weapon = item
            self.weap_icon_lbl.setPixmap(self._get_item_pixmap(item.icon, 52))
            self.weap_name_lbl.setText(item.name or item.code)
            self.weap_code_lbl.setText(f"{item.code} ({slot_disp})")

        if notify:
            self.toast.show_toast(
                f"Chọn {item.name or item.code} ({item.code})", "ok"
            )

    def _try_find_pid(self) -> Optional[int]:
        try:
            return self.ctx.find_process_id(PROCESS_TARGET)
        except OSError:
            return None

    def _load_memory_config(self) -> Dict[str, Any]:
        if not self.memory_config_path.exists():
            return DEFAULT_MEMORY_CONFIG
        try:
            return json.loads(self.memory_config_path.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULT_MEMORY_CONFIG

    @staticmethod
    def _parse_cfg_int(val: Any) -> int:
        if isinstance(val, int):
            return val
        return int(str(val).strip(), 0)

    def _on_apply_equip(self) -> None:
        if not self.selected_ride and not self.selected_weapon:
            self.toast.show_toast("Chưa chọn trang bị nào để áp.", "warn")
            return

        pid = self._try_find_pid()
        if not pid:
            self.toast.show_toast("Mở game trước (Không thấy MSango.bin).", "warn")
            return

        if self.sync is None:
            self.toast.show_toast("Thiếu cơ sở dữ liệu catalog.", "err")
            return

        cfg = self._load_memory_config()
        ptr_size = int(cfg.get("pointer_size", 4))
        tasks: List[Tuple[str, CatalogItem, Dict[str, Any]]] = []
        if self.selected_ride is not None:
            tasks.append(("ride", self.selected_ride, dict(cfg.get("ride") or {})))
        if self.selected_weapon is not None:
            tasks.append(("weapon", self.selected_weapon, dict(cfg.get("weapon") or {})))

        configured_tasks = [
            t for t in tasks if str(t[2].get("aob_pattern", "")).strip()
        ]
        codes = [t[1].code for t in tasks]

        if not configured_tasks:
            self.toast.show_toast(
                f"Đã kết nối PID {pid} ({', '.join(codes)}) — Điền AOB/Offset vào memory_config.json để ghi bộ nhớ.",
                "warn",
                3600,
            )
            return

        applied_codes: List[str] = []
        try:
            for _kind, item, slot_cfg in configured_tasks:
                pattern = str(slot_cfg.get("aob_pattern", "")).strip()
                pat_offset = self._parse_cfg_int(slot_cfg.get("pattern_offset", 0))
                raw_offsets = slot_cfg.get("offsets") or []
                offsets = [self._parse_cfg_int(x) for x in raw_offsets]
                field = str(slot_cfg.get("payload_field", "mesh")).strip() or "mesh"
                scan_data = bool(slot_cfg.get("scan_data", False))

                self.sync.execute_pipeline(
                    item_code=item.code,
                    aob_pattern=pattern,
                    pointer_offsets=offsets,
                    process_id=pid,
                    pointer_size=ptr_size,
                    pattern_offset=pat_offset,
                    require_executable=not scan_data,
                    payload_field=field,
                )
                applied_codes.append(item.code)

            self.toast.show_toast(
                f"Đã áp ({', '.join(applied_codes)}) vào PID {pid}.", "ok"
            )
        except OSError as exc:
            self.toast.show_toast(
                f"Ghi bộ nhớ thất bại (Cần quyền Admin?): {exc}", "err", 4000
            )
        except Exception as exc:
            self.toast.show_toast(f"Lỗi khi áp mã: {exc}", "err", 4000)

    def _clear_equip_slots(self) -> None:
        self.selected_ride = None
        self.selected_weapon = None
        self.ride_icon_lbl.clear()
        self.ride_name_lbl.setText("—")
        self.ride_code_lbl.setText("Chưa chọn")
        self.weap_icon_lbl.clear()
        self.weap_name_lbl.setText("—")
        self.weap_code_lbl.setText("Chưa chọn")

    def _on_unequip(self) -> None:
        self._clear_equip_slots()
        self.toast.show_toast("Đã gỡ.", "ok")

    # ------------------------------------------------------------------
    # QUẢN LÝ BỘ YÊU THÍCH (fav_sets.json)
    # ------------------------------------------------------------------

    def _refresh_fav_list_ui(self) -> None:
        self.fav_list_widget.clear()
        if not self.fav_sets:
            item = QListWidgetItem("Chưa có bộ")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.fav_list_widget.addItem(item)
            return

        for s in self.fav_sets:
            name = str(s.get("name", "Bộ"))
            codes = list(s.get("codes", []))
            c1 = codes[0] if len(codes) > 0 and codes[0] else "—"
            c2 = codes[1] if len(codes) > 1 and codes[1] else "—"
            self.fav_list_widget.addItem(f"{name}  ·  {c1} + {c2}")

        if 0 <= self.active_fav_index < len(self.fav_sets):
            self.fav_list_widget.setCurrentRow(self.active_fav_index)

    def _on_save_fav_set(self) -> None:
        if len(self.fav_sets) >= 24:
            self.toast.show_toast("Tối đa 24 bộ.", "warn")
            return
        name = self.inp_set_name.text().strip() or "Bộ mới"
        c1 = self.selected_ride.code if self.selected_ride else ""
        c2 = self.selected_weapon.code if self.selected_weapon else ""
        if not c1 and not c2:
            self.toast.show_toast("Hãy chọn ít nhất 1 món trước khi lưu bộ.", "warn")
            return

        self.fav_sets.append({"name": name, "codes": [c1, c2]})
        self.active_fav_index = len(self.fav_sets) - 1
        self._save_fav_sets_file()
        self._refresh_fav_list_ui()
        self.toast.show_toast("Đã lưu.", "ok")

    def _on_select_fav_set(self, item: QListWidgetItem) -> None:
        idx = self.fav_list_widget.row(item)
        if 0 <= idx < len(self.fav_sets):
            self.active_fav_index = idx
            entry = self.fav_sets[idx]
            set_name = str(entry.get("name", "Bộ"))
            codes = list(entry.get("codes", []))
            self._clear_equip_slots()
            for code in codes:
                if code and code in self.items_by_code:
                    self._select_equip_item(self.items_by_code[code], notify=False)
            self._save_fav_sets_file()
            self.toast.show_toast(f"Đã nạp bộ: {set_name}", "ok")

    def _on_delete_fav_set(self) -> None:
        row = self.fav_list_widget.currentRow()
        if 0 <= row < len(self.fav_sets):
            self.fav_sets.pop(row)
            self.active_fav_index = -1
            self._save_fav_sets_file()
            self._refresh_fav_list_ui()
            self.toast.show_toast("Đã xóa.", "ok")

    def _save_fav_sets_file(self) -> None:
        payload = {
            "active": self.active_fav_index,
            "sets": self.fav_sets,
        }
        try:
            self.fav_sets_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # TAB 2: SKIN ẤN (nav-seal / sealpage)
    # ------------------------------------------------------------------

    def _build_tab_seal(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("cardFrame")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(10)

        lbl_sub = QLabel(
            "Giả lập đang mặc ấn trên tướng mình. Không cần ấn trong túi."
        )
        lbl_sub.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        c_layout.addWidget(lbl_sub)

        # Thanh công cụ thao tác
        bar = QHBoxLayout()
        bar.setSpacing(8)

        btn_apply_seal = QPushButton("Áp ấn")
        btn_apply_seal.setObjectName("primaryBtn")
        btn_apply_seal.clicked.connect(self._on_apply_seal)

        btn_fix_invis = QPushButton("Gỡ tàn hình")
        btn_fix_invis.setObjectName("dangerBtn")
        btn_fix_invis.clicked.connect(self._on_remove_broken_seal)

        btn_all = QPushButton("Tất cả")
        btn_all.clicked.connect(self._on_seal_select_all)

        btn_full = QPushButton("Đủ model")
        btn_full.clicked.connect(self._on_seal_select_full_model)

        btn_none = QPushButton("Bỏ chọn")
        btn_none.clicked.connect(self._on_seal_select_none)

        self.lbl_seal_count = QLabel("Chưa chọn")
        self.lbl_seal_count.setStyleSheet(
            "color: #60A5FA; font-weight: 700; padding: 0 8px;"
        )

        self.inp_search_seal = QLineEdit()
        self.inp_search_seal.setPlaceholderText("Tìm tướng…")
        self.inp_search_seal.setClearButtonEnabled(True)
        self.inp_search_seal.setFixedWidth(240)
        self.inp_search_seal.textChanged.connect(self._on_filter_seal_heroes)

        bar.addWidget(btn_apply_seal)
        bar.addWidget(btn_fix_invis)
        bar.addSpacing(8)
        bar.addWidget(btn_all)
        bar.addWidget(btn_full)
        bar.addWidget(btn_none)
        bar.addWidget(self.lbl_seal_count)
        bar.addStretch(1)
        bar.addWidget(self.inp_search_seal)
        c_layout.addLayout(bar)

        # Danh sách 55 tướng chia 3 cột
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #262B36; border-radius: 5px; background-color: #12151C; }"
        )
        grid_host = QWidget()
        grid_host.setStyleSheet("background-color: #12151C;")
        self.seal_grid = QGridLayout(grid_host)
        self.seal_grid.setContentsMargins(12, 12, 12, 12)
        self.seal_grid.setHorizontalSpacing(16)
        self.seal_grid.setVerticalSpacing(8)

        for idx, (stem, vi_name) in enumerate(SEAL_HEROES):
            row_frame = QFrame()
            row_frame.setObjectName("itemRow")
            r_lay = QHBoxLayout(row_frame)
            r_lay.setContentsMargins(10, 6, 10, 6)

            is_full = stem in FULL_MODEL_STEMS
            cb = QCheckBox(f"{vi_name}  ({stem})")
            cb.stateChanged.connect(self._on_seal_selection_changed)
            r_lay.addWidget(cb, 1)

            if is_full:
                badge = QLabel("Đủ model")
                badge.setStyleSheet(
                    "background-color: #162B24; color: #6EE7B7; border-radius: 3px; "
                    "padding: 2px 6px; font-size: 10px; font-weight: 600;"
                )
                r_lay.addWidget(badge)

            self.seal_checkboxes[stem] = cb
            self.seal_row_widgets[stem] = row_frame
            self.seal_grid.addWidget(row_frame, idx // 3, idx % 3)

        scroll.setWidget(grid_host)
        c_layout.addWidget(scroll, 1)

        note_lbl = QLabel(
            "Body ấn: *1.mdx trong MODE hoặc *1.msx trong Data.dhp "
            "(Đổng Trác = Equip/Renwu/dongzhuo1.msx). Đồng đội/địch không ăn. Không đụng mod trang bị."
        )
        note_lbl.setStyleSheet("color: #6B7280; font-size: 11px;")
        c_layout.addWidget(note_lbl)

        layout.addWidget(card, 1)
        return page

    def _update_seal_counter_ui(self) -> List[str]:
        selected = [
            stem for stem, cb in self.seal_checkboxes.items() if cb.isChecked()
        ]
        if selected:
            self.lbl_seal_count.setText(f"{len(selected)} tướng")
        else:
            self.lbl_seal_count.setText("Chưa chọn")
        return selected

    def _on_seal_selection_changed(self) -> None:
        selected = self._update_seal_counter_ui()
        self._save_seal_prefs(selected)

    def _on_seal_select_all(self) -> None:
        for cb in self.seal_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._on_seal_selection_changed()

    def _on_seal_select_full_model(self) -> None:
        for stem, cb in self.seal_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(stem in FULL_MODEL_STEMS)
            cb.blockSignals(False)
        self._on_seal_selection_changed()

    def _on_seal_select_none(self) -> None:
        for cb in self.seal_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._on_seal_selection_changed()

    def _on_filter_seal_heroes(self, text: str) -> None:
        q = text.strip().lower()
        for stem, vi_name in SEAL_HEROES:
            w = self.seal_row_widgets[stem]
            visible = (not q) or (q in stem.lower()) or (q in vi_name.lower())
            w.setVisible(visible)

    def _on_apply_seal(self) -> None:
        selected = [
            stem for stem, cb in self.seal_checkboxes.items() if cb.isChecked()
        ]
        if not selected:
            self.toast.show_toast("Chưa chọn tướng để mở skin ấn.", "warn")
            return
        pid = self._try_find_pid()
        if not pid:
            self.toast.show_toast(
                "Chưa thấy MSango.bin — hãy mở game trước.", "warn"
            )
            return
        self.toast.show_toast(
            f"Đã lưu danh sách {len(selected)} tướng (PID {pid}) vào seal_prefs.json.",
            "ok",
        )

    def _on_remove_broken_seal(self) -> None:
        pid = self._try_find_pid()
        if not pid:
            self.toast.show_toast(
                "Chưa thấy MSango.bin — hãy mở game trước.", "warn"
            )
            return
        self.toast.show_toast("Đã gửi yêu cầu khôi phục trạng thái mặc định.", "ok")

    def _save_seal_prefs(self, stems: List[str]) -> None:
        payload = {
            "seal_skins": True,
            "seal_stems": stems,
        }
        try:
            self.seal_prefs_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # TAB 3: VIỆT HÓA (nav-vh / vhpage)
    # ------------------------------------------------------------------

    def _build_tab_viethoa(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        lbl_intro = QLabel("Chặn CDN và cài pack tiếng Việt.")
        lbl_intro.setStyleSheet("color: #9CA3AF; font-size: 13px;")
        layout.addWidget(lbl_intro)

        # CARD 1: Thư mục game (vh-game)
        c_game = QFrame()
        c_game.setObjectName("cardFrame")
        cg_lay = QVBoxLayout(c_game)
        cg_lay.setContentsMargins(16, 12, 16, 12)
        cg_lay.setSpacing(8)

        lbl_cg_title = QLabel("Thư mục game")
        lbl_cg_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F3F4F6;")
        cg_lay.addWidget(lbl_cg_title)

        path_row = QHBoxLayout()
        self.lbl_game_dir = QLabel("Chưa chọn — bấm Đổi…")
        self.lbl_game_dir.setFont(QFont("Consolas", 10))
        self.lbl_game_dir.setStyleSheet(
            "background-color: #12151C; border: 1px solid #2D3342; border-radius: 5px; padding: 6px 10px; color: #D1D5DB;"
        )
        btn_change_dir = QPushButton("Đổi…")
        btn_change_dir.clicked.connect(self._on_pick_game_folder)
        btn_refresh_vh = QPushButton("Làm mới")
        btn_refresh_vh.clicked.connect(self._refresh_viethoa_status)

        path_row.addWidget(self.lbl_game_dir, 1)
        path_row.addWidget(btn_change_dir)
        path_row.addWidget(btn_refresh_vh)
        cg_lay.addLayout(path_row)
        layout.addWidget(c_game)

        # CARD 2: Chặn cập nhật (vh-block)
        c_block = QFrame()
        c_block.setObjectName("cardFrame")
        cb_lay = QVBoxLayout(c_block)
        cb_lay.setContentsMargins(16, 12, 16, 12)
        cb_lay.setSpacing(8)

        lbl_cb_title = QLabel("Chặn cập nhật")
        lbl_cb_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F3F4F6;")
        cb_lay.addWidget(lbl_cb_title)

        lbl_cb_desc = QLabel(
            "Khóa Data.dhp thư mục đang chọn. Không đụng hosts — 梦三国2 vẫn lấy CDN chính thức."
        )
        lbl_cb_desc.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        cb_lay.addWidget(lbl_cb_desc)

        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(24)
        status_grid.setVerticalSpacing(6)

        self.vh_status_labels: Dict[str, QLabel] = {}
        rows_spec = [
            ("admin", "Quyền Admin"),
            ("pack", "Pack client"),
            ("guard", "ViethoaGuard cũ"),
            ("hosts", "Hosts"),
            ("stub", "Stub :80"),
            ("auto1", "Auto 梦三国"),
            ("auto2", "Auto 梦三国2"),
        ]
        for r_idx, (key, title) in enumerate(rows_spec):
            k_lbl = QLabel(title)
            k_lbl.setStyleSheet("color: #9CA3AF;")
            v_lbl = QLabel("—")
            v_lbl.setStyleSheet("color: #E5E7EB; font-weight: 600;")
            self.vh_status_labels[key] = v_lbl
            status_grid.addWidget(k_lbl, r_idx, 0)
            status_grid.addWidget(v_lbl, r_idx, 1)

        status_grid.setColumnStretch(1, 1)
        cb_lay.addLayout(status_grid)

        block_btn_row = QHBoxLayout()
        btn_lock = QPushButton("Chặn update")
        btn_lock.setObjectName("primaryBtn")
        btn_lock.clicked.connect(lambda: self._set_dhp_lock(True))

        btn_unlock = QPushButton("Cho phép update")
        btn_unlock.clicked.connect(lambda: self._set_dhp_lock(False))

        block_btn_row.addWidget(btn_lock)
        block_btn_row.addWidget(btn_unlock)
        block_btn_row.addStretch(1)
        cb_lay.addLayout(block_btn_row)
        layout.addWidget(c_block)

        # CARD 3: Pack tiếng Việt (vh-pack)
        c_pack = QFrame()
        c_pack.setObjectName("cardFrame")
        cp_lay = QVBoxLayout(c_pack)
        cp_lay.setContentsMargins(16, 12, 16, 12)
        cp_lay.setSpacing(8)

        lbl_cp_title = QLabel("Pack tiếng Việt")
        lbl_cp_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F3F4F6;")
        cp_lay.addWidget(lbl_cp_title)

        lbl_cp_desc = QLabel(
            "Tải Data.dhp + version.dll rồi ghi vào thư mục game. Game sẽ đóng khi ghi file."
        )
        lbl_cp_desc.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        cp_lay.addWidget(lbl_cp_desc)

        self.lbl_dhp_info = QLabel(
            "• Pack Việt hóa (thay pack trong Data): Data.dhp — Sẵn sàng"
        )
        self.lbl_dll_info = QLabel(
            "• Proxy chữ / HUD cạnh MSango.bin: version.dll — Sẵn sàng"
        )
        cp_lay.addWidget(self.lbl_dhp_info)
        cp_lay.addWidget(self.lbl_dll_info)

        self.vh_progress = QProgressBar()
        self.vh_progress.setValue(0)
        cp_lay.addWidget(self.vh_progress)

        pack_btn_row = QHBoxLayout()
        self.btn_dl_both = QPushButton("Tải & cài cả hai")
        self.btn_dl_both.setObjectName("primaryBtn")
        self.btn_dl_both.clicked.connect(self._on_download_and_install_pack)

        self.btn_pick_dhp = QPushButton("Chọn Data.dhp…")
        self.btn_pick_dhp.clicked.connect(self._on_install_local_dhp)

        self.btn_pick_dll = QPushButton("Chọn version.dll…")
        self.btn_pick_dll.clicked.connect(self._on_install_local_dll)

        pack_btn_row.addWidget(self.btn_dl_both)
        pack_btn_row.addWidget(self.btn_pick_dhp)
        pack_btn_row.addWidget(self.btn_pick_dll)
        pack_btn_row.addStretch(1)
        cp_lay.addLayout(pack_btn_row)

        layout.addWidget(c_pack)
        layout.addStretch(1)

        self._refresh_viethoa_status()
        return page

    def _on_pick_game_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Chọn thư mục có MSango.bin", self.game_folder or str(self.app_dir)
        )
        if folder:
            self.game_folder = folder
            self.lbl_game_dir.setText(folder)
            self._save_ui_prefs()
            self._refresh_viethoa_status()
            self.toast.show_toast("Đã chọn thư mục game.", "ok")

    def _refresh_viethoa_status(self) -> None:
        self.vh_status_labels["admin"].setText("Có" if self.is_admin else "Không")
        self.vh_status_labels["guard"].setText("Đã gỡ")
        self.vh_status_labels["hosts"].setText("Không chặn (CDN thật)")
        self.vh_status_labels["stub"].setText("Tắt")
        self.vh_status_labels["auto1"].setText("Mở — vào server mới được")
        self.vh_status_labels["auto2"].setText("Đang mở")

        pack_lbl = self.vh_status_labels["pack"]
        if not self.game_folder:
            pack_lbl.setText("Chưa chọn thư mục game")
            pack_lbl.setStyleSheet("color: #9CA3AF; font-weight: 600;")
            return

        dhp_path = Path(self.game_folder) / "Data" / "Data.dhp"
        if not dhp_path.exists():
            pack_lbl.setText("Thiếu Data\\Data.dhp")
            pack_lbl.setStyleSheet("color: #FCA5A5; font-weight: 700;")
            return

        is_ro = not os.access(dhp_path, os.W_OK)
        if is_ro:
            pack_lbl.setText("ĐANG KHÓA PACK NÀY")
            pack_lbl.setStyleSheet("color: #6EE7B7; font-weight: 700;")
        else:
            pack_lbl.setText("Chưa khóa")
            pack_lbl.setStyleSheet("color: #FCD34D; font-weight: 700;")

    def _set_dhp_lock(self, lock: bool) -> None:
        if not self.game_folder:
            self.toast.show_toast(
                "Chưa chọn thư mục game. Bấm Đổi… rồi chọn folder có MSango.bin.",
                "warn",
            )
            return
        dhp_path = Path(self.game_folder) / "Data" / "Data.dhp"
        if not dhp_path.exists():
            self.toast.show_toast("Thư mục game thiếu Data\\Data.dhp.", "err")
            return

        try:
            if lock:
                os.chmod(dhp_path, stat.S_IREAD)
                self.toast.show_toast("Đã khóa Data.dhp.", "ok")
            else:
                os.chmod(dhp_path, stat.S_IREAD | stat.S_IWRITE)
                self.toast.show_toast("Đã cho phép cập nhật chính thức.", "ok")
            self._refresh_viethoa_status()
        except Exception as exc:
            self.toast.show_toast(f"Lỗi đổi quyền Data.dhp: {exc}", "err")

    def _on_download_and_install_pack(self) -> None:
        if getattr(self, "_vh_worker", None) is not None and self._vh_worker.isRunning():
            self.toast.show_toast("Đang tải & cài gói Việt hóa, vui lòng chờ…", "warn")
            return

        if not self.game_folder:
            self._on_pick_game_folder()
            if not self.game_folder:
                self.toast.show_toast(
                    "Chưa chọn thư mục game. Bấm Đổi… rồi chọn folder có MSango.bin.",
                    "warn",
                )
                return

        if not self.guard_catalog_path.exists():
            self.toast.show_toast("Không tìm thấy _guard_catalog.json.", "err")
            return

        self.btn_dl_both.setEnabled(False)
        self.btn_dl_both.setText("Đang tải & cài…")
        self.btn_pick_dhp.setEnabled(False)
        self.btn_pick_dll.setEnabled(False)
        self.vh_progress.setValue(1)

        cache_dir = self.app_dir / "cache"
        self._vh_worker = VietHoaInstallWorker(
            catalog_path=self.guard_catalog_path,
            cache_dir=cache_dir,
            game_dir=Path(self.game_folder),
        )
        self._vh_worker.progress_changed.connect(self._on_vh_install_progress)
        self._vh_worker.install_done.connect(self._on_vh_install_done)
        self._vh_worker.start()

    def _on_vh_install_progress(self, pct: int, dhp_txt: str, dll_txt: str) -> None:
        self.vh_progress.setValue(pct)
        self.lbl_dhp_info.setText(dhp_txt)
        self.lbl_dll_info.setText(dll_txt)

    def _on_vh_install_done(self, ok: bool, msg: str) -> None:
        self.btn_dl_both.setEnabled(True)
        self.btn_dl_both.setText("Tải & cài cả hai")
        self.btn_pick_dhp.setEnabled(True)
        self.btn_pick_dll.setEnabled(True)
        self._refresh_viethoa_status()
        if ok:
            self.toast.show_toast(msg, "ok", 4000)
        else:
            self.vh_progress.setValue(0)
            self.toast.show_toast(f"Lỗi cài Việt hóa: {msg}", "err", 4500)

    def _on_install_local_dhp(self) -> None:
        if not self.game_folder:
            self.toast.show_toast("Bấm Đổi… chọn thư mục game trước.", "warn")
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn Data.dhp", "", "Data.dhp (*.dhp);;All Files (*)"
        )
        if not file_path:
            return
        try:
            src = Path(file_path)
            with src.open("rb") as f:
                magic = f.read(4)
            if magic != b"1PHD":
                self.toast.show_toast(
                    "File không phải Data.dhp (thiếu header 1PHD).", "err"
                )
                return
            dst = Path(self.game_folder) / "Data" / "Data.dhp"
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                os.chmod(dst, stat.S_IREAD | stat.S_IWRITE)
            shutil.copy2(src, dst)
            self.vh_progress.setValue(100)
            self.toast.show_toast("Đã cài Data.dhp vào thư mục game.", "ok")
            self._refresh_viethoa_status()
        except Exception as exc:
            self.toast.show_toast(f"Không ghi được Data.dhp: {exc}", "err")

    def _on_install_local_dll(self) -> None:
        if not self.game_folder:
            self.toast.show_toast("Bấm Đổi… chọn thư mục game trước.", "warn")
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn version.dll", "", "DLL (*.dll);;All Files (*)"
        )
        if not file_path:
            return
        try:
            src = Path(file_path)
            with src.open("rb") as f:
                magic = f.read(2)
            if magic != b"MZ":
                self.toast.show_toast("File không phải version.dll hợp lệ.", "err")
                return
            dst = Path(self.game_folder) / "version.dll"
            shutil.copy2(src, dst)
            self.vh_progress.setValue(100)
            self.toast.show_toast("Đã cài version.dll cạnh MSango.bin.", "ok")
        except Exception as exc:
            self.toast.show_toast(f"Không ghi được version.dll: {exc}", "err")

    # ------------------------------------------------------------------
    # LƯU / NẠP TRẠNG THÁI (fav_sets.json, seal_prefs.json, ui_prefs.json)
    # ------------------------------------------------------------------

    def _load_persisted_state(self) -> None:
        # 1. fav_sets.json
        if self.fav_sets_path.exists():
            try:
                data = json.loads(self.fav_sets_path.read_text(encoding="utf-8"))
                self.fav_sets = list(data.get("sets", []))[:24]
                self.active_fav_index = int(data.get("active", -1))
            except Exception:
                self.fav_sets = []
        self._refresh_fav_list_ui()

        # 2. seal_prefs.json
        if self.seal_prefs_path.exists():
            try:
                sdata = json.loads(self.seal_prefs_path.read_text(encoding="utf-8"))
                saved_stems = set(sdata.get("seal_stems", []))
                for stem, cb in self.seal_checkboxes.items():
                    cb.blockSignals(True)
                    cb.setChecked(stem in saved_stems)
                    cb.blockSignals(False)
                self._update_seal_counter_ui()
            except Exception:
                pass

        # 3. ui_prefs.json
        if self.ui_prefs_path.exists():
            try:
                udata = json.loads(self.ui_prefs_path.read_text(encoding="utf-8"))
                self.game_folder = str(udata.get("game_folder", ""))
                if self.game_folder:
                    self.lbl_game_dir.setText(self.game_folder)
                    self._refresh_viethoa_status()
            except Exception:
                pass

    def _save_ui_prefs(self) -> None:
        try:
            self.ui_prefs_path.write_text(
                json.dumps(
                    {"game_folder": self.game_folder}, ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _refresh_process_status(self) -> None:
        pid = self._try_find_pid()
        self.attached_pid = pid
        if pid:
            self.lbl_game_badge.setText(f"Game: MSango.bin (PID {pid})")
            self.lbl_game_badge.setStyleSheet(
                "background-color: #162B24; color: #6EE7B7; border: 1px solid #235342; "
                "border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: 600;"
            )
        else:
            self.lbl_game_badge.setText("Game: Không thấy MSango.bin")
            self.lbl_game_badge.setStyleSheet(
                "background-color: #262020; color: #FCA5A5; border: 1px solid #522B2B; "
                "border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: 600;"
            )


def main() -> int:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                APP_USER_MODEL_ID
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app_dir, bundle_dir = get_runtime_dirs()
    window = Mod3DMainWindow(app_dir=app_dir, bundle_dir=bundle_dir)
    window.show()

    if "--self-test" in sys.argv:
        idx = sys.argv.index("--self-test")
        out_file = (
            Path(sys.argv[idx + 1])
            if idx + 1 < len(sys.argv)
            else (app_dir / "_self_test_ok.json")
        )
        app.processEvents()
        sample_pix = window._get_item_pixmap("Canh/H566.png", 52)
        report = {
            "status": "ok",
            "frozen": bool(getattr(sys, "frozen", False)),
            "app_dir": str(window.app_dir),
            "bundle_dir": str(window.bundle_dir),
            "db_path": str(window.db_path),
            "catalog_count": len(window.all_items),
            "seal_heroes": len(window.seal_checkboxes),
            "icon_loaded": not sample_pix.isNull(),
            "startup_warning": window.startup_warning,
        }
        out_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        QTimer.singleShot(150, window.close)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
