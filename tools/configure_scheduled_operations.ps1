<# Preview first. -Apply requires the exact original task hash from the preview.
Does not start, stop, or restart a service, open SQLite, or change credentials. #>
param(
    [Parameter(Mandatory=$true)][string]$ServiceTaskName,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$BackupSource,
    [Parameter(Mandatory=$true)][string]$BackupDirectory,
    [Parameter(Mandatory=$true)][string]$StateDirectory,
    [string]$SourceRoot = (Split-Path $PSScriptRoot -Parent),
    [string]$BackupTime = '02:00',
    [ValidateRange(1,2147483647)][int]$RetentionDays = 30,
    [string]$ExpectedDefinitionHash,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
function Get-DefinitionHash([string]$Text) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)) | ForEach-Object { $_.ToString('x2') }) }
    finally { $sha.Dispose() }
}
function Full-Path([string]$Value) {
    if ($Value -match '["\r\n]') { throw '路径不能包含引号或换行' }
    $path = [IO.Path]::GetFullPath($Value)
    if ($path -eq [IO.Path]::GetPathRoot($path)) { throw '请使用独立子目录或具体文件，不能使用盘符根目录' }
    return $path.TrimEnd('\')
}
$PythonExe = Full-Path $PythonExe
$SourceRoot = Full-Path $SourceRoot
$BackupSource = Full-Path $BackupSource
$BackupDirectory = Full-Path $BackupDirectory
$StateDirectory = Full-Path $StateDirectory
$supervisor = Join-Path $SourceRoot 'tools\supervise_process.py'
$backupRunner = Join-Path $SourceRoot 'tools\run_scheduled_backup.py'
foreach ($file in @($PythonExe, $BackupSource, $supervisor, $backupRunner)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw '指定解释器、源库或程序文件不存在；未修改任务' }
}
if ($BackupTime -notmatch '^([01]\d|2[0-3]):([0-5]\d)$') { throw '备份时刻必须为HH:MM' }
$hour = [int]$Matches[1]; $minute = [int]$Matches[2]
if (Test-Path -LiteralPath $StateDirectory) {
    throw '运维状态目录已存在，拒绝覆盖；请使用全新独立目录'
}
$task = Get-ScheduledTask -TaskName $ServiceTaskName
if (@($task.Actions).Count -ne 1 -or -not $task.Actions[0].Execute) { throw '只支持一个明确的可执行启动动作' }
if ($task.Principal.LogonType -notin @('ServiceAccount','Interactive','InteractiveToken','S4U')) {
    throw '当前任务登录方式需要另外提供凭据；本工具不读取或修改凭据，拒绝继续'
}
$original = Export-ScheduledTask -TaskName $ServiceTaskName
$hash = Get-DefinitionHash $original
$backupTaskName = $ServiceTaskName + '-DailyBackup'
if (Get-ScheduledTask -TaskName $backupTaskName -ErrorAction SilentlyContinue) { throw '同名每日备份任务已存在，拒绝覆盖' }
$plan = [ordered]@{ serviceTask=$ServiceTaskName; backupTask=$backupTaskName; definitionHash=$hash;
    executionTimeLimit='PT0S'; multipleInstances='IgnoreNew'; maxProcessRestarts=3; restartDelaySeconds=60;
    backupTime=$BackupTime; backupSource=$BackupSource; backupDirectory=$BackupDirectory;
    retentionDays=$RetentionDays;
    stateDirectory=$StateDirectory; serviceRestarted=$false; databaseOpened=$false; applied=$false }
if (-not $Apply) { $plan | ConvertTo-Json -Depth 5; return }
if (-not $ExpectedDefinitionHash -or $ExpectedDefinitionHash -cne $hash) { throw '任务定义与已审核预览不一致，拒绝应用' }
if ((Get-DefinitionHash (Export-ScheduledTask -TaskName $ServiceTaskName)) -cne $hash) { throw '任务定义已变化，拒绝应用' }

New-Item -ItemType Directory -Path $StateDirectory -ErrorAction Stop | Out-Null
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true, $false)
foreach ($identity in @([Security.Principal.WindowsIdentity]::GetCurrent().User,
        [Security.Principal.SecurityIdentifier]::new('S-1-5-18'),
        [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity, 'FullControl',
        'ContainerInherit,ObjectInherit', 'None', 'Allow'))
}
$directoryInfo = [IO.DirectoryInfo]::new($StateDirectory)
if ($directoryInfo.PSObject.Methods.Name -contains 'SetAccessControl') {
    $directoryInfo.SetAccessControl($acl)
} else {
    [IO.FileSystemAclExtensions]::SetAccessControl($directoryInfo, $acl)
}
[IO.File]::WriteAllText((Join-Path $StateDirectory 'service-task.before.xml'), $original, [Text.Encoding]::Unicode)
$actionFile = Join-Path $StateDirectory 'service-action.json'
$action = @{ execute=$task.Actions[0].Execute; arguments=[string]$task.Actions[0].Arguments;
             directory=[string]$task.Actions[0].WorkingDirectory }
[IO.File]::WriteAllText($actionFile, ($action | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$serviceArguments = '"' + $supervisor + '" --state-directory "' + (Join-Path $StateDirectory 'monitor') +
    '" --max-restarts 3 --restart-delay 60 --windows-action-file "' + $actionFile + '"'
$serviceAction = New-ScheduledTaskAction -Execute $PythonExe -Argument $serviceArguments
if ($task.Actions[0].WorkingDirectory) { $serviceAction.WorkingDirectory = $task.Actions[0].WorkingDirectory }
$settings = [Microsoft.Management.Infrastructure.CimInstance]::new($task.Settings)
$settings.ExecutionTimeLimit = 'PT0S'
$settings.MultipleInstances = 2
$backupAction = New-ScheduledTaskAction -Execute $PythonExe -Argument (
    '"' + $backupRunner + '" --source "' + $BackupSource + '" --directory "' + $BackupDirectory + '" --retention-days ' + $RetentionDays)
$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($hour).AddMinutes($minute))
$backupSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
$created = $false
try {
    Register-ScheduledTask -TaskName $backupTaskName -Action $backupAction -Trigger $trigger -Settings $backupSettings -Principal $task.Principal | Out-Null
    $created = $true
    if ((Get-DefinitionHash (Export-ScheduledTask -TaskName $ServiceTaskName)) -cne $hash) { throw '应用前任务被其他操作者修改，拒绝覆盖' }
    Set-ScheduledTask -TaskName $ServiceTaskName -Action $serviceAction -Settings $settings | Out-Null
    $plan.applied = $true
    $plan.updatedDefinitionHash = Get-DefinitionHash (Export-ScheduledTask -TaskName $ServiceTaskName)
    [IO.File]::WriteAllText((Join-Path $StateDirectory 'applied-plan.json'), ($plan | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    $plan | ConvertTo-Json -Depth 5
} catch {
    if ($created) {
        $ownedBackup = Get-ScheduledTask -TaskName $backupTaskName -ErrorAction SilentlyContinue
        if ($ownedBackup -and $ownedBackup.Actions[0].Execute -ceq $PythonExe -and
                $ownedBackup.Actions[0].Arguments -ceq $backupAction.Arguments) {
            Unregister-ScheduledTask -TaskName $backupTaskName -Confirm:$false
        }
    }
    $current = Get-ScheduledTask -TaskName $ServiceTaskName
    if ($current.Actions[0].Execute -ceq $PythonExe -and $current.Actions[0].Arguments -ceq $serviceArguments) {
        Register-ScheduledTask -TaskName $ServiceTaskName -Xml $original -Force | Out-Null
    }
    throw
}
