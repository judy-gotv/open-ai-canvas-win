# 影策 Windows 便携版启动脚本（作者：Passwd Word）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 18789

$env:CANVAS_BACKEND_ADDR = "127.0.0.1:$port"
$env:CANVAS_BACKEND_DATA_DIR = Join-Path $root "data"
$env:CANVAS_CORS_ORIGINS = "http://127.0.0.1:$port"
$env:CANVAS_PI_RUNTIME_DIR = Join-Path $root "agent-runtime\pi"
$env:CANVAS_NO_BROWSER = "1"  # 脚本自己等就绪后弹浏览器，关掉 exe 的自动弹窗避免重复
$env:PATH = (Join-Path $root "tools\node") + ";" + (Join-Path $root "tools\ffmpeg\bin") + ";" + $env:PATH

$exe = Join-Path $root "yingce.exe"
if (-not (Test-Path $exe)) { Write-Host "找不到 yingce.exe，请确认解压完整。"; pause; exit 1 }

$inUse = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
$url = "http://127.0.0.1:$port/"
if ($inUse) {
  Write-Host "端口 $port 已被占用，可能是影策已经在运行，直接打开页面…"
  Start-Process $url
  exit
}

Write-Host "正在启动影策后端…"
$proc = Start-Process -FilePath $exe -WorkingDirectory $root -PassThru -WindowStyle Minimized

$ready = $false
for ($i = 0; $i -lt 90; $i++) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { $ready = $true; break }
  } catch {}
  if ($proc.HasExited) {
    Write-Host ""
    Write-Host "启动失败，后端已退出（退出码 $($proc.ExitCode)）。"
    Write-Host "请检查 data 目录权限，或确认没有杀毒软件拦截。"
    pause; exit 1
  }
  Start-Sleep -Seconds 1
}
if (-not $ready) { Write-Host "等待超时，请检查后端是否正常启动。"; pause; exit 1 }

Write-Host ""
Write-Host "影策已启动：$url"
Write-Host "关闭本窗口不会停止服务；彻底退出请运行「停止影策.bat」。"
Start-Process $url
pause
