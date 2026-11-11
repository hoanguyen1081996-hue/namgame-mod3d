@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === TĂNG PHIÊN BẢN + BUILD EXE + ĐẨY TỰ ĐỘNG LÊN GITHUB RELEASES ===
set /p MSG="Nhập nội dung bản cập nhật mới (Enter để dùng mặc định): "
if "%MSG%"=="" set MSG=Phát hành phiên bản mới
python publish_release.py --bump-patch --rebuild-exe --zip --push --gh-release --changelog "%MSG%"
echo.
echo [HOÀN TẤT 100%%] Đã đẩy mã nguồn + EXE lên GitHub Releases và cập nhật Mod3D_Portable_Release.zip!
pause
