# pack_source.ps1
# Đóng gói SOURCE CODE để upload lên GitHub / Copilot Chat / Claude.
# CHỈ giữ file .py, config, docs. KHÔNG bao gồm model, dataset, video, build artifacts.

$ErrorActionPreference = "Stop"

$root      = $PSScriptRoot
$stage     = Join-Path $root "_pack_tmp"
$zipName   = "FireSmokeMonitor_source.zip"
$zipPath   = Join-Path $root $zipName

Write-Host "[1/4] Dọn thư mục staging cũ..." -ForegroundColor Cyan
if (Test-Path $stage)   { Remove-Item $stage -Recurse -Force }
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

# Danh sách thư mục / file cần copy (chỉ source + config thiết yếu)
$includes = @(
    "src",
    "tools",
    "docs",
    "app.py",
    "build_release.ps1",
    "FireSmokeMonitor.spec",
    "pack_source.ps1",
    ".gitignore",
    "README.md"
)

# data/data.yaml (chỉ file yaml, không bao gồm ảnh/labels)
$dataYaml = Join-Path $root "data\data.yaml"

# Pattern loại trừ khi copy đệ quy
$excludeDirs  = @("__pycache__", ".venv", "build", "dist", "runs", "training_data",
                  "videos", "alerts", "models", "logs", "_pack_tmp")
$excludeFiles = @("*.pt", "*.pth", "*.onnx", "*.h5", "*.pkl",
                  "*.db", "*.sqlite", "*.sqlite3",
                  "*.mp4", "*.avi", "*.mkv", "*.mov",
                  "*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp",
                  "*.ico", "*.zip", "*.7z", "*.rar",
                  ".app_key", "*.log")

function Copy-Filtered {
    param([string]$src, [string]$dst)
    if (-not (Test-Path $src)) { return }

    if ((Get-Item $src) -is [System.IO.DirectoryInfo]) {
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
        Get-ChildItem -Path $src -Force | ForEach-Object {
            if ($_.PSIsContainer) {
                if ($excludeDirs -contains $_.Name) { return }
                Copy-Filtered -src $_.FullName -dst (Join-Path $dst $_.Name)
            } else {
                $skip = $false
                foreach ($pat in $excludeFiles) {
                    if ($_.Name -like $pat) { $skip = $true; break }
                }
                if (-not $skip) {
                    Copy-Item $_.FullName -Destination (Join-Path $dst $_.Name) -Force
                }
            }
        }
    } else {
        Copy-Item $src -Destination $dst -Force
    }
}

Write-Host "[2/4] Copy source files..." -ForegroundColor Cyan
foreach ($item in $includes) {
    $srcPath = Join-Path $root $item
    if (Test-Path $srcPath) {
        $dstPath = Join-Path $stage $item
        Copy-Filtered -src $srcPath -dst $dstPath
        Write-Host "  + $item"
    }
}

# Copy data/data.yaml riêng (không lấy cả thư mục data/)
if (Test-Path $dataYaml) {
    $dstYaml = Join-Path $stage "data\data.yaml"
    New-Item -ItemType Directory -Path (Split-Path $dstYaml) -Force | Out-Null
    Copy-Item $dataYaml -Destination $dstYaml -Force
    Write-Host "  + data/data.yaml"
}

# Tạo requirements.txt nhẹ (dump từ venv nếu có)
$venvPip = Join-Path $root ".venv\Scripts\pip.exe"
if (Test-Path $venvPip) {
    Write-Host "[3/4] Sinh requirements.txt từ venv..." -ForegroundColor Cyan
    & $venvPip freeze | Out-File -FilePath (Join-Path $stage "requirements.txt") -Encoding utf8
} else {
    Write-Host "[3/4] Bỏ qua requirements.txt (không có venv)" -ForegroundColor Yellow
}

Write-Host "[4/4] Nén ZIP..." -ForegroundColor Cyan
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force

# Dọn staging
Remove-Item $stage -Recurse -Force

$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  XONG! File: $zipPath" -ForegroundColor Green
Write-Host "  Kích thước: $sizeMB MB" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Upload file ZIP này lên GitHub / Claude / Copilot Chat để AI đọc source."
