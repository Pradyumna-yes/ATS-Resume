# tests/test_storage_unit.py
import pytest
from io import BytesIO
from fastapi import UploadFile
from starlette.datastructures import Headers

import app.services.storage as storage_mod

class DummyS3Client:
    def __init__(self):
        self.objects = {}
        self.buckets = set()

    def head_bucket(self, Bucket):
        if Bucket not in self.buckets:
            raise Exception("NoSuchBucket")

    def create_bucket(self, Bucket):
        self.buckets.add(Bucket)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        # store bytes
        # Body may be bytes or a file-like; we expect bytes in our test use
        self.objects[(Bucket, Key)] = Body
        return {"ETag": '"dummy-etag"'}

    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
        bucket = Params["Bucket"]
        key = Params["Key"]
        return f"https://fake.s3/{bucket}/{key}?expires_in={ExpiresIn}"

    def get_object(self, Bucket, Key):
        data = self.objects.get((Bucket, Key))
        if data is None:
            raise Exception("NoSuchKey")
        # If data is bytes, return a BytesIO-like Body
        from io import BytesIO
        return {"Body": BytesIO(data)}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


@pytest.mark.asyncio
async def test_store_file_calls_s3_put(monkeypatch):
    """
    Unit test: monkeypatch boto3.client to return a dummy client that records put_object calls.
    """
    dummy = DummyS3Client()
    # Create the test bucket so put_object works
    dummy.create_bucket("unit-test-bucket")

    # monkeypatch boto3.client used in storage._get_s3_client
    def fake_boto3_client(*args, **kwargs):
        return dummy

    monkeypatch.setattr("app.services.storage.boto3.client", fake_boto3_client)

    # create a fake UploadFile with correct FastAPI constructor
    content = b"hello unit test"
    file_obj = BytesIO(content)
    headers = Headers({"content-type": "text/plain"})
    upload = UploadFile(file=file_obj, filename="test.txt", size=len(content), headers=headers)

    # call store_file
    key = await storage_mod.store_file(upload, bucket="unit-test-bucket")
    assert key.endswith(".txt")

    # verify that the object was stored in dummy client
    assert ("unit-test-bucket", key) in dummy.objects
    # dummy stored raw bytes
    assert dummy.objects[("unit-test-bucket", key)] == content

    # presigned url
    url = storage_mod.generate_presigned_url(key, expires_in=60, bucket="unit-test-bucket")
    assert "fake.s3/unit-test-bucket" in url

    # download
    data = storage_mod.download_to_bytes(key, bucket="unit-test-bucket")
    assert data == content

    # delete
    ok = storage_mod.delete_object(key, bucket="unit-test-bucket")
    assert ok
    assert ("unit-test-bucket", key) not in dummy.objects
