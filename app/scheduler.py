import time
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models
import threading

REQUEST_TIMEOUT = httpx.Timeout(
    connect=3.0,
    read=5.0,
    write=5.0,
    pool=5.0
)

shutdown_event = threading.Event()

def schedule_runs():
    """
    Periodically scans schedules and creates Run records.
    This function NEVER executes HTTP requests.
    """
    while not shutdown_event.is_set():
        db: Session = SessionLocal()
        try:
            now = datetime.utcnow()

            schedules = (
                db.query(models.Schedule)
                .filter(
                    models.Schedule.status == "active",
                    models.Schedule.next_run_at <= now
                )
                .all()
            )

            for schedule in schedules:
                if schedule.end_time and now >= schedule.end_time:
                    schedule.status = "completed"
                    continue

                run = models.Run(
                    schedule_id=schedule.id,
                    scheduled_for=schedule.next_run_at,
                    status="pending"
                )
                db.add(run)

                schedule.next_run_at = schedule.next_run_at + timedelta(
                    seconds=schedule.interval_seconds
                )

            db.commit()

        except Exception as e:
            db.rollback()
            print("Scheduler error:", e)
        finally:
            db.close()

        time.sleep(1)

def execute_runs():
    """
    Picks pending Run records and executes HTTP requests.
    This function NEVER schedules future runs.
    """
    while not shutdown_event.is_set():
        db: Session = SessionLocal()
        try:
            run = (
                db.query(models.Run)
                .filter(models.Run.status == "pending")
                .order_by(models.Run.id)
                .first()
            )

            if not run:
                time.sleep(1)
                continue

            schedule = db.query(models.Schedule).get(run.schedule_id)
            target = db.query(models.Target).get(schedule.target_id)

            run.execution_state = "running"
            run.started_at = datetime.utcnow()
            db.commit()

            start_time = time.time()

            try:
                response = httpx.request(
                    method=target.method,
                    url=target.url,
                    headers=eval(target.headers) if target.headers else None,
                    data=target.body,
                    timeout=REQUEST_TIMEOUT
                )

                latency = int((time.time() - start_time) * 1000)

                run.status = "success"
                run.status_code = response.status_code
                run.latency_ms = latency
                run.response_size = len(response.content)

            except httpx.TimeoutException:
                run.status = "failed"
                run.error_type = "timeout"

            except httpx.RequestError:
                run.status = "failed"
                run.error_type = "connection_error"
                
            except httpx.ConnectTimeout:
                run.status = "failed"
                run.error_type = "connect_timeout"
            except httpx.ReadTimeout:
                run.status = "failed"
                run.error_type = "read_timeout"

            run.execution_state = "done"
            run.finished_at = datetime.utcnow()
            db.commit()
            
        except Exception as e:
            db.rollback()
            print("Executor error:", e)
        finally:
            db.close()

        time.sleep(0.5)