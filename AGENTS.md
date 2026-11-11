# Quy Tắc Vận Hành & Tự Động Cập Nhật Từ Xa (Agent Rules)

Tài liệu này quy định kiến trúc chuẩn và quy trình bắt buộc dành cho AI Agent khi bảo trì, sửa lỗi và phát hành cập nhật từ xa cho công cụ độc lập `Mod3D_Standalone` (`d:\namgame\namgame_tool`).

## 1. Nguyên Tắc Phát Triển Độc Lập (Clean-Room Standalone)

- Toàn bộ dự án trong `d:\namgame\namgame_tool\` là ứng dụng quản lý bộ nhớ tiến trình nội bộ trên Windows được xây dựng độc lập từ đầu bằng Python 3.12 + PySide6 (`gui.py`, `main.py`, `win32_system_context.py`, `auto_updater.py`) và cơ sở dữ liệu SQLite cục bộ (`data/inject_catalog.db`).
- **Tuyệt đối không** sửa đổi mã máy (patch binary), không can thiệp cơ chế bản quyền/DRM của phần mềm bên thứ ba, và không nhúng hoặc thực thi tệp nhị phân thương mại bên ngoài. Mọi thay đổi tính năng phải viết trực tiếp trên mã nguồn sạch của dự án.
- Sau mỗi lần sửa các tệp Python cốt lõi trong `d:\namgame\namgame_tool\` (`gui.py`, `main.py`, `win32_system_context.py`, `auto_updater.py`), luôn đồng bộ bản sao tương ứng ra thư mục gốc `d:\namgame\`.

## 2. Kiến Trúc Tự Động Cập Nhật 2 Tầng Qua GitHub

- **Kho lưu trữ chính thức**: `hoanguyen1081996-hue/namgame-mod3d` (nhánh `main`), được cấu hình mặc định trong `DEFAULT_UPDATE_CONFIG` (`auto_updater.py`) và `update_config.json`.
- **Tệp điều phối chữ ký số**: `release/manifest.json` lưu phiên bản hiện hành, ghi chú cập nhật (`changelog`), thông tin bản thực thi (`exe.url`, `exe.sha256`, `exe.size`) và danh sách tệp cấu hình nóng (`hotfix_files`).

### Tầng 1 — Cập nhật Nóng (Hotfix `< 1 giây`, không cần khởi động lại Client)
- **Khi nào sử dụng**: Khi chỉ chỉnh sửa mẫu AOB / chuỗi con trỏ / offset bộ nhớ (`memory_config.json`), dữ liệu vật phẩm (`data/inject_catalog.db`), hoặc danh mục nhóm hiển thị (`_guard_catalog.json`).
- **Quy trình phát hành**:
  ```powershell
  cd d:\namgame\namgame_tool
  python publish_release.py --hotfix --changelog "Nội dung cập nhật offset/catalog" --push
  ```
  *(Hoặc chạy tệp `1_day_hotfix_nhanh.bat`).*
- **Lưu ý bắt buộc**: Ở Tầng 1, **không** dùng cờ `--bump-patch` và **không** cần đóng gói lại `.exe`. Máy Client khi mở ứng dụng (hoặc bấm nút `⟳ Cập nhật`) sẽ đối chiếu mã băm SHA-256 của 3 tệp trong `hotfix_files`, tự tải tệp khác biệt và gọi `Mod3DMainWindow.reload_runtime_assets()` để nạp nóng ngay trên giao diện đang mở.

### Tầng 2 — Phát hành Bản Thực Thi Mới (`Mod3D_Standalone.exe` qua GitHub Releases)
- **Khi nào sử dụng**: Khi sửa đổi mã nguồn Python (`gui.py`, `main.py`, `win32_system_context.py`, `auto_updater.py`, `build_exe.py`) hoặc bổ sung ảnh PNG mới vào `data/icons/`.
- **Quy trình phát hành**:
  ```powershell
  cd d:\namgame\namgame_tool
  python publish_release.py --bump-patch --rebuild-exe --zip --push --gh-release --changelog "Nội dung nâng cấp phiên bản mới"
  ```
  *(Hoặc chạy tệp `2_dong_goi_zip_va_release.bat`).*
- **Lưu ý bắt buộc**:
  1. Phải có cờ `--bump-patch` (tự động tăng `APP_VERSION` trong `auto_updater.py`, ví dụ `1.3.70` -> `1.3.71`) để Client nhận biết `parse_version_tuple(remote_version) > parse_version_tuple(local_version)`.
  2. Phải chạy `--rebuild-exe` **trước** khi sinh `release/manifest.json` để mã băm `exe.sha256` và `exe.size` trong manifest khớp tuyệt đối 100% với tệp `Mod3D_Standalone.exe` đăng lên GitHub Releases (`--gh-release`).
  3. Bản nén gửi máy khác luôn được xuất tự động ra `d:\namgame\Mod3D_Portable_Release.zip` khi kèm cờ `--zip`.

## 3. Quy Tắc Toàn Vẹn SHA-256 & Chống Độ Trễ CDN 0 Giây

1. **Bảo toàn byte giữa Windows và Git (`.gitattributes`)**:
   - Không được xóa hoặc sửa đổi quy tắc `*.json -text`, `*.db binary`, `*.png binary`, `*.ico binary` trong `d:\namgame\namgame_tool\.gitattributes`.
   - Nếu Git tự chuyển đổi `CRLF` (`\r\n`) sang `LF` (`\n`), mã băm SHA-256 của tệp trên GitHub sẽ lệch so với tệp cục bộ lúc tạo `release/manifest.json`, khiến bộ kiểm tra an toàn của Client từ chối bản cập nhật.
2. **Vượt bộ nhớ đệm CDN 5 phút & giới hạn API (`_resolve_latest_ref`)**:
   - `raw.githubusercontent.com/{owner}/{repo}/main/...` lưu đệm Fastly CDN 5 phút (`max-age=300`) và bỏ qua query string, còn `api.github.com` giới hạn 60 lượt/giờ khi không có token.
   - Do đó, `GitHubAutoUpdater._resolve_latest_ref()` bắt buộc giữ cơ chế ưu tiên truy vấn `https://github.com/{repo}.git/info/refs?service=git-upload-pack` để lấy mã commit SHA 40 ký tự thực thời và tải tệp qua đường dẫn bất biến `raw.githubusercontent.com/{repo}/{commit_sha}/...` (độ trễ 0 giây, không giới hạn rate-limit).
3. **Kiểm tra an toàn trước khi ghi đè**:
   - Mọi đường dẫn tệp trong `hotfix_files` phải đi qua `_safe_target_path()` để chặn tấn công Path Traversal (`..`).
   - Tệp tải về phải ghi vào tệp tạm `.upd_tmp`, đối chiếu khớp SHA-256 (và kiểm tra chữ ký PE `MZ` + dung lượng `> 1 MB` đối với `.exe`) rồi mới thay thế nguyên tử bằng `os.replace()`.

## 4. Quy Tắc PyInstaller One-File & Kiểm Thử Trước Phát Hành

- **Khởi động lại sau khi tự cập nhật `.exe`**: Trong `GitHubAutoUpdater.spawn_self_replace_and_exit()`, bắt buộc giữ thiết lập `PYINSTALLER_RESET_ENVIRONMENT=1` và xóa các biến môi trường bắt đầu bằng `_MEI` trước khi tiến trình con gọi lại `Mod3D_Standalone.exe` mới (tránh lỗi bootloader đọc nhầm thư mục giải nén tạm `_MEIPASS` cũ đã xóa).
- **Kiểm thử tự động bắt buộc sau mỗi lần build `.exe`**:
  Chạy kiểm tra tự động không cần mở cửa sổ thật (`QT_QPA_PLATFORM=offscreen`):
  ```powershell
  $env:QT_QPA_PLATFORM="offscreen"
  d:\namgame\namgame_tool\Mod3D_Standalone.exe --self-test "$env:TEMP\mod3d_selftest.json"
  ```
  Đảm bảo JSON kết quả trả về `"status": "ok"`, `"catalog_count": 1045`, `"seal_heroes": 55`, `"icon_loaded": true` và `"startup_warning": null`.
