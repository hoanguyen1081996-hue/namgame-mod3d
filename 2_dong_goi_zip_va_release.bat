@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === TĂNG PHIÊN BẢN + BUILD LẠI EXE + NÉN FILE ZIP MANG SANG MÁY KHÁC ===
set /p MSG="Nhập nội dung bản cập nhật mới: "
if "%MSG%"=="" set MSG=Phát hành phiên bản mới
python publish_release.py --bump-patch --rebuild-exe --zip --changelog "%MSG%"
echo.
echo [HOÀN TẤT] File ZIP gửi sang máy khác nằm tại: d:\namgame\Mod3D_Portable_Release.zip
echo Hãy đăng Mod3D_Standalone.exe lên mục Releases trên GitHub và chạy git push!
pause
