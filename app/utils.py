import os
import subprocess
from pathlib import Path
from typing import List, Optional
from loguru import logger
import boto3

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def run_ffmpeg(args: List[str]) -> None:
    logger.info("FFmpeg: {}", " ".join(args))
    subprocess.run(args, check=True)

def s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
        region_name=os.getenv("AWS_REGION"),
    )

def upload_to_s3(local_path: Path, s3_key: str):
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET not configured")
    client = s3_client()
    with local_path.open("rb") as fh:
        client.upload_fileobj(fh, bucket, s3_key)
    logger.success("Uploaded to s3://{}/{}", bucket, s3_key)

def safe_title(title: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9_-]", "_", title)

def build_output_key(prefix: str, filename: str) -> str:
    prefix = prefix.strip("/").rstrip("/")
    return f"{prefix}/{filename}" if prefix else filename

def stream_download(url: str, dest: Path):
    import requests
    logger.info("Downloading {}", url)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
    logger.success("Saved {}", dest)

def burn_subtitles_args(subs_path: Optional[Path]) -> List[str]:
    if not subs_path:
        return []
    # Uses the subtitles filter; for .srt this is fine
    return ["-vf", f"subtitles={subs_path.as_posix()}"]