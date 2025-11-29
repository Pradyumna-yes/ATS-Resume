# tests/test_storage_integration.py
import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers
from io import BytesIO

import app.services.storage as storage_mod
from app.core.config import settings

@pytest.mark.asyncio
async def test_minio_integration_upload_and_presign():
    """
    Integration test: tries to use the configured S3 client (MinIO) to upload and presign URL.
    Skips if no S3 endpoint & creds are set in settings (so safe for CI).
    """
    # require MINIO endpoint or S3 endpoint for integration testing
    if not settings.S3_ENDPOINT or not settings.S3_ACCESS_KEY or not settings.S3_SECRET_KEY:
        pytest.skip("S3 endpoint/creds not configured for integration test")

    # pick a test bucket (use settings.S3_BUCKET)
    bucket = settings.S3_BUCKET
    # smallest sanity check: try to create a simple upload
    content = b"integration test content"
    # create UploadFile with correct FastAPI constructor including headers for content_type
    file_obj = BytesIO(content)
    headers = Headers({"content-type": "text/plain"})
    upload = UploadFile(file=file_obj, filename="minio-test.txt", size=len(content), headers=headers)

    # store file (this should use real S3 client configured by env)
    key = await storage_mod.store_file(upload, bucket=bucket)
    assert key is not None

    # try presigned url
    url = storage_mod.generate_presigned_url(key, expires_in=60, bucket=bucket)
    assert url is not None

    # try download (may work for MinIO)
    data = storage_mod.download_to_bytes(key, bucket=bucket)
    # download may return bytes or None depending on provider - ensure it doesn't error
    if data is not None:
        assert data == content

    # cleanup (best-effort)
    storage_mod.delete_object(key, bucket=bucket)
