import os
import logging
import boto3
from botocore.config import Config as BotoConfig

from config import AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION

log = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
            config=BotoConfig(retries={"max_attempts": 3, "mode": "standard"}),
        )
    return _client


def download_file(bucket: str, key: str, local_path: str):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    log.info(f"S3 download: s3://{bucket}/{key} → {local_path}")
    _get_client().download_file(bucket, key, local_path)
    log.info(f"S3 download complete: {os.path.getsize(local_path)} bytes")


def upload_file(local_path: str, bucket: str, key: str):
    log.info(f"S3 upload: {local_path} → s3://{bucket}/{key}")
    _get_client().upload_file(local_path, bucket, key)
    log.info("S3 upload complete")
