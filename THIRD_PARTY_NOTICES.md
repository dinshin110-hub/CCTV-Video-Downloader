# Third-Party Notices

This project is licensed under GPL-3.0-only. Release binaries bundle or depend
on the components below.

## FFmpeg

- Component: `ffmpeg.exe`
- Build used: Gyan.dev `ffmpeg-9.0.1-essentials_build`
- Upstream project: https://ffmpeg.org/
- Source code: https://ffmpeg.org/releases/ffmpeg-9.0.1.tar.xz
- Build provider: https://www.gyan.dev/ffmpeg/builds/
- License: GPL-3.0-or-later, because the selected build is configured with GPL
  components and version 3 licensing.
- Usage: invoked as a separate process to inspect and download HLS media. The
  executable is packaged alongside the Python application for convenience.

The build script records the exact download URL and verifies the published
SHA-256 checksum.

## PyInstaller

- Project: https://pyinstaller.org/
- License: GPL-2.0-or-later with the PyInstaller bootloader exception.
- Usage: packages the Python application into a Windows executable.

## Python and Tcl/Tk

- Project: https://www.python.org/
- License: Python Software Foundation License.
- Usage: Python runtime and Tkinter GUI toolkit included by PyInstaller.

## Icons

The application icon in `assets/cctv_downloader.ico` was generated for this
project. It does not contain third-party stock artwork.
