import pytest
from app.services.r2_presign import async_generate_presigned_put_url


@pytest.mark.asyncio
async def test_presign(monkeypatch):
	"""Ensure the async presign wrapper returns the value returned by boto3's client."""

	class DummyClient:
		def generate_presigned_url(self, *args, **kwargs):
			return "https://example.com/fake-presign"

	def fake_boto_client(name, **kwargs):
		assert name == "s3"
		return DummyClient()

	monkeypatch.setattr("boto3.client", fake_boto_client)

	url = await async_generate_presigned_put_url("my-bucket", "my-key")
	assert url == "https://example.com/fake-presign"