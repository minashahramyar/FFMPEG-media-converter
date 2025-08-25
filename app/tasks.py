import os
from celery import Celery, states
from celery.utils.log import get_task_logger
from loguru import logger
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional

from .ffmpeg_profiles import MP4_PRESET, WEBM_PRESET, HLS_LADDER
from .utils import (
    ensure_dir, run_ffmpeg, upload_to_s3, stream_download, burn_subtitles_args,
    safe_title, build_output_key
)

load_dotenv()

# logging setup
os.makedirs("logs", exist_ok=True)
logger.add("logs/worker.log", rotation="1 MB", retention="7 days", level="INFO")

# Celery
redis_url = f"redis://{os.getenv('REDIS_HOST','localhost')}:{os.getenv('REDIS_PORT','6379')}/{os.getenv('REDIS_DB','0')}"
app = Celery("tasks", broker=redis_url, backend=redis_url)

SAVE_DIR = Path(os.getenv("SAVE_DIR", "/tmp/media"))
ensure_dir(SAVE_DIR)

def _dl_input(file_url: str, title: str) -> Path:
    input_path = SAVE_DIR / f"{title}_input"
    ensure_dir(input_path)
    src = input_path / "source"
    stream_download(file_url, src)
    return src

def _maybe_download_subs(url: Optional[str], title: str) -> Optional[Path]:
    if not url:
        return None
    subs_dir = SAVE_DIR / f"{title}_input"
    ensure_dir(subs_dir)
    subs_path = subs_dir / "subs.srt"
    stream_download(url, subs_path)
    return subs_path

def _mp4(src: Path, out: Path, subs: Optional[Path]):
    args = ["ffmpeg", "-y", "-i", src.as_posix(), "-c:v", MP4_PRESET["vcodec"],
            "-preset", MP4_PRESET["preset"], "-crf", MP4_PRESET["crf"],
            "-c:a", MP4_PRESET["acodec"], "-b:a", MP4_PRESET["audio_bitrate"]]
    args += burn_subtitles_args(subs)
    args += [out.as_posix()]
    run_ffmpeg(args)

def _webm(src: Path, out: Path, subs: Optional[Path]):
    args = ["ffmpeg", "-y", "-i", src.as_posix(), "-c:v", WEBM_PRESET["vcodec"],
            "-b:v", WEBM_PRESET["b:v"], "-crf", WEBM_PRESET["crf"],
            "-cpu-used", WEBM_PRESET["cpu-used"],
            "-c:a", WEBM_PRESET["acodec"], "-b:a", WEBM_PRESET["audio_bitrate"]]
    args += burn_subtitles_args(subs)
    args += [out.as_posix()]
    run_ffmpeg(args)

def _gif(src: Path, out: Path, start: float, duration: float):
    # palette generation for quality
    pal = out.with_suffix(".palette.png")
    run_ffmpeg(["ffmpeg", "-y", "-ss", str(start), "-t", str(duration),
                "-i", src.as_posix(), "-vf", "palettegen", pal.as_posix()])
    run_ffmpeg(["ffmpeg", "-y", "-ss", str(start), "-t", str(duration),
                "-i", src.as_posix(), "-i", pal.as_posix(),
                "-lavfi", "paletteuse", out.as_posix()])

def _audio(src: Path, out: Path):
    run_ffmpeg(["ffmpeg", "-y", "-i", src.as_posix(), "-vn", "-c:a", "aac", "-b:a", "160k", out.as_posix()])

def _thumbnail(src: Path, out: Path, t: float):
    run_ffmpeg(["ffmpeg", "-y", "-ss", str(t), "-i", src.as_posix(), "-vframes", "1", out.as_posix()])

def _hls(src: Path, out_dir: Path):
    ensure_dir(out_dir)
    # Create renditions
    for w, h, v_b, a_b in HLS_LADDER:
        var_out = out_dir / f"{h}p.m3u8"
        run_ffmpeg([
            "ffmpeg", "-y", "-i", src.as_posix(),
            "-vf", f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease",
            "-c:v", "libx264", "-profile:v", "main", "-crf", "22", "-b:v", v_b,
            "-c:a", "aac", "-b:a", a_b,
            "-hls_time", "6", "-hls_playlist_type", "vod",
            "-hls_segment_filename", (out_dir / f"{h}p_%03d.ts").as_posix(),
            var_out.as_posix()
        ])
    # Master playlist
    master = out_dir / "master.m3u8"
    with master.open("w") as f:
        for w, h, _, _ in HLS_LADDER:
            f.write(f'#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=0,RESOLUTION={w}x{h}\n{h}p.m3u8\n')
    logger.success("HLS packaged at {}", out_dir)

@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def convert_task(self,
                 file_url: str,
                 title: str,
                 targets: list,
                 burn_subtitles_url: str | None = None,
                 thumbnail_time: float = 2.0,
                 gif_start: float = 0.0,
                 gif_duration: float = 3.0):
    safe = safe_title(title)
    base_dir = SAVE_DIR / safe
    ensure_dir(base_dir)

    # 1) Download
    src = _dl_input(file_url, safe)
    subs = _maybe_download_subs(burn_subtitles_url, safe)

    outputs = []

    # 2) Convert per target
    if "mp4" in targets:
        out = base_dir / f"{safe}.mp4"
        _mp4(src, out, subs)
        upload_to_s3(out, build_output_key(safe, out.name))
        outputs.append(out.name)

    if "webm" in targets:
        out = base_dir / f"{safe}.webm"
        _webm(src, out, subs)
        upload_to_s3(out, build_output_key(safe, out.name))
        outputs.append(out.name)

    if "gif" in targets:
        out = base_dir / f"{safe}.gif"
        _gif(src, out, gif_start, gif_duration)
        upload_to_s3(out, build_output_key(safe, out.name))
        outputs.append(out.name)

    if "audio" in targets:
        out = base_dir / f"{safe}.m4a"
        _audio(src, out)
        upload_to_s3(out, build_output_key(safe, out.name))
        outputs.append(out.name)

    if "thumbnail" in targets:
        out = base_dir / f"{safe}_thumb.jpg"
        _thumbnail(src, out, thumbnail_time)
        upload_to_s3(out, build_output_key(safe, out.name))
        outputs.append(out.name)

    if "hls" in targets and os.getenv("ENABLE_HLS", "false").lower() == "true":
        hls_dir = base_dir / "hls"
        _hls(src, hls_dir)
        # You might upload HLS directory via sync in CI/CD or S3 multipart; skipping per-file upload here.

    logger.success("Conversion done for {}. Outputs: {}", safe, outputs)
    return {"outputs": outputs}