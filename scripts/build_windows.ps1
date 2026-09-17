[CmdletBinding()]
param(
    [switch]$SkipFFmpegDownload
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$ffmpeg = Join-Path $root "vendor\ffmpeg.exe"
$icon = Join-Path $root "assets\cctv_downloader.ico"
$versionFile = Join-Path $root "packaging\version_info.txt"
$source = Join-Path $root "src\cctv_downloader.py"
$dist = Join-Path $root "dist"
$work = Join-Path $root "build\pyinstaller"
$spec = Join-Path $root "build\spec"

Push-Location $root
try {
    if (-not (Test-Path -LiteralPath $ffmpeg)) {
        if ($SkipFFmpegDownload) {
            throw "vendor\ffmpeg.exe is missing and -SkipFFmpegDownload was set"
        }
        & (Join-Path $PSScriptRoot "download_ffmpeg.ps1") -OutputPath $ffmpeg
    }

    $pythonExe = $env:PYTHON
    if (-not $pythonExe) {
        $pythonExe = (Get-Command python -ErrorAction Stop).Source
        & $pythonExe -c "import PyInstaller" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
            if ($pyLauncher) {
                $candidate = & $pyLauncher.Source -3.11 -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate) {
                    $pythonExe = $candidate.Trim()
                }
            }
        }
    }

    & $pythonExe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "Unit tests failed"
    }

    New-Item -ItemType Directory -Force -Path $dist, $work, $spec | Out-Null
    $arguments = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--noupx",
        "--name", "CCTVVideoDownloader",
        "--icon", $icon,
        "--version-file", $versionFile,
        "--add-binary", "$ffmpeg;.",
        "--add-data", "$icon;.",
        "--distpath", $dist,
        "--workpath", $work,
        "--specpath", $spec,
        $source
    )

    & $pythonExe @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed"
    }

    $exe = Join-Path $dist "CCTVVideoDownloader.exe"
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "Expected build output was not found: $exe"
    }

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash
    "$hash  CCTVVideoDownloader.exe" | Set-Content -Encoding ASCII (Join-Path $dist "SHA256SUMS.txt")
    Write-Host "Build complete: $exe"
    Write-Host "SHA-256: $hash"
}
finally {
    Pop-Location
}
