from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Target(Base):
    __tablename__ = "targets"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    method = Column(String, nullable=False)
    headers = Column(String)      # store as JSON string
    body = Column(String)         # store as JSON string

    schedules = relationship("Schedule", back_populates="target")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False)

    interval_seconds = Column(Integer, nullable=False)
    status = Column(String, default="active")  # active | paused | completed
    next_run_at = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

    target = relationship("Target", back_populates="schedules")
    runs = relationship("Run", back_populates="schedule")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)

    scheduled_for = Column(DateTime, nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)

    status = Column(String)  # success | failed
    status_code = Column(Integer)
    error_type = Column(String)
    latency_ms = Column(Integer)
    response_size = Column(Integer)

    execution_state = Column(
        String,
        default="pending"
    )

    schedule = relationship("Schedule", back_populates="runs")
