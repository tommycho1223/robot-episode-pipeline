"""Quality-control checks for robot episodes.

The checks are pure functions (no database or S3), which keeps them easy to
unit-test. `validate_pending` wires them up to storage and the database.
"""
import csv
import io
import json
import logging
import math
import statistics
from dataclasses import dataclass

from . import storage
from .db import connect

log = logging.getLogger(__name__)

REQUIRED_FIELDS = ("episode_id", "robot_id", "task", "started_at", "duration_s")
EXPECTED_HZ = 30
MIN_HZ = 25                # below this, we consider frames dropped
DURATION_TOLERANCE = 0.10  # sensor span may differ from metadata by 10%...
DURATION_MIN_SLACK_S = 1.0  # ...or 1 second, whichever is larger


@dataclass
class CheckResult:
    check_name: str
    passed: bool
    detail: str = ""


def check_metadata(meta: dict) -> list[CheckResult]:
    missing = [f for f in REQUIRED_FIELDS if meta.get(f) in (None, "")]
    results = [CheckResult(
        "required_fields", not missing,
        f"missing: {', '.join(missing)}" if missing else "",
    )]
    dur = meta.get("duration_s")
    if dur is not None:
        ok = isinstance(dur, (int, float)) and dur > 0
        results.append(CheckResult("positive_duration", ok, "" if ok else f"duration_s={dur}"))
    return results


def parse_joint_states(text: str) -> list[list[float]]:
    """Parse the CSV into rows of floats. Raises ValueError if malformed."""
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or header[0] != "t":
        raise ValueError("missing or invalid header")
    rows = [[float(x) for x in row] for row in reader if row]
    if len(rows) < 2:
        raise ValueError(f"only {len(rows)} data rows")
    return rows


def check_sensor_data(meta: dict, csv_text: str | None) -> list[CheckResult]:
    if csv_text is None:
        return [CheckResult("sensor_file_present", False, "joint_states.csv not found")]
    results = [CheckResult("sensor_file_present", True)]

    try:
        rows = parse_joint_states(csv_text)
    except ValueError as e:
        results.append(CheckResult("sensor_parseable", False, str(e)))
        return results
    results.append(CheckResult("sensor_parseable", True))

    nan_rows = [i for i, r in enumerate(rows) if any(math.isnan(v) for v in r)]
    results.append(CheckResult(
        "no_nan_values", not nan_rows,
        f"{len(nan_rows)} row(s) with NaN, first at row {nan_rows[0]}" if nan_rows else "",
    ))

    times = [r[0] for r in rows]
    diffs = [b - a for a, b in zip(times, times[1:])]
    backwards = sum(d <= 0 for d in diffs)
    results.append(CheckResult(
        "monotonic_timestamps", backwards == 0,
        f"{backwards} non-increasing step(s)" if backwards else "",
    ))

    positive = [d for d in diffs if d > 0]
    if positive:
        hz = 1 / statistics.median(positive)
        results.append(CheckResult(
            "frame_rate", hz >= MIN_HZ,
            f"{hz:.1f} Hz (expected ~{EXPECTED_HZ})" if hz < MIN_HZ else "",
        ))

    dur = meta.get("duration_s")
    if isinstance(dur, (int, float)) and dur > 0:
        span = max(times) - min(times)
        slack = max(dur * DURATION_TOLERANCE, DURATION_MIN_SLACK_S)
        ok = abs(span - dur) <= slack
        results.append(CheckResult(
            "duration_matches", ok,
            "" if ok else f"sensor span {span:.1f}s vs metadata {dur:.1f}s",
        ))
    return results


def run_checks(meta: dict, csv_text: str | None) -> list[CheckResult]:
    return check_metadata(meta) + check_sensor_data(meta, csv_text)


def validate_pending() -> dict:
    """Validate every episode still in 'ingested' status."""
    s3 = storage.client()
    stats = {"passed": 0, "failed": 0}

    with connect() as conn:
        pending = conn.execute(
            "SELECT episode_id, s3_prefix FROM episodes WHERE status = 'ingested'"
        ).fetchall()

        for ep in pending:
            meta_text = storage.read_text(ep["s3_prefix"] + "metadata.json", s3)
            try:
                meta = json.loads(meta_text) if meta_text else {}
            except json.JSONDecodeError:
                meta = {}
            csv_text = storage.read_text(ep["s3_prefix"] + "joint_states.csv", s3)

            results = run_checks(meta, csv_text)
            passed = all(r.passed for r in results)

            with conn.transaction():
                conn.cursor().executemany(
                    "INSERT INTO qc_results (episode_id, check_name, passed, detail) "
                    "VALUES (%s, %s, %s, %s)",
                    [(ep["episode_id"], r.check_name, r.passed, r.detail) for r in results],
                )
                conn.execute(
                    "UPDATE episodes SET status = %s, validated_at = now() WHERE episode_id = %s",
                    ("passed" if passed else "failed", ep["episode_id"]),
                )
            stats["passed" if passed else "failed"] += 1

    return stats
