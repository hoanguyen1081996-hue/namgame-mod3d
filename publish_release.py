# -*- coding: utf-8 -*-
"""
Công cụ Phát hành & Đóng gói Tự động (Developer Publisher):
1. Chế độ Hotfix siêu tốc (< 1 giây, không cần build lại EXE):
   `python publish_release.py --hotfix --changelog "Cập nhật offset vũ khí" --push`
2. Chế độ Build Full EXE + Nén ZIP mang sang máy khác / đăng GitHub Release:
   `python publish_release.py --rebuild-exe --zip` (thêm `--bump-patch` khi muốn tăng số bản v1.3.70 -> v1.3.71)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List
import zipfile

from auto_updater import DEFAULT_UPDATE_CONFIG, sha256_file
from gui import DEFAULT_MEMORY_CONFIG

HOTFIX_TARGETS = [
    "memory_config.json",
    "_guard_catalog.json",
    "data/inject_catalog.db",
]


def read_current_version(proj_dir: Path) -> str:
    src = (proj_dir / "auto_updater.py").read_text(encoding="utf-8")
    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', src, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("Không tìm thấy hằng số APP_VERSION trong auto_updater.py")
    return m.group(1)


def bump_patch_version(proj_dir: Path) -> str:
    updater_file = proj_dir / "auto_updater.py"
    src = updater_file.read_text(encoding="utf-8")
    cur = read_current_version(proj_dir)
    parts = [int(x) for x in cur.split(".")]
    parts[-1] += 1
    new_ver = ".".join(str(x) for x in parts)
    updated = re.sub(
        r'^APP_VERSION\s*=\s*"[^"]+"',
        f'APP_VERSION = "{new_ver}"',
        src,
        count=1,
        flags=re.MULTILINE,
    )
    updater_file.write_text(updated, encoding="utf-8")
    print(f"[VERSION] Đã tăng phiên bản: {cur} -> {new_ver}")
    return new_ver


def ensure_runtime_configs(proj_dir: Path, repo_override: str = "") -> Dict[str, Any]:
    mem_path = proj_dir / "memory_config.json"
    if not mem_path.exists():
        mem_path.write_text(
            json.dumps(DEFAULT_MEMORY_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    upd_path = proj_dir / "update_config.json"
    cfg = dict(DEFAULT_UPDATE_CONFIG)
    if upd_path.exists():
        try:
            cfg.update(json.loads(upd_path.read_text(encoding="utf-8")))
        except Exception:
            pass
    if repo_override.strip():
        cfg["github_repo"] = repo_override.strip().strip("/")
    upd_path.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return cfg


def generate_manifest(
    proj_dir: Path, version: str, cfg: Dict[str, Any], changelog: str
) -> Path:
    repo = str(cfg.get("github_repo", "")).strip().strip("/")
    branch = str(cfg.get("branch", "main")).strip() or "main"

    exe_path = proj_dir / "Mod3D_Standalone.exe"
    exe_entry: Dict[str, Any] = {
        "url": (
            f"https://github.com/{repo}/releases/download/v{version}/Mod3D_Standalone.exe"
            if repo
            else ""
        ),
        "sha256": sha256_file(exe_path) if exe_path.is_file() else "",
        "size": exe_path.stat().st_size if exe_path.is_file() else 0,
    }

    hotfix_entries: List[Dict[str, Any]] = []
    for rel in HOTFIX_TARGETS:
        fpath = proj_dir / rel
        if not fpath.is_file():
            continue
        raw_url = (
            f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}" if repo else ""
        )
        hotfix_entries.append(
            {
                "path": rel,
                "url": raw_url,
                "sha256": sha256_file(fpath),
                "size": fpath.stat().st_size,
            }
        )

    manifest = {
        "version": version,
        "changelog": changelog or f"Bản phát hành v{version}",
        "exe": exe_entry,
        "hotfix_files": hotfix_entries,
    }

    rel_dir = proj_dir / "release"
    rel_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = rel_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[MANIFEST] Đã cập nhật chữ ký SHA-256 tại: {manifest_path}")
    return manifest_path


def create_portable_zip(proj_dir: Path, version: str, out_zip: Path) -> Path:
    exe_path = proj_dir / "Mod3D_Standalone.exe"
    if not exe_path.is_file():
        raise FileNotFoundError(
            "Chưa có Mod3D_Standalone.exe. Hãy chạy kèm --rebuild-exe trước."
        )

    readme_txt = (
        f"=== HƯỚNG DẪN SỬ DỤNG TOOL MOD 3D ĐỘC LẬP (v{version}) ===\r\n\r\n"
        "1. Giải nén toàn bộ thư mục 'Mod3D_Portable' ra ổ đĩa bất kỳ (VD: D:\\Mod3D_Portable).\r\n"
        "2. Chuột phải vào 'Mod3D_Standalone.exe' -> Chọn 'Run as administrator' (Chạy với quyền Quản trị).\r\n"
        "   (Không cần cài Python, không cần nhập Key License).\r\n"
        "3. Cập nhật tự động qua GitHub:\r\n"
        "   - Bấm nút '⟳ Cập nhật' ở góc trên bên phải, điền tên GitHub Repo (VD: ten-anh/mod3d-tool) -> Lưu.\r\n"
        "   - Từ lần sau, mỗi khi máy Dev đẩy bản sửa lỗi (offset / catalog / EXE mới) lên GitHub,\r\n"
        "     máy Test chỉ cần mở tool (hoặc bấm 'Kiểm tra ngay' -> 'Cập nhật ngay') là tự động cập nhật!\r\n"
    )

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    root_folder = "Mod3D_Portable"

    files_to_pack = [
        (exe_path, f"{root_folder}/Mod3D_Standalone.exe"),
        (proj_dir / "memory_config.json", f"{root_folder}/memory_config.json"),
        (proj_dir / "update_config.json", f"{root_folder}/update_config.json"),
        (proj_dir / "_guard_catalog.json", f"{root_folder}/_guard_catalog.json"),
        (proj_dir / "app_icon.png", f"{root_folder}/app_icon.png"),
        (
            proj_dir / "data" / "inject_catalog.db",
            f"{root_folder}/data/inject_catalog.db",
        ),
    ]

    icons_root = proj_dir / "data" / "icons"
    if icons_root.is_dir():
        for icon_file in sorted(icons_root.rglob("*")):
            if icon_file.is_file():
                rel_ic = icon_file.relative_to(proj_dir).as_posix()
                files_to_pack.append((icon_file, f"{root_folder}/{rel_ic}"))

    with zipfile.ZipFile(
        out_zip, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for src_p, arc_name in files_to_pack:
            if src_p.is_file():
                zf.write(src_p, arcname=arc_name)
        zf.writestr(f"{root_folder}/HUONG_DAN_CHAY.txt", readme_txt.encode("utf-8"))

    mb = out_zip.stat().st_size / (1024 * 1024)
    print(f"[ZIP OK] Đã đóng gói bản gửi máy khác: {out_zip} ({mb:.2f} MB)")
    return out_zip


def _find_gh_cli() -> str:
    default_gh = Path(r"C:\Program Files\GitHub CLI\gh.exe")
    if default_gh.is_file():
        return str(default_gh)
    return "gh"


def publish_github_release_asset(
    proj_dir: Path, version: str, repo: str, changelog: str
) -> None:
    exe_path = proj_dir / "Mod3D_Standalone.exe"
    if not exe_path.is_file():
        raise FileNotFoundError("Không tìm thấy Mod3D_Standalone.exe để đăng Release.")
    gh_bin = _find_gh_cli()
    tag = f"v{version}"
    notes = changelog or f"Bản phát hành {tag}"

    # Kiểm tra xem tag đã tồn tại chưa; nếu có thì upload đè (--clobber), chưa có thì tạo mới
    chk = subprocess.run(
        [gh_bin, "release", "view", tag, "--repo", repo],
        cwd=str(proj_dir),
        capture_output=True,
    )
    if chk.returncode == 0:
        subprocess.run(
            [
                gh_bin,
                "release",
                "upload",
                tag,
                str(exe_path),
                "--clobber",
                "--repo",
                repo,
            ],
            cwd=str(proj_dir),
            check=True,
        )
    else:
        subprocess.run(
            [
                gh_bin,
                "release",
                "create",
                tag,
                str(exe_path),
                "--title",
                f"Mod 3D {tag}",
                "--notes",
                notes,
                "--repo",
                repo,
            ],
            cwd=str(proj_dir),
            check=True,
        )
    print(f"[GITHUB RELEASE OK] Đã đăng tải {exe_path.name} lên Release {tag} ({repo})!")


def git_push_hotfix(proj_dir: Path, message: str) -> None:
    if not (proj_dir / ".git").exists():
        print(
            "[GIT] Thư mục chưa khởi tạo git remote. Bỏ qua bước tự push (chỉ cập nhật manifest cục bộ)."
        )
        return
    subprocess.run(["git", "add", "-A"], cwd=str(proj_dir), check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(proj_dir),
        check=False,
    )
    subprocess.run(["git", "push"], cwd=str(proj_dir), check=True)
    print("[GIT PUSH OK] Đã đẩy bản cập nhật lên GitHub!")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Công cụ đóng gói ZIP & xuất bản cập nhật tự động GitHub."
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="",
        help="Cập nhật tên GitHub Repo (VD: owner/repo) vào update_config.json",
    )
    parser.add_argument(
        "--bump-patch",
        action="store_true",
        help="Tự động tăng số phiên bản patch (VD: 1.3.70 -> 1.3.71)",
    )
    parser.add_argument(
        "--rebuild-exe",
        action="store_true",
        help="Đóng gói lại Mod3D_Standalone.exe bằng PyInstaller",
    )
    parser.add_argument(
        "--hotfix",
        action="store_true",
        help="Chỉ tạo lại manifest.json cho các file cấu hình/catalog (< 1s, không build lại EXE)",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Nén toàn bộ bản Portable sạch ra tệp Mod3D_Portable_Release.zip để gửi sang máy khác",
    )
    parser.add_argument(
        "--zip-out",
        type=Path,
        default=Path(r"d:\namgame\Mod3D_Portable_Release.zip"),
        help="Đường dẫn tệp .zip đầu ra",
    )
    parser.add_argument(
        "--changelog",
        type=str,
        default="",
        help="Ghi chú thay đổi hiển thị trên máy Client",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Tự động git commit & git push lên GitHub sau khi cập nhật manifest",
    )
    parser.add_argument(
        "--gh-release",
        action="store_true",
        help="Tự động tạo/cập nhật GitHub Release và tải Mod3D_Standalone.exe lên bằng gh CLI",
    )
    args = parser.parse_args()

    proj_dir = Path(__file__).resolve().parent
    cfg = ensure_runtime_configs(proj_dir, repo_override=args.repo)

    if args.bump_patch:
        version = bump_patch_version(proj_dir)
    else:
        version = read_current_version(proj_dir)

    if args.rebuild_exe and not args.hotfix:
        import build_exe

        build_exe.build()

    generate_manifest(
        proj_dir=proj_dir,
        version=version,
        cfg=cfg,
        changelog=args.changelog,
    )

    if args.zip:
        create_portable_zip(proj_dir=proj_dir, version=version, out_zip=args.zip_out)

    if args.push:
        git_push_hotfix(
            proj_dir, args.changelog or f"chore(release): update v{version}"
        )

    if args.gh_release:
        repo_name = str(cfg.get("github_repo", "")).strip()
        if not repo_name:
            raise ValueError("Chưa có github_repo trong update_config.json để tạo Release.")
        publish_github_release_asset(
            proj_dir=proj_dir,
            version=version,
            repo=repo_name,
            changelog=args.changelog,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
