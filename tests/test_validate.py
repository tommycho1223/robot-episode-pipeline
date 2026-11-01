"""Unit tests for the QC checks. No database or S3 needed."""
import pytest

from robodata.validate import run_checks

GOOD_META = {
    "episode_id": "ep-1", "robot_id": "arm-01", "task": "pick_cup",
    "started_at": "2026-10-01T09:00:00+00:00", "duration_s": 2.0,
}


def make_csv(times, nan_at=None):
    lines = ["t,j1,j2,j3,j4,j5,j6"]
    for i, t in enumerate(times):
        j1 = "nan" if i == nan_at else "0.1"
        lines.append(f"{t},{j1},0.2,0.3,0.4,0.5,0.6")
    return "\n".join(lines)


GOOD_TIMES = [i / 30 for i in range(60)]  # 2 seconds at 30 Hz


def failed(results):
    return {r.check_name for r in results if not r.passed}


def test_good_episode_passes_everything():
    assert failed(run_checks(GOOD_META, make_csv(GOOD_TIMES))) == set()


@pytest.mark.parametrize("field", ["task", "duration_s", "started_at"])
def test_missing_field(field):
    meta = {k: v for k, v in GOOD_META.items() if k != field}
    assert "required_fields" in failed(run_checks(meta, make_csv(GOOD_TIMES)))


def test_zero_duration():
    assert "positive_duration" in failed(run_checks({**GOOD_META, "duration_s": 0}, make_csv(GOOD_TIMES)))


def test_missing_sensor_file():
    assert failed(run_checks(GOOD_META, None)) == {"sensor_file_present"}


def test_empty_sensor_file():
    assert "sensor_parseable" in failed(run_checks(GOOD_META, ""))


def test_nan_values():
    assert failed(run_checks(GOOD_META, make_csv(GOOD_TIMES, nan_at=10))) == {"no_nan_values"}


def test_non_monotonic_time():
    times = GOOD_TIMES.copy()
    times[20], times[21] = times[21], times[20]
    assert "monotonic_timestamps" in failed(run_checks(GOOD_META, make_csv(times)))


def test_frame_drops():
    assert "frame_rate" in failed(run_checks(GOOD_META, make_csv(GOOD_TIMES[::4])))


def test_duration_mismatch():
    meta = {**GOOD_META, "duration_s": 10.0}
    assert "duration_matches" in failed(run_checks(meta, make_csv(GOOD_TIMES)))
