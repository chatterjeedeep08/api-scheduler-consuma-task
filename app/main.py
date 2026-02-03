from fastapi import FastAPI
from .database import engine
from .models import Base
from sqlalchemy.orm import Session
from .database import SessionLocal
from fastapi import Depends
from . import models, schemas
from datetime import datetime
from threading import Thread
from typing import Optional
from sqlalchemy import func
from fastapi import HTTPException
from threading import Thread
from .scheduler import schedule_runs, execute_runs, shutdown_event

app = FastAPI(title="API Scheduler Consuma")

ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE"}

@app.on_event("startup")
def start_workers():
    Thread(target=schedule_runs, daemon=True).start()
    Thread(target=execute_runs, daemon=True).start()
    
@app.on_event("shutdown")
def shutdown_workers():
    shutdown_event.set()

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
        
#==============================
# TARGET ENDPOINTS
#==============================

@app.post("/targets", response_model=schemas.TargetOut)
def create_target(
    target: schemas.TargetCreate,
    db: Session = Depends(get_db)
):
    method = target.method.upper()

    if method not in ALLOWED_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid HTTP method. Allowed: {ALLOWED_METHODS}"
        )

    db_target = models.Target(
        url=target.url,
        method=method,
        headers=target.headers,
        body=target.body
    )
    db.add(db_target)
    db.commit()
    db.refresh(db_target)
    return db_target

@app.get("/targets", response_model=list[schemas.TargetOut])
def list_targets(db: Session = Depends(get_db)):
    return db.query(models.Target).all()

@app.put("/targets/{target_id}", response_model=schemas.TargetOut)
def update_target(
    target_id: int,
    updated: schemas.TargetCreate,
    db: Session = Depends(get_db)
):
    target = db.query(models.Target).get(target_id)
    if not target:
        raise HTTPException(404, "Target not found")

    for key, value in updated.dict().items():
        setattr(target, key, value)

    db.commit()
    db.refresh(target)
    return target

@app.delete("/targets/{target_id}")
def delete_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(models.Target).get(target_id)
    if not target:
        raise HTTPException(404, "Target not found")

    db.delete(target)
    db.commit()
    return {"deleted": True}


#==============================
# SCHEDULE ENDPOINTS
#==============================

@app.post("/schedules", response_model=schemas.ScheduleOut)
def create_schedule(
    schedule: schemas.ScheduleCreate,
    db: Session = Depends(get_db)
):
    # Guardrail 1: interval must be positive
    if schedule.interval_seconds <= 0:
        raise HTTPException(
            status_code=400,
            detail="interval_seconds must be greater than 0"
        )

    # Guardrail 2: end_time must be in the future
    if schedule.end_time and schedule.end_time <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="end_time must be in the future"
        )
        
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

@app.get("/schedules/{schedule_id}", response_model=schemas.ScheduleDetailOut)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(models.Schedule).get(schedule_id)
    if not schedule:
        raise HTTPException(404, "Schedule not found")

    runs = (
        db.query(models.Run)
        .filter(models.Run.schedule_id == schedule_id)
        .order_by(models.Run.id.desc())
        .limit(10)
        .all()
    )

    schedule.runs = runs
    return schedule

@app.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(models.Schedule).get(schedule_id)
    if not schedule:
        raise HTTPException(404, "Schedule not found")

    db.delete(schedule)
    db.commit()
    return {"deleted": True}

#==============================
# RUN ENDPOINTS
#==============================

@app.get("/runs", response_model=list[schemas.RunOut])
def list_runs(
    schedule_id: int | None = None,
    status: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Run)

    if schedule_id:
        query = query.filter(models.Run.schedule_id == schedule_id)
    if status:
        query = query.filter(models.Run.status == status)
    if from_time:
        query = query.filter(models.Run.scheduled_for >= from_time)
    if to_time:
        query = query.filter(models.Run.scheduled_for <= to_time)

    return query.order_by(models.Run.id.desc()).limit(100).all()

@app.get("/runs/{run_id}", response_model=schemas.RunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.Run).get(run_id)
    if not run:
        return {"error": "Run not found"}
    return run

#==============================
# METRICS ENDPOINTS
#==============================

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

