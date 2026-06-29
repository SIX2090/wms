param(
    [string]$RootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$DistDir = ''
)

$ErrorActionPreference = 'Stop'

if (-not $DistDir) {
    $DistDir = Join-Path $RootDir 'dist\WMS'
}

$root = (Resolve-Path $RootDir).Path
$dist = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DistDir)
$appSrc = Join-Path $root 'app'
$wheelhouse = Join-Path $root 'wheelhouse'
$pythonInstaller = Join-Path $root 'runtime\python-3.11.9-amd64.exe'
$pythonEmbedZip = Join-Path $root 'runtime\python-3.11.9-embed-amd64.zip'
$pythonDir = Join-Path $dist 'python'
$pythonExe = Join-Path $pythonDir 'python.exe'
$sitePackages = Join-Path $pythonDir 'Lib\site-packages'

if (-not (Test-Path (Join-Path $appSrc 'app.py'))) {
    throw "app\app.py not found under $root"
}
if (-not (Test-Path $wheelhouse)) {
    throw "wheelhouse not found under $root"
}

Write-Host '============================================================'
Write-Host 'Building portable WMS package'
Write-Host "Root: $root"
Write-Host "Dist: $dist"
Write-Host '============================================================'

$py = $null
$candidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
    (Join-Path $env:ProgramFiles 'Python311\python.exe')
)
foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
        $py = $candidate
        break
    }
}
if (-not $py) {
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $py = $cmd.Source
    }
}
if (-not $py) {
    throw 'Build machine needs Python 3.11 to install wheels into the portable runtime. User machines do not need Python after this package is built.'
}

Write-Host "[1/6] Cleaning dist..."
if (Test-Path $dist) {
    Remove-Item -LiteralPath $dist -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $dist | Out-Null

Write-Host "[2/6] Copying application files..."
robocopy $appSrc (Join-Path $dist 'app') /E /XD __pycache__ instance backups logs /XF *.pyc | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "robocopy app failed with exit code $LASTEXITCODE"
}
robocopy (Join-Path $root 'tools') (Join-Path $dist 'tools') /E /XD __pycache__ /XF *.pyc | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "robocopy tools failed with exit code $LASTEXITCODE"
}

Get-ChildItem -LiteralPath $dist -Recurse -Include *.bat,*.cmd | Where-Object { -not $_.PSIsContainer } | ForEach-Object {
    $text = [System.IO.File]::ReadAllText($_.FullName)
    $text = [regex]::Replace($text, "`r?`n", "`r`n")
    [System.IO.File]::WriteAllText($_.FullName, $text, [System.Text.Encoding]::ASCII)
}

Write-Host "[3/6] Creating embedded Python runtime..."
if (-not (Test-Path $pythonEmbedZip)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $pythonEmbedZip -Parent) | Out-Null
    $embedUrl = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip'
    Write-Host "Downloading embedded Python: $embedUrl"
    Invoke-WebRequest -Uri $embedUrl -OutFile $pythonEmbedZip
}
Expand-Archive -LiteralPath $pythonEmbedZip -DestinationPath $pythonDir -Force
New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null
$pth = Join-Path $pythonDir 'python311._pth'
if (Test-Path $pth) {
    $pthLines = [System.IO.File]::ReadAllLines($pth)
    $newLines = New-Object System.Collections.Generic.List[string]
    $hasPythonDir = $false
    $hasAppDir = $false
    $hasSitePackages = $false
    $hasImportSite = $false
    foreach ($line in $pthLines) {
        if ($line.Trim() -eq '.') {
            $hasPythonDir = $true
        }
        if ($line.Trim() -eq '..\app') {
            $hasAppDir = $true
        }
        if ($line.Trim() -eq 'Lib\site-packages') {
            $hasSitePackages = $true
        }
        if ($line.Trim() -eq 'import site' -or $line.Trim() -eq '#import site') {
            if (-not $hasPythonDir) {
                $newLines.Add('.')
                $hasPythonDir = $true
            }
            if (-not $hasAppDir) {
                $newLines.Add('..\app')
                $hasAppDir = $true
            }
            if (-not $hasSitePackages) {
                $newLines.Add('Lib\site-packages')
                $hasSitePackages = $true
            }
            $newLines.Add('import site')
            $hasImportSite = $true
        } else {
            $newLines.Add($line)
        }
    }
    if (-not $hasPythonDir) {
        $newLines.Add('.')
    }
    if (-not $hasAppDir) {
        $newLines.Add('..\app')
    }
    if (-not $hasSitePackages) {
        $newLines.Add('Lib\site-packages')
    }
    if (-not $hasImportSite) {
        $newLines.Add('import site')
    }
    [System.IO.File]::WriteAllLines($pth, $newLines, [System.Text.Encoding]::ASCII)
}

Write-Host "[4/6] Installing dependencies into dist\WMS\python..."
& $py -m pip install --no-index --find-links $wheelhouse -r (Join-Path $dist 'app\requirements.txt') --target $sitePackages --upgrade
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to install WMS dependencies from wheelhouse.'
}

Write-Host "[5/6] Writing portable launchers..."
$startName = ([string][char]0x542F) + ([string][char]0x52A8) + 'WMS.bat'
function Write-BatFile($Path, [string[]]$Lines) {
    [System.IO.File]::WriteAllText($Path, (($Lines -join "`r`n") + "`r`n"), [System.Text.Encoding]::ASCII)
}

Write-BatFile (Join-Path $dist $startName) @(
    '@echo off',
    'setlocal EnableExtensions',
    'chcp 65001 >nul',
    'cd /d "%~dp0" || exit /b 1',
    'call "%~dp0app\start_wms_offline.bat" %*'
)

Write-BatFile (Join-Path $dist 'WMS.bat') @(
    '@echo off',
    'setlocal EnableExtensions',
    'cd /d "%~dp0" || exit /b 1',
    'call "%~dp0app\start_wms_offline.bat" %*'
)

Write-BatFile (Join-Path $dist 'open_login.bat') @(
    '@echo off',
    'start "" "http://127.0.0.1:8080/login"'
)

Write-BatFile (Join-Path $dist 'stop_wms.bat') @(
    '@echo off',
    'call "%~dp0app\stop_wms_offline.bat" %*'
)

$exeSource = @"
using System;
using System.Diagnostics;
using System.IO;

public static class Program
{
    public static void Main()
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string bat = Path.Combine(dir, "app", "start_wms_offline.bat");
        var psi = new ProcessStartInfo("cmd.exe", "/c \"" + bat + "\"")
        {
            WorkingDirectory = dir,
            UseShellExecute = false,
            CreateNoWindow = false
        };
        Process.Start(psi);
    }
}
"@
try {
    Add-Type -TypeDefinition $exeSource -OutputAssembly (Join-Path $dist 'WMS.exe') -OutputType WindowsApplication
} catch {
    Write-Warning "WMS.exe was not generated: $($_.Exception.Message). The startup batch file is still available."
}

Write-Host "[6/6] Smoke testing embedded runtime..."
& $pythonExe -m py_compile (Join-Path $dist 'app\app.py') (Join-Path $dist 'app\config.py') (Join-Path $dist 'app\utils.py')
if ($LASTEXITCODE -ne 0) {
    throw 'Portable runtime smoke test failed.'
}

Write-Host ''
Write-Host '============================================================'
Write-Host '[OK] Portable WMS package built'
Write-Host "Start: $dist\$startName"
Write-Host "Optional: $dist\WMS.exe"
Write-Host 'Login: http://127.0.0.1:8080/login'
Write-Host 'Username: admin'
Write-Host 'Password: admin123'
Write-Host '============================================================'
