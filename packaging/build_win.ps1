# Windows 打包：生成 dist\NardoFoxWriteDesk\NardoFoxWriteDesk.exe（可选再出安装包）
# 用法：powershell -ExecutionPolicy Bypass -File packaging\build_win.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python -m PyInstaller --noconfirm packaging\app.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败" }

$exe = Join-Path $PWD "dist\NardoFoxWriteDesk\NardoFoxWriteDesk.exe"
if (-not (Test-Path $exe)) { throw "没找到 $exe" }

# 冒烟测试：无界面跑 1.8 秒，退出码 0 才算过
$env:QT_QPA_PLATFORM = "offscreen"
$p = Start-Process -FilePath $exe -ArgumentList "--smoke" -PassThru -Wait
if ($p.ExitCode -ne 0) { throw "冒烟测试失败，退出码 $($p.ExitCode)" }
Write-Host "构建完成：$exe"

# 有 Inno Setup 就顺手生成安装包
$iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $guess = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
    if (Test-Path $guess) { $iscc = Get-Item $guess }
}
if ($iscc) {
    & $iscc.Source "packaging\win\installer.iss"
    Write-Host "安装包：dist\installer\NardoFoxWriteDesk-Setup-2.9.exe"
} else {
    Write-Host "没装 Inno Setup，跳过安装包；装好后运行 iscc packaging\win\installer.iss"
}
