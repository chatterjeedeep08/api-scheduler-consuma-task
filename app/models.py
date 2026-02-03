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
from sqlalchemy import UniqueConstraint
from sqlalchemy import Column, Integer

class Target(Base):
    __tablename__ = "targets"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    method = Column(String, nullable=False)
    headers = Column(String)      # store as JSON string
    body = Column(String)         # store as JSON string

    schedules = relationship(
        "Schedule",
        back_populates="target",
        cascade="all, delete-orphan"
    )


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False)

    interval_seconds = Column(Integer, nullable=False)
    status = Column(String, default="active")  # active | paused | completed
    next_run_at = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

    target = relationship("Target", back_populates="schedules")
    runs = relationship(
    "Run",
    back_populates="schedule",
    cascade="all, delete-orphan"
)


class Run(Base):
    __tablename__ = "runs"
    
    __table_args__ = (
        UniqueConstraint(
            "schedule_id",
            "scheduled_for",
            name="uq_schedule_run"
        ),
    )

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
    reattempt_count = Column(Integer, default=0)
    execution_state = Column(
        String,
        default="pending"
    )
    schedule = relationship("Schedule", back_populates="runs")
