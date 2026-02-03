from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TargetCreate(BaseModel):
    url: str
    method: str
    headers: Optional[str] = None
    body: Optional[str] = None


class TargetOut(TargetCreate):
    id: int

    class Config:
        from_attributes = True


class ScheduleCreate(BaseModel):
    target_id: int
    interval_seconds: int
    end_time: Optional[datetime] = None


class ScheduleOut(ScheduleCreate):
    id: int
    status: str
    next_run_at: datetime

    class Config:
        from_attributes = True

class RunOut(BaseModel):
    id: int
    schedule_id: int
    scheduled_for: datetime
    started_at: datetime | None
    finished_at: datetime | None
    status: str | None
    status_code: int | None
    error_type: str | None
    latency_ms: int | None
    response_size: int | None

    class Config:
        from_attributes = True

