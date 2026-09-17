# CCTV Video Downloader

A small Windows GUI utility that downloads publicly available videos from CCTV
video detail pages. It accepts one or more CCTV URLs, resolves the video title
and duration, selects the highest available unencrypted official rendition,
downloads it to MP4, and reports progress.

Created and maintained by **YaoYao**.

## Features

- Windows 10/11 x64 GUI application
- Paste one or more CCTV video detail page URLs
- Automatic title and duration detection
- Selects the highest available official unencrypted stream
- Downloads directly to MP4 with bundled FFmpeg
- Progress display, cancellation, existing-file skip, and optional overwrite
- Head/tail validation after download
- Single-file executable build

## Download

Download the latest release from the GitHub Releases page.

Official release binaries are intended to be signed through the
[SignPath Foundation](https://signpath.org/) free code signing program for open
source software after the project is accepted.

Until a release is signed, Windows SmartScreen may show an "Unknown publisher"
warning. Verify the published SHA-256 checksum before running a binary.

## Usage

1. Start `CCTVVideoDownloader.exe`.
2. Paste one or more CCTV video detail page URLs, one per line.
3. Choose an output directory.
4. Select "Start Download".
5. Wait for the progress indicator to reach 100%.

The tool does not bypass DRM or encrypted high-bitrate streams. It only uses
official, publicly accessible streams that can be downloaded as ordinary MP4
media.

## Build from source

Requirements:

- Windows 10/11 x64
- Python 3.11+
- PowerShell 7 or Windows PowerShell 5.1

Run:

```powershell
python -m pip install -r requirements-build.txt
./scripts/build_windows.ps1
```

The script downloads a pinned FFmpeg GPL build, verifies its SHA-256, runs the
unit tests, and builds `dist/CCTVVideoDownloader.exe` with PyInstaller.

## Free open-source code signing

This repository is structured for the SignPath Foundation open-source code
signing program:

- Public source repository
- GPL-3.0-only license
- GitHub-hosted Windows build runner
- Reproducible build script
- SignPath GitHub Action workflow
- Artifact configuration for Authenticode signing

See [docs/SIGNPATH_APPLICATION.md](docs/SIGNPATH_APPLICATION.md).

## Legal and privacy

This project is an independent utility and is not affiliated with or endorsed by CCTV or China Central Television.

Only download media that you are authorized to save or use. The project does
not include CCTV account credentials, cookies, DRM keys, or bypass mechanisms.

Downloaded media is saved locally and is not uploaded by this application.

## Third-party components

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

GPL-3.0-only. See [LICENSE](LICENSE).

---

## 中文说明

这是一个 Windows CCTV 视频下载小工具，支持一次输入多条 CCTV 视频详情页
链接，自动识别标题并下载官方公开的明文视频线路。

界面顶部显示 `CCTV视频下载工具 v1.0.0 by:YaoYao`。

项目采用 GPL-3.0-only 开源，并计划申请 SignPath Foundation 的免费开源软件
代码签名服务。请不要使用本工具绕过 DRM、付费限制或保存无权使用的视频。
