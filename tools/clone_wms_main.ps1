param(
    [string]$RepoUrl = "https://github.com/SIX2090/wms.git",
    [string]$Destination = (Join-Path $env:USERPROFILE "Desktop\wms-main")
)

$ErrorActionPreference = "Stop"
$destinationPath = [IO.Path]::GetFullPath($Destination)

if (Test-Path (Join-Path $destinationPath ".git")) {
    git -C $destinationPath remote set-url origin $RepoUrl
    git -C $destinationPath fetch origin main
    git -C $destinationPath switch main
    git -C $destinationPath pull --ff-only origin main
} elseif (Test-Path $destinationPath) {
    $entries = @(Get-ChildItem -Force -LiteralPath $destinationPath)
    if ($entries.Count -gt 0) {
        throw "目标目录存在但不是 Git 仓库且不为空，请改用新目录或先人工备份: $destinationPath"
    }
    git clone --branch main --single-branch $RepoUrl $destinationPath
} else {
    git clone --branch main --single-branch $RepoUrl $destinationPath
}

git -C $destinationPath config core.hooksPath .githooks
git -C $destinationPath status --short --branch
Write-Host "已准备 main 工作区: $destinationPath"
