"""Settings, read from environment variables so nothing is hard-coded."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://robo:robo@localhost:5432/robodata"
    )
    s3_endpoint: str | None = os.getenv("S3_ENDPOINT", "http://localhost:9000")
    s3_bucket: str = os.getenv("S3_BUCKET", "robot-episodes")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
    aws_region: str = os.getenv("AWS_REGION", "us-west-2")
    raw_dir: str = os.getenv("RAW_DIR", "data/raw")


settings = Settings()
