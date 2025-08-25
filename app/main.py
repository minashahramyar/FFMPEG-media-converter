import os
from fastapi import FastAPI, Header, HTTPException
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
from .models import ConvertRequest, SubmitResponse, StatusResponse
from .tasks import app as celery_app, convert_task

load_dotenv()

API_KEY = os.getenv("API_KEY")

app = FastAPI(title="Multi-format Media Converter", version="1.0")
logger.add("logs/api.log", rotation="1 MB", retention="7 days", level="INFO")

def require_api_key(x_api_key: str | None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

@app.post("/convert", response_model=SubmitResponse)
def submit(req: ConvertRequest, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    job = convert_task.delay(
        file_url=str(req.file_url),
        title=req.title,
        targets=req.targets,
        burn_subtitles_url=str(req.burn_subtitles_url) if req.burn_subtitles_url else None,
        thumbnail_time=req.thumbnail_time,
        gif_start=req.gif_start,
        gif_duration=req.gif_duration,
    )
    logger.info("Queued job {}", job.id)
    return SubmitResponse(job_id=job.id, message="Queued")

@app.get("/status/{job_id}", response_model=StatusResponse)
def status(job_id: str, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    res = celery_app.AsyncResult(job_id)
    payload = StatusResponse(job_id=job_id, status=res.state.lower())
    if res.failed():
        payload.error = str(res.info)
    if res.successful() and isinstance(res.result, dict):
        payload.outputs = res.result.get("outputs", [])
    return payload

@app.get("/")
def root():
    return {"service": "Multi-format Media Converter", "status": "ok"}