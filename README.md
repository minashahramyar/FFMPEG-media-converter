# Multi-format Media Converter

Hi! This is a **scalable media pipeline** that turns a single input video into **MP4 / WebM / GIF / audio / thumbnail**, and can optionally package **HLS**. It runs jobs in the background (Celery), uses FFmpeg under the hood, and can upload results to **Amazon S3**.

## Why it exists
Video conversion is fiddly and slow. I wanted a service that:
- accepts a URL,
- runs a clean, configurable pipeline,
- and gives me web-ready outputs… reliably and at scale.

## Features
- MP4 (H.264/AAC), WebM (VP9/Opus), GIF preview
- Audio extraction (M4A), thumbnails at any timestamp
- Optional subtitle **burn-in** from a .srt URL
- Optional **HLS** packaging with a simple ladder
- Asynchronous processing with **Celery + Redis**
- Logging, retries, Dockerized

## Quickstart
```bash
cp .env.example .env   # fill values
docker-compose up --build

