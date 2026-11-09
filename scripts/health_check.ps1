<#
.SYNOPSIS
    被动核对封存制品、计划任务和监听进程；不探测HTTP或数据库。
.DESCRIPTION
    AI-SEC-F01 既有运维入口的 BUG-2026-11-07-008/B3 修复。
    身份通过不代表业务健康或完整文件校验。无启停、安装、备份或恢复操作。
#>
param(
    [string]$InstallDir = '',
    [int]$Port = 8080,
    [string]$TaskName = 'WMS-Warehouse',
    [string]$ExpectedSourceSha = '',
    [string]$ExpectedPython = '',
    [string]$ExpectedEntry = '',
    [string]$EntryArguments = '',
    [string]$ValidatorPython = '',
    [switch]$IncludeLogMetadata
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'

# Optional file metadata only; preserve both supported log layouts and newest choice.
function Get-WmsLogMetadata {
    param([string]$InstallDir)
    $logCandidates = @(
        (Join-Path $InstallDir "app\logs\app.log"),
        (Join-Path $InstallDir "logs\app.log")
    )
    $logPath = $null
    foreach ($candidate in $logCandidates) {
        if (Test-Path -LiteralPath $candidate) {
            if ($null -eq $logPath -or (Get-Item -LiteralPath $candidate).LastWriteTime -gt (Get-Item -LiteralPath $logPath).LastWriteTime) {
                $logPath = $candidate
            }
        }
    }
    if ($null -ne $logPath) {
        $item = Get-Item -LiteralPath $logPath
        return @{ path=$logPath; last_write=$item.LastWriteTime.ToString('o'); bytes=$item.Length }
    }
    return $null
}

try {
    # Missing expectations fail before collecting system state or reading any file.
    foreach ($value in @($InstallDir,$ExpectedPython,$ExpectedEntry,$ValidatorPython)) {
        if (!$value -or ![IO.Path]::IsPathRooted($value)) { throw '请明确制品、解释器及入口绝对路径' }
    }
    if ($ExpectedSourceSha -cnotmatch '^[0-9a-f]{40}$' -or !$TaskName.Trim() -or $Port -lt 1 -or $Port -gt 65535) {
        throw '请明确完整来源SHA、计划任务名及有效端口'
    }
    $task = Get-ScheduledTask -TaskName $TaskName
    if (@($task).Count -ne 1) { throw '计划任务不唯一' }
    $allProcesses = @(Get-CimInstance Win32_Process)
    $processMap = @{}
    foreach ($row in $allProcesses) { $processMap[[int]$row.ProcessId] = $row }
    $listeners = @(Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq $Port | Select-Object -ExpandProperty OwningProcess -Unique)
    $rows = @()
    $seen = @{}
    foreach ($listenerPid in $listeners) {
        $currentId = [int]$listenerPid
        for ($depth=0; $depth -lt 32 -and $currentId -gt 0; $depth++) {
            if ($seen.ContainsKey($currentId)) { break }
            $seen[$currentId] = $true
            $row = $processMap[$currentId]
            if (!$row) { break }
            $ticks = $null
            if ($row.CreationDate) { $ticks = $row.CreationDate.ToUniversalTime().Ticks }
            $rows += @{pid=[int]$row.ProcessId; ppid=[int]$row.ParentProcessId; executable=$row.ExecutablePath; command=$row.CommandLine; created_ticks=$ticks}
            $currentId = [int]$row.ParentProcessId
        }
    }
    $packet = @{
        expected = @{release_root=$InstallDir; source_sha=$ExpectedSourceSha; python=$ExpectedPython; entry=$ExpectedEntry; entry_arguments=$EntryArguments; task_name=$TaskName; port=$Port}
        snapshot = @{
            port=$Port; listeners=@($listeners); processes=@($rows)
            task=@{name=$task.TaskName; state=[string]$task.State; actions=@($task.Actions | ForEach-Object { @{execute=$_.Execute; arguments=$_.Arguments} })}
        }
    }
    $validator = Join-Path $PSScriptRoot '..\tools\passive_wms_identity.py'
    $raw = $packet | ConvertTo-Json -Depth 8 -Compress
    $output = $raw | & $ValidatorPython -I -B -X utf8 $validator
    $code = $LASTEXITCODE
    if ($code -notin @(0,1,2)) { throw '身份校验器未正常完成' }
    $result = $output | ConvertFrom-Json
    if ($IncludeLogMetadata) { $result | Add-Member -NotePropertyName log_metadata -NotePropertyValue (Get-WmsLogMetadata $InstallDir) }
    $result | ConvertTo-Json -Depth 6 -Compress
    exit $code
} catch {
    # Never print raw process commands, task arguments, secrets or database paths.
    @{identity_verified=$false; failures=@('身份资料缺失或查询失败，请按现役手册核对参数和权限'); database_access=$false; http_request=$false; service_action=$false} | ConvertTo-Json -Compress
    exit 2
}
