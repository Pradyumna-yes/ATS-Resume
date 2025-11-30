# app/services/r2_fetch.py
import concurrent.futures
import io
from typing import Optional
from app.core.config import settings
import boto3

_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)

def _get_s3_client():
    """
    Reuse same boto3 client config used for presign.
    """
    endpoint = getattr(settings, "S3_ENDPOINT", None)
    access_key = getattr(settings, "S3_ACCESS_KEY", None)
    secret = getattr(settings, "S3_SECRET_KEY", None)
    region = getattr(settings, "S3_REGION", None) or "us-east-1"

    client_kwargs = {}
    if access_key and secret:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret
    if endpoint:
        client_kwargs["endpoint_url"] = endpoint
    client_kwargs["region_name"] = region
    return boto3.client("s3", **client_kwargs)

def _get_object_bytes(bucket: str, key: str) -> bytes:
    """
    Blocking function to fetch S3 object bytes. Run in threadpool for async use.
    """
    client = _get_s3_client()
    resp = client.get_object(Bucket=bucket, Key=key)
    body = resp["Body"].read()
    return body

async def get_object_bytes(bucket: str, key: str) -> Optional[bytes]:
    """
    Async wrapper for fetching object bytes from S3/R2.
    Returns bytes or raises exception (let caller decide retry).
    """
    loop = __import__("asyncio").get_event_loop()
    return await loop.run_in_executor(_thread_pool, _get_object_bytes, bucket, key)
