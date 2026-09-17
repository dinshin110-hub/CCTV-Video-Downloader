from __future__ import annotations

import ctypes
import json
import os
import queue
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

APP_NAME = "CCTV视频下载工具"
VERSION = "1.0.0"
DISPLAY_TITLE = f"{APP_NAME} v{VERSION} by:YaoYao"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class CancelledError(Exception):
    pass


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def find_ffmpeg() -> Optional[Path]:
    env_path = os.environ.get("CCTV_FFMPEG", "").strip()
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend([
        resource_path("ffmpeg.exe"),
        Path(__file__).resolve().with_name("ffmpeg.exe"),
    ])
    for item in candidates:
        if item.is_file():
            return item
    which = shutil.which("ffmpeg")
    return Path(which) if which else None


def run_checked(cmd: list[str], timeout: int, cancel_event: threading.Event) -> tuple[int, str, str]:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    start = time.monotonic()
    while proc.poll() is None:
        if cancel_event.is_set():
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            raise CancelledError("用户取消")
        if time.monotonic() - start > timeout:
            proc.kill()
            raise TimeoutError(f"命令执行超时（{timeout} 秒）")
        time.sleep(0.15)
    out, err = proc.communicate()
    return proc.returncode, out or "", err or ""


def fetch_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "CERTIFICATE_VERIFY_FAILED" not in reason.upper():
            raise
        insecure = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=timeout, context=insecure) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")


def extract_guid(html: str) -> str:
    patterns = [
        r"var\s+guid\s*=\s*[\"']([\da-fA-F]+)",
        r"videoCenterId(?:\s*[\"']\s*,|:)\s*[\"']([\da-fA-F]+)",
        r"changePlayer\s*\(\s*[\"']([\da-fA-F]+)",
        r"load[Vv]ideo\s*\(\s*[\"']([\da-fA-F]+)",
        r"var\s+initMyAray\s*=\s*[\"']([\da-fA-F]+)",
        r"var\s+ids\s*=\s*\[[\"']([\da-fA-F]+)",
        r"guid\s*[:=]\s*[\"']([\da-fA-F]{16,})[\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return match.group(1).lower()
    raise ValueError("未能从页面中识别 CCTV 视频 ID，请确认链接是视频详情页")


def parse_urls(raw: str) -> list[str]:
    urls: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        found = re.findall(r"https?://[^\s\]\[\<\>\"'\)]+", line)
        if found:
            for url in found:
                url = url.rstrip(".,;，。；")
                if url not in urls:
                    urls.append(url)
        elif re.match(r"^(?:tv\.|www\.)?cctv\.com/", line, flags=re.IGNORECASE):
            url = "https://" + line.rstrip(".,;，。；")
            if url not in urls:
                urls.append(url)
    return urls


def cctv_metadata(url: str) -> dict:
    html = fetch_text(url)
    guid = extract_guid(html)
    api_url = f"https://vdn.apps.cntv.cn/api/getHttpVideoInfo.do?pid={guid}"
    data = json.loads(fetch_text(api_url))
    if data.get("ack") != "yes":
        raise RuntimeError(data.get("tip_msg") or "CCTV 视频接口返回失败")
    title = str(data.get("title") or f"CCTV_{guid}").strip()
    video = data.get("video") or {}
    try:
        duration = float(video.get("totalLength") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0 and data.get("len"):
        parts = [int(x) for x in str(data["len"]).split(":")[-3:]]
        while len(parts) < 3:
            parts.insert(0, 0)
        duration = parts[0] * 3600 + parts[1] * 60 + parts[2]
    return {"url": url, "guid": guid, "title": title, "duration": duration}


def probe_stream(ffmpeg: Path, url: str, cancel_event: threading.Event) -> dict:
    cmd = [
        str(ffmpeg), "-hide_banner", "-nostats",
        "-i", url, "-t", "5", "-f", "null", "NUL",
    ]
    code, stdout, stderr = run_checked(cmd, timeout=90, cancel_event=cancel_event)
    text = (stdout or "") + "\n" + (stderr or "")
    if code != 0:
        raise RuntimeError(f"FFmpeg 无法读取该线路（退出码 {code}）")
    low = text.lower()
    bad_markers = (
        "error while decoding",
        "corrupt decoded frame",
        "packet corrupt",
        "cabac decode",
        "invalid nal",
        "invalid data found",
    )
    if any(marker in low for marker in bad_markers):
        raise RuntimeError("该线路存在加密或码流损坏，无法直接下载")
    match = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"\b(\d{2,5})x(\d{2,5})\b", text)
    if not match:
        raise RuntimeError("无法识别视频分辨率")
    width, height = int(match.group(1)), int(match.group(2))
    if width < 160 or height < 90:
        raise RuntimeError(f"视频分辨率异常：{width}x{height}")
    return {"url": url, "width": width, "height": height, "pixels": width * height, "probe": text}


def select_best_stream(
    ffmpeg: Path,
    guid: str,
    cancel_event: threading.Event,
    log: Optional[Callable[[str], None]] = None,
) -> dict:
    qualities = (2000, 1200, 850, 450)
    valid: list[dict] = []
    failures: list[str] = []
    for quality in qualities:
        if cancel_event.is_set():
            raise CancelledError("用户取消")
        url = (
            "https://newcntv.qcloudcdn.com/asp/hls/"
            f"{quality}/0303000a/3/default/{guid}/{quality}.m3u8"
        )
        if log:
            log(f"检测线路 {quality}…")
        try:
            item = probe_stream(ffmpeg, url, cancel_event)
            if any(x["pixels"] == item["pixels"] for x in valid):
                continue
            valid.append(item)
            if log:
                log(f"可用线路：{item['width']}x{item['height']}")
        except CancelledError:
            raise
        except Exception as exc:
            failures.append(f"{quality}: {exc}")
    if not valid:
        detail = "；".join(failures[-2:]) if failures else "没有可用线路"
        raise RuntimeError(f"未找到可直接下载的明文视频线路：{detail}")
    return max(valid, key=lambda x: (x["pixels"], x["width"]))


def safe_filename(name: str, max_length: int = 120) -> str:
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        name = "CCTV视频"
    return name[:max_length].rstrip(" .")


def download_stream(
    ffmpeg: Path,
    stream_url: str,
    output: Path,
    duration: float,
    cancel_event: threading.Event,
    progress: Optional[Callable[[float, str], None]] = None,
    limit_seconds: Optional[float] = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.stem + ".part" + output.suffix)
    if temp.exists():
        temp.unlink()
    cmd = [
        str(ffmpeg), "-hide_banner", "-v", "error", "-nostats",
        "-progress", "pipe:1", "-stats_period", "0.5",
        "-y", "-i", stream_url,
        "-c", "copy", "-bsf:a", "aac_adtstoasc",
        "-movflags", "+faststart",
    ]
    if limit_seconds:
        cmd.extend(["-t", str(limit_seconds)])
    cmd.append(str(temp))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )
    error_lines: list[str] = []
    values: dict[str, str] = {}
    last_report = 0.0
    try:
        assert proc.stdout is not None
        while True:
            line = proc.stdout.readline()
            if line:
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    values[key] = value
                    if key in {"out_time_us", "out_time_ms"}:
                        try:
                            seconds = int(value) / 1_000_000
                        except ValueError:
                            seconds = 0.0
                        frac = min(0.999, seconds / duration) if duration > 0 else 0.0
                        now = time.monotonic()
                        if progress and now - last_report >= 0.4:
                            speed = values.get("speed", "")
                            progress(frac, speed)
                            last_report = now
                elif line:
                    error_lines.append(line)
            elif proc.poll() is not None:
                break
            if cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise CancelledError("用户取消")
            if proc.poll() is None and not line:
                time.sleep(0.03)
        code = proc.wait()
    except CancelledError:
        if temp.exists():
            temp.unlink()
        raise
    finally:
        if proc.poll() is None:
            proc.kill()
    joined_errors = "\n".join(error_lines)
    low = joined_errors.lower()
    if code != 0:
        if temp.exists():
            temp.unlink()
        raise RuntimeError(f"FFmpeg 下载失败（退出码 {code}）\n{joined_errors[-1200:]}")
    if any(marker in low for marker in ("error while decoding", "corrupt decoded frame", "packet corrupt")):
        if temp.exists():
            temp.unlink()
        raise RuntimeError("下载过程中检测到码流损坏，已删除不完整文件")
    if not temp.exists() or temp.stat().st_size < 1024:
        if temp.exists():
            temp.unlink()
        raise RuntimeError("下载结果为空或文件过小")
    os.replace(temp, output)
    if progress:
        progress(1.0, values.get("speed", ""))


def quick_verify(ffmpeg: Path, path: Path, duration: float, cancel_event: threading.Event) -> bool:
    checks = [[str(ffmpeg), "-hide_banner", "-v", "error", "-ss", "0", "-i", str(path), "-t", "2", "-f", "null", "NUL"]]
    if duration > 8:
        checks.append([
            str(ffmpeg), "-hide_banner", "-v", "error",
            "-ss", str(max(0, duration - 3)), "-i", str(path),
            "-t", "2", "-f", "null", "NUL",
        ])
    for cmd in checks:
        code, out, err = run_checked(cmd, timeout=45, cancel_event=cancel_event)
        text = (out or "") + (err or "")
        if code != 0 or any(marker in text.lower() for marker in ("error while decoding", "corrupt decoded frame", "packet corrupt")):
            return False
    return True


class DownloaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(DISPLAY_TITLE)
        self.root.geometry("860x650")
        self.root.minsize(760, 580)
        self.events: queue.Queue[tuple] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None
        self.ffmpeg = find_ffmpeg()

        self.url_text: tk.Text
        self.out_var = tk.StringVar(value=str(Path.home() / "Downloads" / "CCTV视频"))
        self.overwrite_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="就绪")
        self.progress_var = tk.DoubleVar(value=0)

        self._build_ui()
        self._set_icon()
        self._poll_events()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        if self.ffmpeg:
            self.log(f"已加载 FFmpeg：{self.ffmpeg}")
        else:
            self.log("错误：未找到 FFmpeg，工具无法下载。")

    def _set_icon(self) -> None:
        ico = resource_path("cctv_downloader.ico")
        if ico.is_file():
            try:
                self.root.iconbitmap(default=str(ico))
            except tk.TclError:
                pass

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 16, "bold"))
        style.configure("Sub.TLabel", foreground="#5b6573")
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"))

        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        main.rowconfigure(8, weight=2)

        ttk.Label(main, text=DISPLAY_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(main, text="支持一次粘贴多条 CCTV 视频详情页链接，每行一条", style="Sub.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 10))

        url_frame = ttk.LabelFrame(main, text="视频链接", padding=8)
        url_frame.grid(row=2, column=0, sticky="nsew")
        url_frame.columnconfigure(0, weight=1)
        url_frame.rowconfigure(0, weight=1)
        self.url_text = tk.Text(url_frame, height=7, wrap="none", undo=True, font=("Consolas", 10))
        yscroll = ttk.Scrollbar(url_frame, orient="vertical", command=self.url_text.yview)
        xscroll = ttk.Scrollbar(url_frame, orient="horizontal", command=self.url_text.xview)
        self.url_text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.url_text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        out_frame = ttk.LabelFrame(main, text="保存位置", padding=8)
        out_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        out_frame.columnconfigure(0, weight=1)
        ttk.Entry(out_frame, textvariable=self.out_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(out_frame, text="浏览…", command=self.choose_dir).grid(row=0, column=1, padx=(8, 0))

        opts = ttk.Frame(main)
        opts.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(opts, text="覆盖已存在的同名文件", variable=self.overwrite_var).pack(side="left")
        ttk.Button(opts, text="打开保存目录", command=self.open_output_dir).pack(side="right")

        buttons = ttk.Frame(main)
        buttons.grid(row=5, column=0, sticky="ew", pady=(10, 6))
        self.start_btn = ttk.Button(buttons, text="开始下载", command=self.start_download, style="Accent.TButton")
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(buttons, text="取消", command=self.cancel_download, state="disabled")
        self.cancel_btn.pack(side="left", padx=(8, 0))
        ttk.Label(buttons, textvariable=self.status_var, style="Sub.TLabel").pack(side="right")

        self.progress = ttk.Progressbar(main, variable=self.progress_var, maximum=100)
        self.progress.grid(row=6, column=0, sticky="ew", pady=(2, 10))

        ttk.Label(main, text="运行日志").grid(row=7, column=0, sticky="w")
        self.log_box = ScrolledText(main, height=12, state="disabled", wrap="word", font=("Microsoft YaHei UI", 9))
        self.log_box.grid(row=8, column=0, sticky="nsew", pady=(4, 0))
        self.log_box.configure(background="#f7f9fc", foreground="#263238", relief="flat")

    def choose_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.out_var.get() or str(Path.home()))
        if selected:
            self.out_var.set(selected)

    def open_output_dir(self) -> None:
        path = Path(self.out_var.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"无法打开目录：{exc}")

    def log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def emit(self, kind: str, **payload: object) -> None:
        self.events.put((kind, payload))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self.log(str(payload.get("text", "")))
                elif kind == "status":
                    self.status_var.set(str(payload.get("text", "")))
                elif kind == "overall":
                    self.progress_var.set(float(payload.get("value", 0)))
                elif kind == "done":
                    self._finish_worker(bool(payload.get("cancelled", False)), int(payload.get("errors", 0)))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def start_download(self) -> None:
        if not self.ffmpeg:
            messagebox.showerror(APP_NAME, "未找到 FFmpeg。请重新安装完整版本的 CCTV视频下载工具。")
            return
        urls = parse_urls(self.url_text.get("1.0", "end"))
        if not urls:
            messagebox.showwarning(APP_NAME, "请先粘贴至少一条 CCTV 视频链接。")
            return
        out_dir = Path(self.out_var.get()).expanduser()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"无法创建保存目录：{exc}")
            return
        self.cancel_event.clear()
        self.progress_var.set(0)
        self.status_var.set("准备中…")
        self.start_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.worker_thread = threading.Thread(
            target=self._worker,
            args=(urls, out_dir, self.overwrite_var.get(), self.ffmpeg),
            daemon=True,
        )
        self.worker_thread.start()

    def cancel_download(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            self.cancel_event.set()
            self.status_var.set("正在取消…")
            self.emit("log", text="收到取消请求，正在停止下载…")

    def _worker(self, urls: list[str], out_dir: Path, overwrite: bool, ffmpeg: Path) -> None:
        errors = 0
        cancelled = False
        total = len(urls)
        for index, url in enumerate(urls, start=1):
            if self.cancel_event.is_set():
                cancelled = True
                break
            self.emit("status", text=f"处理第 {index}/{total} 条")
            self.emit("log", text=f"\n[{index}/{total}] {url}")
            try:
                meta = cctv_metadata(url)
                self.emit("log", text=f"标题：{meta['title']}")
                if meta["duration"]:
                    self.emit("log", text=f"时长：{meta['duration']:.1f} 秒")
                stream = select_best_stream(
                    ffmpeg,
                    meta["guid"],
                    self.cancel_event,
                    log=lambda text: self.emit("log", text=text),
                )
                resolution = f"{stream['width']}x{stream['height']}"
                suffix = f"{stream['height']}p"
                filename = safe_filename(f"{meta['title']}_{suffix}") + ".mp4"
                output = out_dir / filename
                if output.exists() and not overwrite:
                    self.emit("log", text=f"已存在，跳过：{output.name}")
                    self.emit("overall", value=index / total * 100)
                    continue
                self.emit("log", text=f"开始下载 {resolution} 到：{output}")

                def on_progress(frac: float, speed: str) -> None:
                    base = ((index - 1) + max(0.0, min(1.0, frac))) / total * 100
                    self.emit("overall", value=base)
                    speed_text = f"，速度 {speed}" if speed else ""
                    self.emit("status", text=f"第 {index}/{total} 条  {frac * 100:.1f}%{speed_text}")

                download_stream(ffmpeg, stream["url"], output, meta["duration"], self.cancel_event, on_progress)
                if not quick_verify(ffmpeg, output, meta["duration"], self.cancel_event):
                    raise RuntimeError("下载文件首尾校验失败")
                self.emit("log", text=f"完成：{output.name}（{output.stat().st_size / 1024 / 1024:.1f} MB）")
                self.emit("overall", value=index / total * 100)
            except CancelledError:
                cancelled = True
                self.emit("log", text="已取消")
                break
            except Exception as exc:
                errors += 1
                self.emit("log", text=f"失败：{exc}")
        self.emit("done", cancelled=cancelled, errors=errors)

    def _finish_worker(self, cancelled: bool, errors: int) -> None:
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        if cancelled:
            self.status_var.set("已取消")
            messagebox.showinfo(APP_NAME, "下载已取消。")
        elif errors:
            self.status_var.set(f"完成，{errors} 条失败")
            messagebox.showwarning(APP_NAME, f"任务结束，有 {errors} 条下载失败。请查看日志。")
        else:
            self.status_var.set("全部完成")
            self.progress_var.set(100)
            messagebox.showinfo(APP_NAME, "下载完成。")

    def on_close(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            if not messagebox.askyesno(APP_NAME, "下载仍在进行，确定退出吗？"):
                return
            self.cancel_event.set()
        self.root.destroy()


def cli_probe(argv: list[str]) -> int:
    if "--probe" not in argv:
        return 2
    idx = argv.index("--probe")
    if idx + 1 >= len(argv):
        return 2
    url = argv[idx + 1]
    json_out = None
    if "--json-out" in argv:
        j = argv.index("--json-out")
        if j + 1 < len(argv):
            json_out = Path(argv[j + 1])
    result: dict
    try:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("FFmpeg not found")
        meta = cctv_metadata(url)
        stream = select_best_stream(ffmpeg, meta["guid"], threading.Event())
        result = {
            "ok": True,
            "title": meta["title"],
            "guid": meta["guid"],
            "duration": meta["duration"],
            "width": stream["width"],
            "height": stream["height"],
            "stream_url": stream["url"],
            "ffmpeg": str(ffmpeg),
        }
        code = 0
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
        code = 1
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return code


def cli_test_download(argv: list[str]) -> int:
    if "--test-download" not in argv:
        return 2
    idx = argv.index("--test-download")
    if idx + 1 >= len(argv):
        return 2
    url = argv[idx + 1]
    out_dir = Path("work") / "smoke"
    seconds = 8.0
    if "--out" in argv:
        o = argv.index("--out")
        if o + 1 < len(argv):
            out_dir = Path(argv[o + 1])
    if "--seconds" in argv:
        s = argv.index("--seconds")
        if s + 1 < len(argv):
            seconds = float(argv[s + 1])
    json_out = out_dir / "smoke_result.json"
    try:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("FFmpeg not found")
        meta = cctv_metadata(url)
        stream = select_best_stream(ffmpeg, meta["guid"], threading.Event())
        output = out_dir / "smoke_video.mp4"
        download_stream(
            ffmpeg, stream["url"], output, meta["duration"], threading.Event(), limit_seconds=seconds
        )
        result = {
            "ok": True,
            "output": str(output.resolve()),
            "bytes": output.stat().st_size,
            "width": stream["width"],
            "height": stream["height"],
        }
        code = 0
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
        code = 1
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return code


def main() -> int:
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    if "--probe" in sys.argv:
        return cli_probe(sys.argv)
    if "--test-download" in sys.argv:
        return cli_test_download(sys.argv)
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())