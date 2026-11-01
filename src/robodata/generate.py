"""Generate fake robot episodes, some with deliberate defects.

Each episode is a folder:
    data/raw/<episode_id>/metadata.json
    data/raw/<episode_id>/joint_states.csv   (t, j1..j6 at ~30 Hz)
"""
import csv
import json
import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROBOTS = ["arm-01", "arm-02", "arm-03", "arm-04"]
TASKS = ["pick_cup", "open_drawer", "fold_towel", "stack_blocks", "wipe_table"]
OPERATORS = ["op-a", "op-b", "op-c"]
HZ = 30
DEFECTS = [
    "missing_field",
    "zero_duration",
    "missing_sensor_file",
    "empty_sensor_file",
    "nan_values",
    "non_monotonic_time",
    "duration_mismatch",
    "frame_drops",
]


def _write_joint_states(path: Path, duration_s: float, defect: str | None, rng) -> None:
    n = max(int(duration_s * HZ), 1)
    times = [i / HZ for i in range(n)]

    if defect == "frame_drops":  # keep only ~1 in 4 frames
        times = [t for i, t in enumerate(times) if i % 4 == 0]
    if defect == "non_monotonic_time" and len(times) > 10:
        i = rng.randrange(5, len(times) - 2)
        times[i], times[i + 1] = times[i + 1], times[i]

    with path.open("w", newline="") as f:
        if defect == "empty_sensor_file":
            return
        w = csv.writer(f)
        w.writerow(["t"] + [f"j{k}" for k in range(1, 7)])
        bad_row = rng.randrange(len(times)) if defect == "nan_values" else -1
        for i, t in enumerate(times):
            joints = [round(math.sin(t + k) * 0.5 + rng.gauss(0, 0.01), 4) for k in range(6)]
            if i == bad_row:
                joints[rng.randrange(6)] = float("nan")
            w.writerow([round(t, 4)] + joints)


def generate(out_dir: str, n: int = 300, defect_rate: float = 0.15, seed: int = 7) -> dict:
    """Write n episodes and return how many of each defect were planted."""
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    planted: dict[str, int] = {}
    start = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)

    for i in range(n):
        episode_id = f"ep-{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}"
        defect = rng.choice(DEFECTS) if rng.random() < defect_rate else None
        duration = round(rng.uniform(8, 40), 2)
        if defect:
            planted[defect] = planted.get(defect, 0) + 1

        meta = {
            "episode_id": episode_id,
            "robot_id": rng.choice(ROBOTS),
            "task": rng.choice(TASKS),
            "operator_id": rng.choice(OPERATORS),
            "started_at": (start + timedelta(minutes=7 * i)).isoformat(),
            "duration_s": duration,
            "success": rng.random() < 0.8,
        }
        sensor_duration = duration
        if defect == "missing_field":
            del meta[rng.choice(["task", "duration_s", "started_at"])]
        elif defect == "zero_duration":
            meta["duration_s"] = 0
        elif defect == "duration_mismatch":
            sensor_duration = duration * 0.5  # recording cut off halfway

        ep_dir = out / episode_id
        ep_dir.mkdir(exist_ok=True)
        (ep_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
        if defect != "missing_sensor_file":
            _write_joint_states(ep_dir / "joint_states.csv", sensor_duration, defect, rng)

    return {"episodes": n, "planted_defects": planted}
