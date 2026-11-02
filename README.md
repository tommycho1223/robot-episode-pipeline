# Robot Episode Pipeline

An ingestion and quality-control pipeline for robot learning data. It takes raw recorded episodes (metadata plus joint-state sensor streams), stores the files in S3-compatible object storage, catalogs them in PostgreSQL, runs automated QC checks, and serves the results through a REST API.

It's modeled on a real problem: in robot data collection, a meaningful share of episodes are unusable (dropped frames, truncated recordings, corrupt or missing files). Catching them automatically at ingestion is much cheaper than finding them during training.

## Architecture

```
 raw episodes          ┌──────────────┐        ┌───────────────┐
 (metadata.json  ───▶  │   ingest     │ ─────▶ │  S3 / MinIO   │  episode files
  joint_states.csv)    │              │        └───────────────┘
                       │              │ ─────▶ ┌───────────────┐
                       └──────────────┘        │  PostgreSQL   │  episodes
                       ┌──────────────┐        │               │  qc_results
                       │  validate    │ ◀────▶ │               │
                       │ (8 QC checks)│        └───────┬───────┘
                       └──────────────┘                │
                                               ┌───────▼───────┐
                                               │ FastAPI (REST)│  /episodes, /stats
                                               └───────────────┘
```

## Quick start

Requires Docker.

```bash
docker compose up --build
```

This starts PostgreSQL and MinIO, generates 300 synthetic episodes (about 15% with planted defects), then ingests and validates them and starts the API.

- API docs: http://localhost:8000/docs
- MinIO console (browse the stored files): http://localhost:9001 (user and password: `minioadmin`)

## Quality checks

| Check | Catches |
|---|---|
| `required_fields` | Metadata missing task, duration, start time, etc. |
| `positive_duration` | Zero or negative duration |
| `sensor_file_present` | Sensor stream never uploaded |
| `sensor_parseable` | Empty or malformed CSV |
| `no_nan_values` | NaN readings in joint data |
| `monotonic_timestamps` | Out-of-order or duplicated timestamps |
| `frame_rate` | Dropped frames (median rate below 25 Hz, expected 30) |
| `duration_matches` | Recording truncated vs. reported duration (>10% or >1 s off) |

Each check result is stored per episode with a human-readable reason, so failed episodes can be triaged and re-collected.

**Verification:** on a 300-episode run with 45 planted defects, the pipeline flagged all 45, each by the correct check, and flagged none of the 255 clean episodes.

## API

| Endpoint | Description |
|---|---|
| `GET /episodes?status=failed&robot_id=arm-02` | Filter and page through episodes |
| `GET /episodes/{id}` | Episode details plus every QC result |
| `GET /stats` | Pass rate per robot, most common failure reasons |
| `GET /health` | Liveness check (includes DB) |

## Design decisions

- **Idempotent ingestion.** Re-running skips episodes already cataloged (`ON CONFLICT DO NOTHING`), so a crashed run can simply be restarted.
- **Bad data is recorded, not dropped.** Episodes with broken metadata are still ingested and then marked `failed` with a reason, so nothing disappears silently.
- **Checks are pure functions.** QC logic has no database or S3 dependency, so it's unit-tested in isolation (`tests/test_validate.py`).
- **Atomic per-episode writes.** Each episode's QC results and status update commit in one transaction.
- **Plain SQL over an ORM.** The schema and queries are explicit and easy to review, with indexes matching the API's access patterns.

## Running without Docker

```bash
pip install -e ".[dev]"
pytest                                  # unit tests
python -m robodata run-all              # needs Postgres + S3/MinIO; configure via env vars
uvicorn robodata.api:app --reload
```

Settings come from environment variables: `DATABASE_URL`, `S3_ENDPOINT`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `RAW_DIR`. Leave `S3_ENDPOINT` empty to use real AWS S3.

## Project layout

```
src/robodata/
  generate.py   synthetic episodes with planted defects
  ingest.py     upload to S3 + register in Postgres
  validate.py   QC checks + validation runner
  api.py        FastAPI service
  db.py, storage.py, config.py
sql/schema.sql
tests/test_validate.py
```
