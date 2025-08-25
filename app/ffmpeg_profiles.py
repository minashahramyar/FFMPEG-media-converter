# Simple presets & ladders to keep the code clean.

MP4_PRESET = {
    "vcodec": "libx264",
    "acodec": "aac",
    "crf": "22",
    "preset": "veryfast",
    "audio_bitrate": "160k",
}

WEBM_PRESET = {
    "vcodec": "libvpx-vp9",
    "acodec": "libopus",
    "b:v": "0",           # CRF-based
    "crf": "32",
    "cpu-used": "4",
    "audio_bitrate": "128k",
}

HLS_LADDER = [
    # (width, height, video_bitrate, audio_bitrate)
    (426, 240, "400k", "96k"),
    (640, 360, "800k", "96k"),
    (854, 480, "1400k", "128k"),
    (1280, 720, "2800k", "128k"),
]