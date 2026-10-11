@echo off
REM ============================================================
REM 启用 Print Spooler 服务（F1.5 / 审计 §7.2）
REM
REM 背景：本机 Print Spooler 被禁用且未运行，WMS 服务器端打印
REM （标签/单据）依赖它枚举与驱动打印机。
REM
REM 用法：右键 -> 以管理员身份运行。
REM ============================================================
setlocal EnableExtensions

net session >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 请以管理员身份运行本脚本（右键 -^> 以管理员身份运行）。
  pause
  exit /b 1
)

echo [1/3] 设置 Print Spooler 为自动启动...
sc config Spooler start= auto
if errorlevel 1 (
  echo [ERROR] sc config 失败。
  pause
  exit /b 1
)

echo [2/3] 启动 Print Spooler...
sc start Spooler
REM 1056 = 服务已在运行，视为成功
if errorlevel 1 (
  sc query Spooler | findstr /i "RUNNING" >nul
  if errorlevel 1 (
    echo [ERROR] Spooler 启动失败，请打开 services.msc 手动检查。
    pause
    exit /b 1
  )
)

echo [3/3] 验证服务状态与打印机枚举...
sc query Spooler | findstr /i "STATE"
powershell -NoProfile -Command "try { $p = Get-Printer -ErrorAction Stop; if ($p) { $p | Select-Object -ExpandProperty Name | ForEach-Object { Write-Output ('  printer: ' + $_) } } else { Write-Output '  (no printers installed yet)' } } catch { Write-Output ('  [WARN] Get-Printer failed: ' + $_.Exception.Message) }"

echo.
echo [OK] Print Spooler 已启用。WMS 服务器端打印功能可用。
pause
