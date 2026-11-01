"""Object storage (S3 or MinIO) helpers."""
import boto3
from botocore.exceptions import ClientError

from .config import settings


def client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint or None,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


def ensure_bucket(s3=None) -> None:
    s3 = s3 or client()
    try:
        s3.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        s3.create_bucket(
            Bucket=settings.s3_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region},
        )


def upload_file(local_path: str, key: str, s3=None) -> None:
    (s3 or client()).upload_file(local_path, settings.s3_bucket, key)


def read_text(key: str, s3=None) -> str | None:
    """Return the object's text, or None if it does not exist."""
    try:
        obj = (s3 or client()).get_object(Bucket=settings.s3_bucket, Key=key)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise
    return obj["Body"].read().decode("utf-8", errors="replace")
