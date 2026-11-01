"""Read-only REST API over the episode catalog and QC results."""
from typing import Literal

from fastapi import FastAPI, HTTPException, Query

from .db import connect

app = FastAPI(title="Robot Episode Pipeline", version="1.0")


@app.get("/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/episodes")
def list_episodes(
    status: Literal["ingested", "passed", "failed"] | None = None,
    robot_id: str | None = None,
    task: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    where, params = [], {"limit": limit, "offset": offset}
    for col, val in (("status", status), ("robot_id", robot_id), ("task", task)):
        if val is not None:
            where.append(f"{col} = %({col})s")
            params[col] = val
    sql = "SELECT * FROM episodes"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY started_at NULLS LAST, episode_id LIMIT %(limit)s OFFSET %(offset)s"
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


@app.get("/episodes/{episode_id}")
def get_episode(episode_id: str):
    with connect() as conn:
        ep = conn.execute(
            "SELECT * FROM episodes WHERE episode_id = %s", (episode_id,)
        ).fetchone()
        if ep is None:
            raise HTTPException(404, "episode not found")
        ep["qc_results"] = conn.execute(
            "SELECT check_name, passed, detail, checked_at FROM qc_results "
            "WHERE episode_id = %s ORDER BY id", (episode_id,)
        ).fetchall()
    return ep


@app.get("/stats")
def stats():
    """Pass rate per robot and the most common failure reasons."""
    with connect() as conn:
        by_robot = conn.execute("""
            SELECT robot_id,
                   count(*)                                   AS episodes,
                   count(*) FILTER (WHERE status = 'failed')  AS failed,
                   round(100.0 * count(*) FILTER (WHERE status = 'passed')
                         / NULLIF(count(*) FILTER (WHERE status <> 'ingested'), 0), 1)
                                                              AS pass_rate_pct
            FROM episodes GROUP BY robot_id ORDER BY robot_id
        """).fetchall()
        top_failures = conn.execute("""
            SELECT check_name, count(*) AS failures
            FROM qc_results WHERE NOT passed
            GROUP BY check_name ORDER BY failures DESC
        """).fetchall()
    return {"by_robot": by_robot, "top_failures": top_failures}
