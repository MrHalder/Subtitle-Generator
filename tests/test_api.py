import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_index_returns_html(client):
    async with client as c:
        response = await c.get("/")
    assert response.status_code == 200
    assert "Subtitle Generator" in response.text


@pytest.mark.asyncio
async def test_languages_endpoint(client):
    async with client as c:
        response = await c.get("/api/languages")
    assert response.status_code == 200
    data = response.json()
    assert "en" in data["languages"]
    assert "hi" in data["languages"]
    assert "hi-en" in data["languages"]


@pytest.mark.asyncio
async def test_upload_no_file(client):
    async with client as c:
        response = await c.post("/api/upload", data={"language": "en"})
    assert response.status_code == 422  # validation error - no file


@pytest.mark.asyncio
async def test_upload_unsupported_format(client):
    async with client as c:
        response = await c.post(
            "/api/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
            data={"language": "en"},
        )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_unsupported_language(client):
    async with client as c:
        response = await c.post(
            "/api/upload",
            files={"file": ("test.wav", b"\x00" * 100, "audio/wav")},
            data={"language": "fr"},
        )
    assert response.status_code == 400
    assert "Unsupported language" in response.json()["detail"]


@pytest.mark.asyncio
async def test_progress_nonexistent_job(client):
    async with client as c:
        response = await c.get("/api/progress/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_preview_nonexistent_job(client):
    async with client as c:
        response = await c.get("/api/preview/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_nonexistent_job(client):
    async with client as c:
        response = await c.get("/api/download/nonexistent")
    assert response.status_code == 404
