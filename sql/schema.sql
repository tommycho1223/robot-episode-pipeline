-- Robot episode pipeline schema
-- One row per recorded episode, plus one row per QC check result.

CREATE TABLE IF NOT EXISTS episodes (
    episode_id      TEXT PRIMARY KEY,
    robot_id        TEXT NOT NULL,
    task            TEXT NOT NULL,
    operator_id     TEXT,
    started_at      TIMESTAMPTZ,
    duration_s      DOUBLE PRECISION,
    success         BOOLEAN,
    s3_prefix       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'ingested'
                    CHECK (status IN ('ingested', 'passed', 'failed')),
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    validated_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS qc_results (
    id              BIGSERIAL PRIMARY KEY,
    episode_id      TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
    check_name      TEXT NOT NULL,
    passed          BOOLEAN NOT NULL,
    detail          TEXT,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for the queries the API runs most often.
CREATE INDEX IF NOT EXISTS idx_episodes_status   ON episodes (status);
CREATE INDEX IF NOT EXISTS idx_episodes_robot    ON episodes (robot_id);
CREATE INDEX IF NOT EXISTS idx_qc_episode        ON qc_results (episode_id);
CREATE INDEX IF NOT EXISTS idx_qc_failed_checks  ON qc_results (check_name) WHERE NOT passed;
