# API Scheduler (Cron-like Service)

A backend service that allows users to schedule HTTP requests to external targets, similar to a cron system for API calls.  
The system persists schedules, executes requests reliably, records execution history, and exposes observability endpoints.

---

## Features

- Define **Targets** (URL, HTTP method, headers, body)
- Create **Schedules** to trigger targets at fixed intervals
- Pause / resume / delete schedules
- Persistent scheduling across server restarts
- Execute HTTP requests with enforced timeouts
- Record **Runs** with execution metadata
- Filterable run history
- Basic metrics endpoint
- Graceful shutdown of background workers

---

## Architecture Overview

The system is intentionally split into two background components:

### Scheduler
- Periodically scans persisted schedules
- Determines which schedules are due
- Creates immutable `Run` records
- Advances `next_run_at`
- Never performs HTTP requests

### Executor
- Picks pending `Run` records
- Executes HTTP requests against targets
- Records status, latency, response size, and errors
- Updates run state atomically

The **database acts as the coordination layer**, making the system:
- Restart-safe
- Deterministic
- Easy to reason about

---

## Data Model

### Target
Represents *what* to call.
- `url`
- `method`
- `headers` (stored as JSON string)
- `body` (stored as JSON string)

### Schedule
Represents *when* to call.
- `target_id`
- `interval_seconds`
- `next_run_at`
- `status` (active / paused / completed)
- optional `end_time`

### Run
Represents *what happened*.
- `scheduled_for`
- `started_at`
- `finished_at`
- `status` (success / failed)
- `status_code`
- `latency_ms`
- `response_size`
- `error_type`

---

## API Endpoints

### Targets
- `POST /targets`
- `GET /targets`
- `PUT /targets/{id}`
- `DELETE /targets/{id}`

### Schedules
- `POST /schedules`
- `GET /schedules`
- `GET /schedules/{id}`
- `POST /schedules/{id}/pause`
- `POST /schedules/{id}/resume`
- `DELETE /schedules/{id}`

### Runs & Metrics
- `GET /runs`  
  (filter by schedule, status, and time range)
- `GET /runs/{id}`
- `GET /metrics`

---

## How Scheduling Works

1. Schedules are stored with a `next_run_at` timestamp
2. The scheduler periodically checks for schedules that are due
3. For each due schedule:
   - A `Run` record is created
   - `next_run_at` is advanced
4. The executor picks pending runs and performs HTTP requests
5. Execution results are persisted for observability

---

## Reliability & Safety Guarantees

- No in-memory scheduling
- Schedules survive process restarts
- Database-driven coordination
- Explicit HTTP timeouts enforced
- Graceful shutdown via shutdown signals
- Clear separation between scheduling and execution

---

## Tech Stack

- Python
- FastAPI
- SQLAlchemy
- SQLite
- httpx

> SQLite is used for simplicity and ease of local setup.  
> In production, this would be replaced with PostgreSQL.

---

## How to Run Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:
- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

---

## Tradeoffs & Future Improvements

### Current Tradeoffs

- Single-process background workers
- SQLite instead of PostgreSQL
- Simple retry strategy
- No distributed locking

### Future Improvements

- PostgreSQL with row-level locking
- Multiple executor workers
- Exponential retry backoff
- Dead-letter queue
- Authentication & authorization
- Prometheus-compatible metrics

---

## AI Usage

AI tools were used for:

- Iterative design validation
- Architecture review
- Edge-case analysis
- Refactoring guidance

All implementation, design decisions, and testing were done by me.
Tools used: ChatGPT 5.2, Claude Sonnet 4.5

---