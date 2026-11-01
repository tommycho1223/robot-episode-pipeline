"""Ingest raw episodes: upload files to S3, register metadata in Postgres.

Ingestion is idempotent: re-running it skips episodes already in the database.
"""
import json
import logging
from pathlib import Path

from . import storage
from .db import connect

log = logging.getLogger(__name__)

INSERT_SQL = """
INSERT INTO episodes (episode_id, robot_id, task, operator_id, started_at,
                      duration_s, success, s3_prefix)
VALUES (%(episode_id)s, %(robot_id)s, %(task)s, %(operator_id)s, %(started_at)s,
        %(duration_s)s, %(success)s, %(s3_prefix)s)
ON CONFLICT (episode_id) DO NOTHING
"""


def ingest(raw_dir: str) -> dict:
    s3 = storage.client()
    storage.ensure_bucket(s3)
    stats = {"ingested": 0, "skipped": 0, "unreadable": 0}

    with connect() as conn:
        existing = {r["episode_id"] for r in conn.execute("SELECT episode_id FROM episodes")}

        for ep_dir in sorted(Path(raw_dir).iterdir()):
            if not ep_dir.is_dir():
                continue
            meta_path = ep_dir / "metadata.json"
            try:
                meta = json.loads(meta_path.read_text())
            except (OSError, json.JSONDecodeError) as e:
                log.warning("cannot read %s: %s", meta_path, e)
                stats["unreadable"] += 1
                continue

            episode_id = meta.get("episode_id", ep_dir.name)
            if episode_id in existing:
                stats["skipped"] += 1
                continue

            prefix = f"episodes/{episode_id}/"
            for f in ep_dir.iterdir():
                storage.upload_file(str(f), prefix + f.name, s3)

            # Store whatever metadata we have. Missing required fields are
            # recorded as placeholders so validation can flag them later
            # instead of the episode silently disappearing.
            conn.execute(INSERT_SQL, {
                "episode_id": episode_id,
                "robot_id": meta.get("robot_id", "unknown"),
                "task": meta.get("task", "unknown"),
                "operator_id": meta.get("operator_id"),
                "started_at": meta.get("started_at"),
                "duration_s": meta.get("duration_s"),
                "success": meta.get("success"),
                "s3_prefix": prefix,
            })
            stats["ingested"] += 1

    return stats
