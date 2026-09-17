[CmdletBinding()]
param(
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) {
    $OutputPath = Join-Path $root "vendor\ffmpeg.exe"
}

$ffmpegVersion = "9.0.1"
$archiveUrl = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-$ffmpegVersion-essentials_build.zip"
$checksumUrl = "$archiveUrl.sha256"

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("cctv-ffmpeg-" + [guid]::NewGuid().ToString("N"))
$archivePath = Join-Path $tempRoot "ffmpeg.zip"
$extractPath = Join-Path $tempRoot "extract"

try {
    New-Item -ItemType Directory -Force -Path $tempRoot, $extractPath | Out-Null
    Write-Host "Downloading FFmpeg $ffmpegVersion..."
    & curl.exe -L --fail --retry 4 --retry-delay 2 --connect-timeout 20 --max-time 900 --output $archivePath $archiveUrl
    if ($LASTEXITCODE -ne 0) {
        throw "FFmpeg download failed with exit code $LASTEXITCODE"
    }

    $checksumText = (& curl.exe -L --fail --retry 4 --retry-delay 2 --connect-timeout 20 --max-time 60 $checksumUrl) -join "`n"
    if ($LASTEXITCODE -ne 0 -or -not $checksumText) {
        throw "Could not download the FFmpeg checksum"
    }

    $expectedHash = (($checksumText.Trim() -split "\s+")[0]).ToUpperInvariant()
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToUpperInvariant()

    if ($expectedHash -ne $actualHash) {
        throw "FFmpeg checksum mismatch. Expected $expectedHash but got $actualHash"
    }

    Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force
    $ffmpeg = Get-ChildItem -LiteralPath $extractPath -Recurse -File -Filter "ffmpeg.exe" |
        Select-Object -First 1

    if (-not $ffmpeg) {
        throw "ffmpeg.exe was not found in the downloaded archive"
    }

    $outputDirectory = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    Copy-Item -LiteralPath $ffmpeg.FullName -Destination $OutputPath -Force

    Write-Host "FFmpeg saved to $OutputPath"
    Write-Host "SHA-256 verified: $actualHash"
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
