# app/services/r2_presign.py
import boto3
import functools
import concurrent.futures
import os
from typing import Dict, Any
from app.core.config import settings

# Use synchronous boto3 but run blocking calls in threadpool to keep code async-friendly
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)

def _get_s3_client():
    """
    Create a boto3 S3 client configured for Cloudflare R2 (S3-compatible).
    Expects settings.S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_REGION, S3_PROVIDER.
    """
    endpoint = getattr(settings, "S3_ENDPOINT", None)
    access_key = getattr(settings, "S3_ACCESS_KEY", None)
    secret = getattr(settings, "S3_SECRET_KEY", None)
    region = getattr(settings, "S3_REGION", None) or "us-east-1"

    # allow fallback to boto3 defaults if env not provided (helpful for tests)
    client_kwargs = {}
    if access_key and secret:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret
    if endpoint:
        client_kwargs["endpoint_url"] = endpoint
    # set region if provided
    client_kwargs["region_name"] = region

    # create client with signature version s3v4 (default)
    return boto3.client("s3", **client_kwargs)

def generate_presigned_put_url(bucket: str, key: str, expires_in: int = 900) -> str:
    """
    Generate presigned PUT URL for direct upload.
    Synchronous; calling code may run it in executor (see example below).
    """
    client = _get_s3_client()
    params = {"Bucket": bucket, "Key": key, "ACL": "private"}
    # Using client.generate_presigned_url for put_object
    url = client.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )
    return url

# Async wrapper for FastAPI usage (run blocking in threadpool)
async def async_generate_presigned_put_url(bucket: str, key: str, expires_in: int = 900) -> str:
    loop = __import__("asyncio").get_event_loop()
    return await loop.run_in_executor(_thread_pool, generate_presigned_put_url, bucket, key, expires_in)
