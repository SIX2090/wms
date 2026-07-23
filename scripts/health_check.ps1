<#
.SYNOPSIS
    WMS 部署后健康检查脚本
.DESCRIPTION
    验证服务状态、端口监听、接口响应、日志生成等 10 项检查。
    输出检查结果与异常告警。
    AI-SEC-F01
.PARAMETER InstallDir
    WMS 安装目录，默认 C:\wms
.PARAMETER Port
    WMS 服务端口，默认 8080
.PARAMETER ServiceName
    nssm 服务名称，默认 WMS
.EXAMPLE
    .\health_check.ps1
.EXAMPLE
    .\health_check.ps1 -InstallDir E:\wms -Port 8080
#>
param(
    [string]$InstallDir = "C:\wms",
    [int]$Port = 8080,
    [string]$ServiceName = "WMS"
)

$ErrorActionPreference = "SilentlyContinue"
$results = @()

function Add-Check {
    param([string]$Name, [string]$Status, [string]$Detail)
    $script:results += [PSCustomObject]@{
        CheckNo  = $script:results.Count + 1
        Name     = $Name
        Status   = $Status
        Detail   = $Detail
    }
}

Write-Host "=" * 60
Write-Host "WMS 部署后健康检查 (AI-SEC-F01)"
Write-Host "安装目录: $InstallDir"
Write-Host "端口: $Port"
Write-Host "服务名: $ServiceName"
Write-Host "=" * 60
Write-Host ""

# 1. nssm 服务状态
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($svc) {
    if ($svc.Status -eq 'Running') {
        Add-Check "nssm 服务状态" "PASS" "服务 $ServiceName 正在运行"
    } else {
        Add-Check "nssm 服务状态" "FAIL" "服务 $ServiceName 状态为 $($svc.Status)，预期 Running"
    }
} else {
    Add-Check "nssm 服务状态" "FAIL" "服务 $ServiceName 不存在"
}

# 2. 服务进程存在
$proc = Get-Process -Name python -ErrorAction SilentlyContinue
if ($proc) {
    Add-Check "Python 进程" "PASS" "发现 $($proc.Count) 个 python 进程 (PID: $($proc.Id -join ','))"
} else {
    Add-Check "Python 进程" "FAIL" "未发现 python 进程，服务可能未启动"
}

# 3. 端口监听
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    Add-Check "端口监听" "PASS" "端口 $Port 正在监听 (PID: $($conn.OwningProcess | Select-Object -First 1))"
} else {
    Add-Check "端口监听" "FAIL" "端口 $Port 未监听"
}

# 4. HTTP 本机响应
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/login" -UseBasicParsing -TimeoutSec 10
    if ($resp.StatusCode -eq 200) {
        Add-Check "HTTP 响应" "PASS" "http://127.0.0.1:$Port/login 返回 200"
    } else {
        Add-Check "HTTP 响应" "WARN" "返回状态码 $($resp.StatusCode)，预期 200"
    }
} catch {
    Add-Check "HTTP 响应" "FAIL" "无法访问 http://127.0.0.1:$Port/login : $($_.Exception.Message)"
}

# 5. 登录页内容
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/login" -UseBasicParsing -TimeoutSec 10
    if ($resp.Content -match 'login' -or $resp.Content -match '登录') {
        Add-Check "登录页内容" "PASS" "页面包含登录表单"
    } else {
        Add-Check "登录页内容" "WARN" "页面内容未包含 'login' 关键字"
    }
} catch {
    Add-Check "登录页内容" "FAIL" "无法获取页面内容"
}

# 6. 数据库文件存在
$dbPath = Join-Path $InstallDir "app\instance\inventory.db"
if (Test-Path $dbPath) {
    $dbSize = (Get-Item $dbPath).Length
    Add-Check "数据库文件" "PASS" "数据库存在: $dbPath ($([math]::Round($dbSize/1KB, 1)) KB)"
} else {
    # 尝试备用路径
    $dbPath2 = Join-Path $InstallDir "instance\inventory.db"
    if (Test-Path $dbPath2) {
        Add-Check "数据库文件" "PASS" "数据库存在: $dbPath2"
    } else {
        Add-Check "数据库文件" "FAIL" "数据库文件不存在: $dbPath"
    }
}

# 7. 应用日志生成
$logPath = Join-Path $InstallDir "logs\app.log"
if (Test-Path $logPath) {
    $logSize = (Get-Item $logPath).Length
    if ($logSize -gt 0) {
        Add-Check "应用日志" "PASS" "日志文件存在且非空: $logPath ($([math]::Round($logSize/1KB, 1)) KB)"
    } else {
        Add-Check "应用日志" "WARN" "日志文件存在但为空: $logPath"
    }
} else {
    Add-Check "应用日志" "FAIL" "日志文件不存在: $logPath"
}

# 8. SECRET_KEY 持久化
$secretPath = Join-Path $InstallDir "app\instance\secret_key"
if (Test-Path $secretPath) {
    Add-Check "SECRET_KEY" "PASS" "secret_key 文件已持久化"
} else {
    $secretPath2 = Join-Path $InstallDir "instance\secret_key"
    if (Test-Path $secretPath2) {
        Add-Check "SECRET_KEY" "PASS" "secret_key 文件已持久化"
    } else {
        Add-Check "SECRET_KEY" "WARN" "secret_key 文件不存在（首次启动可能尚未生成）"
    }
}

# 9. auto_update 日志
$stdoutLog = Join-Path $InstallDir "logs\service_stdout.log"
if (Test-Path $stdoutLog) {
    $autoUpdateLine = Select-String -Path $stdoutLog -Pattern "AUTO_UPDATE" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($autoUpdateLine) {
        Add-Check "auto_update 日志" "PASS" "发现自动更新记录"
    } else {
        Add-Check "auto_update 日志" "WARN" "service_stdout.log 存在但未找到 AUTO_UPDATE 记录（可能已跳过）"
    }
} else {
    Add-Check "auto_update 日志" "WARN" "service_stdout.log 不存在（nssm 可能未配置 stdout 重定向）"
}

# 10. 防火墙规则
$fwRule = Get-NetFirewallRule -DisplayName "WMS*" -ErrorAction SilentlyContinue
if ($fwRule) {
    Add-Check "防火墙规则" "PASS" "发现 $($fwRule.Count) 条 WMS 防火墙规则"
} else {
    Add-Check "防火墙规则" "WARN" "未发现 WMS 防火墙规则（如由 Nginx 统一管理可忽略）"
}

# 输出结果
Write-Host ""
Write-Host "=" * 60
Write-Host "检查结果汇总"
Write-Host "=" * 60
$results | Format-Table -AutoSize

$passCount = ($results | Where-Object { $_.Status -eq 'PASS' }).Count
$failCount = ($results | Where-Object { $_.Status -eq 'FAIL' }).Count
$warnCount = ($results | Where-Object { $_.Status -eq 'WARN' }).Count

Write-Host ""
Write-Host "通过: $passCount | 失败: $failCount | 警告: $warnCount | 总计: $($results.Count)"
Write-Host ""

if ($failCount -gt 0) {
    Write-Host "[!!!] 存在 $failCount 项失败检查，部署可能异常！" -ForegroundColor Red
    Write-Host "失败项详情:"
    $results | Where-Object { $_.Status -eq 'FAIL' } | ForEach-Object {
        Write-Host "  - $($_.Name): $($_.Detail)" -ForegroundColor Red
    }
    exit 1
} elseif ($warnCount -gt 0) {
    Write-Host "[!] 存在 $warnCount 项警告，建议检查。" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "[OK] 全部检查通过。" -ForegroundColor Green
    exit 0
}
