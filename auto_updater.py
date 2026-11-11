# -*- coding: utf-8 -*-
"""
Hệ thống Tự động Cập nhật 2 Tầng qua GitHub (Auto-Updater):
- Tầng 1 (Hotfix < 1 giây, không cần khởi động lại): Đồng bộ tức thời `memory_config.json`,
  `data/inject_catalog.db`, `_guard_catalog.json` dựa trên đối chiếu mã băm SHA-256 từ `manifest.json`.
- Tầng 2 (Full EXE Update): Tải bản `Mod3D_Standalone.exe` mới từ GitHub Releases / Manifest,
  kiểm tra chữ ký SHA-256 + PE Header (`MZ`), tự tráo file an toàn và khởi động lại ứng dụng
  (có reset môi trường `PYINSTALLER_RESET_ENVIRONMENT` chống xung đột `_MEIPASS`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

APP_VERSION = "1.3.70"

DEFAULT_UPDATE_CONFIG: Dict[str, Any] = {
    "_comment": "Cấu hình tự động cập nhật từ GitHub Repo chính thức.",
    "github_repo": "hoanguyen1081996-hue/namgame-mod3d",
    "branch": "main",
    "manifest_url": "",
    "auto_check_on_startup": True,
    "sync_hotfix_files": True,
    "github_token": "",
}


def parse_version_tuple(ver_str: str) -> Tuple[int, ...]:
    """Chuyển chuỗi phiên bản (VD: 'v1.3.71' hoặc '1.3.70') thành tuple số nguyên để so sánh chuẩn."""
    cleaned = ver_str.strip().lstrip("vV")
    nums = [int(x) for x in re.findall(r"\d+", cleaned)]
    return tuple(nums) if nums else (0,)


def sha256_file(path: Path) -> str:
    """Tính mã băm SHA-256 của tệp trên đĩa."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(256 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


@dataclass
class HotfixItem:
    rel_path: str
    url: str
    sha256: str = ""
    size: int = 0


@dataclass
class UpdateCheckResult:
    configured: bool
    local_version: str = APP_VERSION
    remote_version: str = APP_VERSION
    has_exe_update: bool = False
    exe_url: str = ""
    exe_sha256: str = ""
    exe_size: int = 0
    changelog: str = ""
    hotfixes_to_apply: List[HotfixItem] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def has_any_update(self) -> bool:
        return self.has_exe_update or bool(self.hotfixes_to_apply)


class GitHubAutoUpdater:
    """Điều phối kiểm tra, tải về, xác thực SHA-256 và áp dụng bản cập nhật từ GitHub."""

    USER_AGENT = f"Mod3D-Standalone-Updater/{APP_VERSION}"

    def __init__(self, app_dir: Path, current_version: str = APP_VERSION) -> None:
        self.app_dir = app_dir.resolve()
        self.current_version = current_version
        self.config_path = self.app_dir / "update_config.json"
        self.ensure_config_file()

    def ensure_config_file(self) -> None:
        if not self.config_path.exists():
            try:
                bundled_cfg = (
                    Path(getattr(sys, "_MEIPASS", self.app_dir)) / "update_config.json"
                )
                if bundled_cfg.is_file() and bundled_cfg.resolve() != self.config_path:
                    self.config_path.write_text(
                        bundled_cfg.read_text(encoding="utf-8"), encoding="utf-8"
                    )
                else:
                    self.config_path.write_text(
                        json.dumps(DEFAULT_UPDATE_CONFIG, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
            except Exception:
                pass

    def load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return dict(DEFAULT_UPDATE_CONFIG)
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_UPDATE_CONFIG)
            merged.update(raw)
            return merged
        except Exception:
            return dict(DEFAULT_UPDATE_CONFIG)

    def save_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self.load_config()
        cfg.update(updates)
        self.config_path.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return cfg

    def _safe_target_path(self, rel_path: str) -> Path:
        """Đảm bảo đường dẫn tệp cập nhật luôn nằm bên trong `self.app_dir` (chống Path Traversal)."""
        clean_rel = rel_path.replace("\\", "/").lstrip("/")
        if not clean_rel or ".." in clean_rel.split("/"):
            raise ValueError(f"Đường dẫn cập nhật không hợp lệ: '{rel_path}'")
        target = (self.app_dir / clean_rel).resolve()
        if target == self.app_dir or self.app_dir not in target.parents:
            raise ValueError(f"Từ chối ghi ra ngoài thư mục ứng dụng: '{rel_path}'")
        return target

    def _build_headers(self, cfg: Dict[str, Any], accept_json: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": self.USER_AGENT,
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
        if accept_json:
            headers["Accept"] = "application/vnd.github+json, application/json"
        token = str(cfg.get("github_token", "")).strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def _with_cache_buster(url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        if "raw.githubusercontent.com" not in parsed.netloc.lower():
            return url
        q = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        q.append(("_cb", str(int(time.time()))))
        new_query = urllib.parse.urlencode(q)
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
        )

    def _http_get_json(self, url: str, cfg: Dict[str, Any], timeout: float = 12.0) -> Dict[str, Any]:
        final_url = self._with_cache_buster(url)
        req = urllib.request.Request(
            final_url, headers=self._build_headers(cfg, accept_json=True)
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)

    def _resolve_latest_ref(self, repo: str, branch: str, cfg: Dict[str, Any]) -> str:
        """
        Truy vấn mã SHA thực thời của nhánh `branch` thông qua giao thức Git Smart HTTP (`info/refs`)
        để vượt hoàn toàn cả bộ nhớ đệm CDN 5 phút của `raw.githubusercontent.com` lẫn giới hạn
        60 req/giờ của REST API (giúp Hotfix đồng bộ tức thời 0 giây ngay sau khi `git push`).
        """
        if not repo:
            return branch
        ctx = ssl.create_default_context()
        # Ưu tiên 1: Git Smart HTTP info/refs (không giới hạn rate-limit, không dính cache CDN 5 phút)
        try:
            refs_url = f"https://github.com/{repo}.git/info/refs?service=git-upload-pack"
            req = urllib.request.Request(refs_url, headers={"User-Agent": "git/2.43.0"})
            with urllib.request.urlopen(req, timeout=6.0, context=ctx) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            m = re.search(
                rf"([0-9a-f]{{40}})\s+refs/heads/{re.escape(branch)}(?:\x00|\s|$)",
                body,
            )
            if m:
                return m.group(1)
        except Exception:
            pass

        # Ưu tiên 2: GitHub REST API (dành cho repo private có cấu hình github_token)
        try:
            commit_api = f"https://api.github.com/repos/{repo}/commits/{branch}"
            data = self._http_get_json(commit_api, cfg, timeout=6.0)
            sha = str(data.get("sha", "")).strip()
            if len(sha) >= 7:
                return sha
        except Exception:
            pass
        return branch

    def check_for_updates(self) -> UpdateCheckResult:
        """
        Kiểm tra bản cập nhật từ `manifest.json` trên GitHub Raw (ưu tiên theo commit SHA mới nhất)
        hoặc tự động fallback sang GitHub Releases API (`/releases/latest`).
        """
        cfg = self.load_config()
        repo = str(cfg.get("github_repo", "")).strip().strip("/")
        branch = str(cfg.get("branch", "main")).strip() or "main"
        manifest_url = str(cfg.get("manifest_url", "")).strip()

        if not manifest_url and not repo:
            return UpdateCheckResult(configured=False, local_version=self.current_version)

        need_gh_ref = bool(repo) and (
            not manifest_url
            or manifest_url.startswith(f"https://raw.githubusercontent.com/{repo}/")
        )
        ref_commit = self._resolve_latest_ref(repo, branch, cfg) if need_gh_ref else branch
        if not manifest_url and repo:
            manifest_url = (
                f"https://raw.githubusercontent.com/{repo}/{ref_commit}/release/manifest.json"
            )
        elif (
            repo
            and ref_commit != branch
            and manifest_url.startswith(f"https://raw.githubusercontent.com/{repo}/{branch}/")
        ):
            manifest_url = manifest_url.replace(
                f"/{repo}/{branch}/", f"/{repo}/{ref_commit}/", 1
            )

        # 1. Thử đọc manifest.json (hỗ trợ cả Hotfix file lẻ + Full EXE)
        manifest_err: Optional[str] = None
        if manifest_url:
            try:
                manifest = self._http_get_json(manifest_url, cfg)
                return self._parse_manifest_response(manifest, cfg, repo, branch, ref_commit)
            except urllib.error.HTTPError as exc:
                manifest_err = f"HTTP {exc.code} khi đọc manifest"
                if exc.code != 404 or not repo:
                    return UpdateCheckResult(
                        configured=True,
                        local_version=self.current_version,
                        error=f"Không đọc được manifest ({exc.code}): {manifest_url}",
                    )
            except Exception as exc:
                manifest_err = str(exc)
                if not repo:
                    return UpdateCheckResult(
                        configured=True,
                        local_version=self.current_version,
                        error=f"Lỗi kết nối máy chủ cập nhật: {exc}",
                    )

        # 2. Fallback sang GitHub Releases API (/releases/latest) nếu repo chưa có release/manifest.json
        if repo:
            api_url = f"https://api.github.com/repos/{repo}/releases/latest"
            try:
                rel_data = self._http_get_json(api_url, cfg)
                return self._parse_github_release(rel_data)
            except Exception as exc:
                detail = f"{manifest_err}; Releases API: {exc}" if manifest_err else str(exc)
                return UpdateCheckResult(
                    configured=True,
                    local_version=self.current_version,
                    error=f"Không kiểm tra được GitHub ({repo}): {detail}",
                )

        return UpdateCheckResult(configured=False, local_version=self.current_version)

    def _parse_manifest_response(
        self,
        manifest: Dict[str, Any],
        cfg: Dict[str, Any],
        repo: str,
        branch: str,
        ref_commit: str = "",
    ) -> UpdateCheckResult:
        effective_ref = ref_commit or branch
        remote_ver = str(manifest.get("version", self.current_version)).strip()
        changelog = str(manifest.get("changelog", "")).strip()

        exe_info = manifest.get("exe") or {}
        exe_url = str(exe_info.get("url", "")).strip()
        if not exe_url and repo:
            exe_url = (
                f"https://github.com/{repo}/releases/download/v{remote_ver}/Mod3D_Standalone.exe"
            )
        exe_sha = str(exe_info.get("sha256", "")).strip().lower()
        exe_size = int(exe_info.get("size", 0) or 0)

        has_exe = bool(
            exe_url
            and parse_version_tuple(remote_ver) > parse_version_tuple(self.current_version)
        )

        hotfixes: List[HotfixItem] = []
        if bool(cfg.get("sync_hotfix_files", True)):
            for entry in manifest.get("hotfix_files") or []:
                rel_p = str(entry.get("path", "")).strip()
                raw_u = str(entry.get("url", "")).strip()
                expected_sha = str(entry.get("sha256", "")).strip().lower()
                f_size = int(entry.get("size", 0) or 0)

                if not rel_p:
                    continue
                if not raw_u and repo:
                    raw_u = f"https://raw.githubusercontent.com/{repo}/{effective_ref}/{rel_p.lstrip('/')}"
                elif (
                    repo
                    and effective_ref != branch
                    and raw_u.startswith(f"https://raw.githubusercontent.com/{repo}/{branch}/")
                ):
                    raw_u = raw_u.replace(
                        f"/{repo}/{branch}/", f"/{repo}/{effective_ref}/", 1
                    )
                if not raw_u:
                    continue

                target = self._safe_target_path(rel_p)
                if not target.exists():
                    hotfixes.append(
                        HotfixItem(
                            rel_path=rel_p, url=raw_u, sha256=expected_sha, size=f_size
                        )
                    )
                elif expected_sha:
                    local_sha = sha256_file(target)
                    if local_sha != expected_sha:
                        hotfixes.append(
                            HotfixItem(
                                rel_path=rel_p,
                                url=raw_u,
                                sha256=expected_sha,
                                size=f_size,
                            )
                        )

        return UpdateCheckResult(
            configured=True,
            local_version=self.current_version,
            remote_version=remote_ver,
            has_exe_update=has_exe,
            exe_url=exe_url,
            exe_sha256=exe_sha,
            exe_size=exe_size,
            changelog=changelog,
            hotfixes_to_apply=hotfixes,
        )

    def _parse_github_release(self, rel_data: Dict[str, Any]) -> UpdateCheckResult:
        tag = str(rel_data.get("tag_name", self.current_version)).strip()
        body = str(rel_data.get("body", "")).strip()
        exe_url = ""
        exe_sha = ""
        exe_size = 0

        for asset in rel_data.get("assets") or []:
            name = str(asset.get("name", ""))
            if name.lower().endswith(".exe"):
                exe_url = str(asset.get("browser_download_url", "")).strip()
                exe_size = int(asset.get("size", 0) or 0)
                digest = str(asset.get("digest", "")).strip().lower()
                if digest.startswith("sha256:"):
                    exe_sha = digest.split(":", 1)[1]
                break

        has_exe = bool(
            exe_url and parse_version_tuple(tag) > parse_version_tuple(self.current_version)
        )
        return UpdateCheckResult(
            configured=True,
            local_version=self.current_version,
            remote_version=tag.lstrip("vV") or tag,
            has_exe_update=has_exe,
            exe_url=exe_url,
            exe_sha256=exe_sha,
            exe_size=exe_size,
            changelog=body,
        )

    def _download_to_temp(
        self,
        url: str,
        tmp_path: Path,
        cfg: Dict[str, Any],
        expected_sha256: str = "",
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        final_url = self._with_cache_buster(url)
        req = urllib.request.Request(final_url, headers=self._build_headers(cfg))
        ctx = ssl.create_default_context()
        tmp_path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        downloaded = 0
        with urllib.request.urlopen(req, timeout=30.0, context=ctx) as resp:
            total = int(resp.headers.get("Content-Length", "0") or 0)
            with tmp_path.open("wb") as out:
                while True:
                    chunk = resp.read(128 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)

        if downloaded == 0:
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError(f"Tệp tải về bị rỗng: {url}")

        if expected_sha256:
            got_sha = hasher.hexdigest().lower()
            if got_sha != expected_sha256.lower():
                tmp_path.unlink(missing_ok=True)
                raise ValueError(
                    f"Sai mã kiểm tra SHA-256 (nhận {got_sha[:12]}…, cần {expected_sha256[:12]}…)"
                )

    @staticmethod
    def _validate_hotfix_payload(target: Path, tmp_path: Path) -> None:
        suffix = target.suffix.lower()
        if suffix == ".json":
            json.loads(tmp_path.read_text(encoding="utf-8"))
        elif suffix == ".db":
            with tmp_path.open("rb") as f:
                hdr = f.read(16)
            if hdr != b"SQLite format 3\x00":
                raise ValueError("Tệp tải về không phải cơ sở dữ liệu SQLite hợp lệ.")

    def apply_hotfixes(
        self,
        items: List[HotfixItem],
        progress_cb: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[str]:
        """Tải và ghi đè nguyên tử (atomic replace) các tệp cấu hình / catalog lẻ."""
        cfg = self.load_config()
        updated_paths: List[str] = []

        for idx, item in enumerate(items, start=1):
            target = self._safe_target_path(item.rel_path)
            tmp_path = target.with_name(f".{target.name}.upd_tmp")
            if progress_cb:
                progress_cb(item.rel_path, idx - 1, len(items))

            self._download_to_temp(
                url=item.url,
                tmp_path=tmp_path,
                cfg=cfg,
                expected_sha256=item.sha256,
            )
            try:
                self._validate_hotfix_payload(target, tmp_path)
                os.replace(tmp_path, target)
                updated_paths.append(item.rel_path)
            finally:
                tmp_path.unlink(missing_ok=True)

            if progress_cb:
                progress_cb(item.rel_path, idx, len(items))

        return updated_paths

    def download_new_exe(
        self,
        exe_url: str,
        expected_sha256: str = "",
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Tải bản `.exe` mới về `<Tên_EXE>.new` và xác thực chữ ký PE + SHA-256."""
        cfg = self.load_config()
        current_exe = (
            Path(sys.executable).resolve()
            if getattr(sys, "frozen", False)
            else (self.app_dir / "Mod3D_Standalone.exe")
        )
        staged_exe = current_exe.with_name(f"{current_exe.name}.new")
        staged_exe.unlink(missing_ok=True)

        self._download_to_temp(
            url=exe_url,
            tmp_path=staged_exe,
            cfg=cfg,
            expected_sha256=expected_sha256,
            progress_cb=progress_cb,
        )

        # Kiểm tra header thực thi Windows PE ('MZ') & dung lượng tối thiểu (> 1 MB)
        st_size = staged_exe.stat().st_size
        with staged_exe.open("rb") as f:
            mz = f.read(2)
        if mz != b"MZ" or st_size < 1024 * 1024:
            staged_exe.unlink(missing_ok=True)
            raise ValueError(
                "Tệp tải về không phải tệp .exe hợp lệ (có thể link tải trả về trang HTML)."
            )

        return staged_exe

    @staticmethod
    def spawn_self_replace_and_exit(staged_exe: Path) -> None:
        """
        Khởi chạy tiến trình nền `.cmd` đợi tiến trình hiện tại đóng hoàn toàn,
        ghi đè tệp `.exe` mới và tự mở lại ứng dụng với môi trường PyInstaller sạch.
        """
        if not getattr(sys, "frozen", False):
            # Nếu đang chạy bằng python gui.py thì chỉ ghi đè Mod3D_Standalone.exe cạnh đó
            target_exe = staged_exe.with_name(staged_exe.name[:-4])
            os.replace(staged_exe, target_exe)
            return

        current_exe = Path(sys.executable).resolve()
        updater_cmd = current_exe.parent / "_mod3d_apply_update.cmd"
        pid = os.getpid()

        script_lines = [
            "@echo off",
            "chcp 65001 >nul",
            f'set "TARGET={current_exe}"',
            f'set "STAGED={staged_exe}"',
            ":wait_loop",
            f'tasklist /FI "PID eq {pid}" 2>nul | find /I "{pid}" >nul',
            "if not errorlevel 1 (",
            "    timeout /t 1 /nobreak >nul",
            "    goto wait_loop",
            ")",
            "for /L %%i in (1,1,10) do (",
            '    move /Y "%STAGED%" "%TARGET%" >nul 2>nul && goto launched',
            "    timeout /t 1 /nobreak >nul",
            ")",
            ":launched",
            'start "" "%TARGET%"',
            'del "%~f0" >nul 2>nul',
        ]
        updater_cmd.write_text("\r\n".join(script_lines) + "\r\n", encoding="utf-8")

        # Quan trọng: Reset biến môi trường nội bộ của PyInstaller (_MEIPASS2) để bản .exe mới
        # tự giải nén thư mục _MEI mới thay vì đọc nhầm thư mục tạm của bản cũ!
        clean_env = os.environ.copy()
        clean_env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        for k in list(clean_env.keys()):
            if k.startswith("_MEI"):
                clean_env.pop(k, None)

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.Popen(
            ["cmd.exe", "/c", str(updater_cmd)],
            cwd=str(current_exe.parent),
            env=clean_env,
            creationflags=creation_flags,
            close_fds=True,
        )
