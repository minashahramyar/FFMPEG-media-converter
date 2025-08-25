from pydantic import BaseModel, HttpUrl, Field, validator
from typing import List, Optional, Literal

Format = Literal["mp4", "webm", "gif", "audio", "thumbnail", "hls"]

class ConvertRequest(BaseModel):
    file_url: HttpUrl
    title: str = Field(default="untitled", max_length=120)
    targets: List[Format] = ["mp4", "webm"]
    burn_subtitles_url: Optional[HttpUrl] = None
    thumbnail_time: float = 2.0  # seconds
    gif_start: float = 0.0
    gif_duration: float = 3.0

    @validator("targets")
    def no_duplicates(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("targets contain duplicates")
        return v

class SubmitResponse(BaseModel):
    job_id: str
    message: str

class StatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "started", "success", "failure"]
    outputs: List[str] = []
    error: Optional[str] = None