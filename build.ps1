$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) { throw '请先运行 run.ps1 安装依赖' }
& $pythonExe (Join-Path $projectRoot 'assets\render_icon.py')
if ($LASTEXITCODE -ne 0) { throw '图标生成失败' }
$ffmpegExe = (Get-Command ffmpeg -ErrorAction Stop).Source
$ffprobeExe = (Get-Command ffprobe -ErrorAction Stop).Source
& $pythonExe -m PyInstaller --noconfirm --clean --windowed --onedir --name RetroKaraokeStudio --icon (Join-Path $projectRoot 'assets\icon.ico') --add-data "$(Join-Path $projectRoot 'assets\icon.png');assets" --add-binary "$ffmpegExe;bin" --add-binary "$ffprobeExe;bin" --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtPdf app.py
if ($LASTEXITCODE -ne 0) { throw 'EXE 打包失败' }
$distDir = Join-Path $projectRoot 'dist\RetroKaraokeStudio'
$conflictingIcu = Join-Path $distDir '_internal\icuuc.dll'
if (Test-Path $conflictingIcu) { Remove-Item -LiteralPath $conflictingIcu -Force }
Copy-Item (Join-Path $projectRoot 'README.md') $distDir -Force
Copy-Item (Join-Path $projectRoot 'LICENSE') $distDir -Force
Copy-Item (Join-Path $projectRoot 'LICENSES.md') $distDir -Force
Copy-Item (Join-Path $projectRoot 'THIRD_PARTY_NOTICES.md') $distDir -Force
Copy-Item (Join-Path $projectRoot 'TEST_REPORT.md') $distDir -Force
Copy-Item (Join-Path $projectRoot 'samples') (Join-Path $distDir 'samples') -Recurse -Force
$audioToLyricsSetup = Join-Path $projectRoot 'third_party\AudioToLyrics-v5.2.0-setup.exe'
if (Test-Path $audioToLyricsSetup) {
    $actualHash = (Get-FileHash -LiteralPath $audioToLyricsSetup -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne '283832eee047714b9f8d2701da4dedfeae3d66401fca26a4ad3de34bfc46d89c') { throw 'AudioToLyrics 官方安装包 SHA-256 不匹配' }
    $toolsDir = Join-Path $distDir 'Tools'
    New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
    Copy-Item -LiteralPath $audioToLyricsSetup -Destination $toolsDir -Force
} else {
    Write-Warning '未找到 AudioToLyrics 官方安装包；本次仅打包 Retro Karaoke Studio，仍可调用已安装的 AudioToLyrics。'
}
& $ffmpegExe -L | Out-File -FilePath (Join-Path $distDir 'FFMPEG_LICENSE.txt') -Encoding utf8
Write-Host (Join-Path $projectRoot 'dist\RetroKaraokeStudio\RetroKaraokeStudio.exe')
