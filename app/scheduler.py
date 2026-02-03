import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models
import httpx
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

def scheduler_loop():
    while True:
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
                # stop if end_time exceeded
                if schedule.end_time and now >= schedule.end_time:
                    schedule.status = "completed"
                    continue

                # create run
                run = models.Run(
                    schedule_id=schedule.id,
                    scheduled_for=schedule.next_run_at,
                    status="pending"
                )
                
                try:
                    db.add(run)
                    db.flush()  # IMPORTANT: forces INSERT now
                except IntegrityError:
                    db.rollback()
                    continue

                # advance next run
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

def execute_pending_runs():
    while True:
        db = SessionLocal()
        try:
            run = (
                db.query(models.Run)
                .filter(models.Run.execution_state == "pending")
                .order_by(models.Run.id)
                .first()
            )

            if not run:
                time.sleep(1)
                continue
            
            run.execution_state = "running"
            updated = db.query(models.Run).filter(
                models.Run.id == run.id,
                models.Run.execution_state == "pending"
            ).update({"execution_state": "running"})

            if updated == 0:
                db.rollback()
                continue
            
            db.commit()

            schedule = db.query(models.Schedule).get(run.schedule_id)
            target = db.query(models.Target).get(schedule.target_id)

            run.started_at = datetime.utcnow()
            run.attempt_count += 1
            db.commit()

            start_time = time.time()

            try:
                response = httpx.request(
                    method=target.method,
                    url=target.url,
                    headers=eval(target.headers) if target.headers else None,
                    data=target.body,
                    timeout=5.0
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
                
            if run.error_type in ["timeout", "connection_error"]:
                if run.attempt_count < 3:
                    run.status = "pending"
                    run.execution_state = "pending"
                    run.started_at = None
                    run.error_type = None
                    db.commit()
                    continue
            
            run.finished_at = datetime.utcnow()
            run.execution_state = "done"
            db.commit()

        except Exception as e:
            db.rollback()
            print("Execution error:", e)
        finally:
            db.close()

        time.sleep(0.5)
