# app/services/storage.py
import os
import uuid
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
import aiofiles

from app.core.config import settings

# Local upload directory for dev fallback
LOCAL_UPLOAD_DIR = Path("uploads")
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _get_s3_client() -> Optional[boto3.client]:
    """
    Return a boto3 S3 client configured for Cloudflare R2 or MinIO.
    If no S3_ENDPOINT or credentials are configured, returns None.
    """
    endpoint = settings.S3_ENDPOINT
    access_key = settings.S3_ACCESS_KEY
    secret_key = settings.S3_SECRET_KEY

    # If we have MinIO specific env set and S3 provider is minio, prefer that
    if settings.S3_PROVIDER and settings.S3_PROVIDER.lower() == "minio" and settings.MINIO_ENDPOINT:
        endpoint = settings.MINIO_ENDPOINT
        access_key = settings.MINIO_ACCESS_KEY
        secret_key = settings.MINIO_SECRET_KEY

    if not endpoint or not access_key or not secret_key:
        return None

    # Use signature s3v4 for compatibility (Cloudflare R2 & MinIO)
    client = boto3.client(
        "s3",
        endpoint_url=str(endpoint),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name=(settings.S3_REGION or None),
    )
    return client


def ensure_bucket(client: boto3.client, bucket: str) -> bool:
    """
    Ensure the bucket exists. For MinIO this may be necessary in dev.
    Returns True if bucket exists or was created successfully.
    """
    if client is None:
        return False
    try:
        # Try head_bucket (supported by S3, R2)
        client.head_bucket(Bucket=bucket)
        return True
    except ClientError:
        # Try to create bucket (works for MinIO; R2 buckets are created in Cloudflare UI usually)
        try:
            # For some S3 providers you must not pass LocationConstraint
            client.create_bucket(Bucket=bucket)
            return True
        except ClientError:
            # Can't create bucket (likely R2) — return False
            return False


async def store_file(file: UploadFile, bucket: Optional[str] = None) -> str:
    """
    Async store: tries configured S3-compatible client, then MinIO fallback, then local filesystem.
    Returns storage key (S3 key) or local path string.
    """
    contents = await file.read()
    ext = Path(file.filename).suffix
    key = f"{uuid.uuid4().hex}{ext}"

    bucket = bucket or settings.S3_BUCKET

    s3 = _get_s3_client()
    if s3:
        try:
            # ensure bucket exists for local MinIO dev; for R2 it will typically already exist
            _ = ensure_bucket(s3, bucket)
            s3.put_object(Bucket=bucket, Key=key, Body=contents, ContentType=file.content_type)
            return key
        except Exception as e:
            print("S3 upload failed, falling back. Error:", repr(e))

    # Fallback: local filesystem
    local_path = LOCAL_UPLOAD_DIR / key
    async with aiofiles.open(local_path, "wb") as out:
        await out.write(contents)
    return str(local_path)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream", bucket: Optional[str] = None) -> str:
    """
    Blocking upload helper for bytes. Returns key or local path.
    """
    bucket = bucket or settings.S3_BUCKET
    s3 = _get_s3_client()
    if s3:
        try:
            ensure_bucket(s3, bucket)
            s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
            return key
        except Exception as e:
            print("S3 upload_bytes failed, falling back locally. Error:", repr(e))

    # Local fallback
    path = LOCAL_UPLOAD_DIR / key
    path.write_bytes(data)
    return str(path)


def generate_presigned_url(key: str, expires_in: int = 3600, bucket: Optional[str] = None) -> Optional[str]:
    """
    Generate a presigned GET URL (works for S3-compatible providers).
    For local fallback returns file:// path if file exists.
    """
    bucket = bucket or settings.S3_BUCKET
    s3 = _get_s3_client()
    if s3:
        try:
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            print("generate_presigned_url failed:", repr(e))
            return None

    # Local file fallback
    p = Path(key) if Path(key).exists() else (LOCAL_UPLOAD_DIR / key)
    if p.exists():
        return f"file://{p.resolve()}"
    return None


def download_to_bytes(key: str, bucket: Optional[str] = None) -> Optional[bytes]:
    """
    Blocking download. Returns bytes or None.
    """
    bucket = bucket or settings.S3_BUCKET
    s3 = _get_s3_client()
    if s3:
        try:
            resp = s3.get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()
        except Exception as e:
            print("S3 download failed:", repr(e))
            return None

    # Local fallback
    p = Path(key) if Path(key).exists() else (LOCAL_UPLOAD_DIR / key)
    if p.exists():
        return p.read_bytes()
    return None


def delete_object(key: str, bucket: Optional[str] = None) -> bool:
    """
    Delete object from S3 (or local file). Returns True on success.
    """
    bucket = bucket or settings.S3_BUCKET
    s3 = _get_s3_client()
    if s3:
        try:
            s3.delete_object(Bucket=bucket, Key=key)
            return True
        except Exception as e:
            print("S3 delete failed:", repr(e))
            return False

    # Local fallback
    p = Path(key) if Path(key).exists() else (LOCAL_UPLOAD_DIR / key)
    try:
        if p.exists():
            p.unlink()
        return True
    except Exception as e:
        print("Local delete failed:", repr(e))
        return False
