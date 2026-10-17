param(
    [string]$RepoUrl = "https://github.com/SIX2090/wms.git",
    [string]$Destination = (Join-Path $env:USERPROFILE "Desktop\wms-main")
)

$ErrorActionPreference = "Stop"

# AUDIT-FULL-20261016-001-F09-F03（原 A13）：原生 git 非零退出不会触发
# ErrorActionPreference=Stop，旧版每条命令都不检查退出码，拉取失败仍会打印
# "已准备 main 工作区"。这里统一包装：任何一步失败立即抛出，最后再核对本地/远端 SHA。
function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$What
    )
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ($What + " 失败（git 退出码 " + $LASTEXITCODE + "）：git " + ($Arguments -join " "))
    }
}

$destinationPath = [IO.Path]::GetFullPath($Destination)

if (Test-Path (Join-Path $destinationPath ".git")) {
    Invoke-Git -What "设置远程地址" -Arguments @("-C", $destinationPath, "remote", "set-url", "origin", $RepoUrl)
    Invoke-Git -What "拉取远端引用" -Arguments @("-C", $destinationPath, "fetch", "origin", "main")
    Invoke-Git -What "切换到 main" -Arguments @("-C", $destinationPath, "switch", "main")
    Invoke-Git -What "快进合并 main" -Arguments @("-C", $destinationPath, "pull", "--ff-only", "origin", "main")
} elseif (Test-Path $destinationPath) {
    $entries = @(Get-ChildItem -Force -LiteralPath $destinationPath)
    if ($entries.Count -gt 0) {
        throw "目标目录存在但不是 Git 仓库且不为空，请改用新目录或先人工备份: $destinationPath"
    }
    Invoke-Git -What "浅克隆 main" -Arguments @("clone", "--branch", "main", "--single-branch", $RepoUrl, $destinationPath)
} else {
    Invoke-Git -What "浅克隆 main" -Arguments @("clone", "--branch", "main", "--single-branch", $RepoUrl, $destinationPath)
}

Invoke-Git -What "配置 hooks 路径" -Arguments @("-C", $destinationPath, "config", "core.hooksPath", ".githooks")

$localHead = (& git -C $destinationPath rev-parse HEAD)
if ($LASTEXITCODE -ne 0) {
    throw "读取本地 HEAD 失败（git 退出码 $LASTEXITCODE）"
}
$remoteHead = (& git -C $destinationPath rev-parse "origin/main")
if ($LASTEXITCODE -ne 0) {
    throw "读取远端 main 失败（git 退出码 $LASTEXITCODE）"
}
if ($localHead.Trim() -ne $remoteHead.Trim()) {
    throw "本地 HEAD 与远端 main 不一致，未完成准备：$($localHead.Trim()) != $($remoteHead.Trim())"
}

Invoke-Git -What "查看工作区状态" -Arguments @("-C", $destinationPath, "status", "--short", "--branch")
Write-Host ("已准备 main 工作区: " + $destinationPath + " @ " + $localHead.Trim())
