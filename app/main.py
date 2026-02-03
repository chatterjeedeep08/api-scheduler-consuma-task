from fastapi import FastAPI
from .database import engine
from .models import Base
from sqlalchemy.orm import Session
from .database import SessionLocal
from fastapi import Depends
from . import models, schemas
from datetime import datetime
from threading import Thread
from .scheduler import scheduler_loop
from .scheduler import execute_pending_runs
from typing import Optional
from sqlalchemy import func

app = FastAPI(title="API Scheduler Consuma")

@app.on_event("startup")
def start_workers():
    Thread(target=scheduler_loop, daemon=True).start()
    Thread(target=execute_pending_runs, daemon=True).start()

# THIS creates the DB file
Base.metadata.create_all(bind=engine)

@app.get("/health")
def health_check():
    return {"status": "ok"}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/targets", response_model=schemas.TargetOut)
def create_target(
    target: schemas.TargetCreate,
    db: Session = Depends(get_db)
):
    db_target = models.Target(**target.dict())
    db.add(db_target)
    db.commit()
    db.refresh(db_target)
    return db_target

@app.get("/targets", response_model=list[schemas.TargetOut])
def list_targets(db: Session = Depends(get_db)):
    return db.query(models.Target).all()

@app.post("/schedules", response_model=schemas.ScheduleOut)
def create_schedule(
    schedule: schemas.ScheduleCreate,
    db: Session = Depends(get_db)
):
    next_run = datetime.utcnow()

    db_schedule = models.Schedule(
        target_id=schedule.target_id,
        interval_seconds=schedule.interval_seconds,
        end_time=schedule.end_time,
        next_run_at=next_run,
        status="active"
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

@app.post("/schedules/{schedule_id}/pause")
def pause_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(models.Schedule).get(schedule_id)
    if not schedule:
        return {"error": "Schedule not found"}

    schedule.status = "paused"
    db.commit()
    return {"status": "paused"}

@app.post("/schedules/{schedule_id}/resume")
def resume_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(models.Schedule).get(schedule_id)
    if not schedule:
        return {"error": "Schedule not found"}

    schedule.status = "active"
    schedule.next_run_at = datetime.utcnow()
    db.commit()
    return {"status": "active"}

@app.get("/schedules", response_model=list[schemas.ScheduleOut])
def list_schedules(db: Session = Depends(get_db)):
    return db.query(models.Schedule).all()

@app.get("/runs", response_model=list[schemas.RunOut])
def list_runs(
    schedule_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Run)

    if schedule_id:
        query = query.filter(models.Run.schedule_id == schedule_id)

    if status:
        query = query.filter(models.Run.status == status)

    return query.order_by(models.Run.id.desc()).all()

@app.get("/runs/{run_id}", response_model=schemas.RunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.Run).get(run_id)
    if not run:
        return {"error": "Run not found"}
    return run

@app.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    total_runs = db.query(func.count(models.Run.id)).scalar()
    success = db.query(func.count(models.Run.id)).filter(
        models.Run.status == "success"
    ).scalar()
    failed = db.query(func.count(models.Run.id)).filter(
        models.Run.status == "failed"
    ).scalar()

    avg_latency = db.query(func.avg(models.Run.latency_ms)).scalar()

    error_breakdown = (
        db.query(models.Run.error_type, func.count(models.Run.id))
        .group_by(models.Run.error_type)
        .all()
    )

    return {
        "total_runs": total_runs,
        "success": success,
        "failed": failed,
        "avg_latency_ms": avg_latency,
        "errors": {e or "none": c for e, c in error_breakdown}
    }
