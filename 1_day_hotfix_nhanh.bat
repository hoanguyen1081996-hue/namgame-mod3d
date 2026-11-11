@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === ĐỒNG BỘ NHANH HOTFIX (OFFSET / CATALOG) LÊN GITHUB (< 1 GIÂY) ===
set /p MSG="Nhập ghi chú sửa lỗi (Enter để dùng mặc định): "
if "%MSG%"=="" set MSG=Cập nhật nhanh cấu hình offset / catalog
python publish_release.py --hotfix --changelog "%MSG%" --push
echo.
pause
