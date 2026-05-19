# build_release.ps1
# Script build & đóng gói FireSmokeMonitor cho Windows.
# Chạy trong PowerShell ở thư mục gốc dự án.
#
# Yêu cầu: đã activate venv (.venv) và đã cài pyinstaller.
#   .\.venv\Scripts\Activate.ps1
#   pip install pyinstaller
#
# Sử dụng:
#   .\build_release.ps1

$ErrorActionPreference = "Stop"

Write-Host "==> 1. Dọn build cũ" -ForegroundColor Cyan
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist)  { Remove-Item -Recurse -Force dist }

Write-Host "==> 2. Chạy PyInstaller" -ForegroundColor Cyan
pyinstaller FireSmokeMonitor.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller thất bại" }

$RELEASE = "dist\FireSmokeMonitor"

Write-Host "==> 3. Copy tài nguyên runtime cạnh exe" -ForegroundColor Cyan

# Mô hình
New-Item -ItemType Directory -Force -Path "$RELEASE\models" | Out-Null
if (Test-Path "models\best.pt") {
    Copy-Item "models\best.pt" "$RELEASE\models\best.pt" -Force
    Write-Host "    + models\best.pt"
}

# Thư mục rỗng cho dữ liệu runtime
New-Item -ItemType Directory -Force -Path "$RELEASE\alerts"  | Out-Null
New-Item -ItemType Directory -Force -Path "$RELEASE\videos" | Out-Null
New-Item -ItemType Directory -Force -Path "$RELEASE\logs"   | Out-Null

# README cho người dùng cuối
@"
FireSmokeMonitor
================

Cách chạy:
    Bấm đúp FireSmokeMonitor.exe

Tài khoản mặc định:
    Username: admin
    Password: admin123
    => Hãy đổi mật khẩu ngay sau lần đăng nhập đầu tiên (mục Cài đặt).

Thư mục dữ liệu (tạo tự động):
    alerts/       — ảnh & video clip cảnh báo
    app_data.db   — CSDL người dùng, log, cấu hình
    .app_key      — khoá mã hoá mật khẩu SMTP (KHÔNG xoá, KHÔNG chia sẻ)

Mô hình:
    models/best.pt — trọng số YOLOv8 đã train. Có thể thay bằng file .pt
                    khác cùng cấu trúc nếu muốn.
"@ | Out-File -Encoding UTF8 "$RELEASE\README.txt"

Write-Host ""
Write-Host "==> Hoàn tất!" -ForegroundColor Green
Write-Host "Thư mục phát hành: $RELEASE"
Write-Host "File chạy:          $RELEASE\FireSmokeMonitor.exe"

# Tổng dung lượng
$size = (Get-ChildItem -Recurse $RELEASE | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host ("Dung lượng:         {0:N0} MB" -f $size)
