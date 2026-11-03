"""DATA-5: photos are uploaded on selection and only URLs are saved."""
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.api.v1 import vendor_stays
from app.integrations.cloudinary import CloudinaryIntegrationError
from app.models.user import User

app = FastAPI()
app.include_router(vendor_stays.router, prefix="/vendor/stays")
app.dependency_overrides[vendor_stays.require_stay_vendor] = lambda: User(id="00000000-0000-0000-0000-000000000001")
client = TestClient(app)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def test_uploads_return_urls(monkeypatch):
    calls = []

    def fake_upload(data, folder, public_id=None):
        calls.append((len(data), folder))
        return {"secure_url": f"https://res.cloudinary.test/{len(calls)}.png", "public_id": f"id{len(calls)}", "width": 10, "height": 10}

    monkeypatch.setattr(vendor_stays, "upload_image", fake_upload)
    response = client.post("/vendor/stays/images", files=[("files", ("a.png", PNG, "image/png")), ("files", ("b.png", PNG, "image/png"))])
    assert response.status_code == 200
    urls = [img["url"] for img in response.json()["images"]]
    assert urls == ["https://res.cloudinary.test/1.png", "https://res.cloudinary.test/2.png"]
    assert all(folder.startswith("tour-ceylon/vendor-stays/") for _, folder in calls)


def test_rejects_non_images(monkeypatch):
    monkeypatch.setattr(vendor_stays, "upload_image", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not upload")))
    response = client.post("/vendor/stays/images", files=[("files", ("x.pdf", b"%PDF", "application/pdf"))])
    assert response.status_code == 415


def test_rejects_oversized_and_empty(monkeypatch):
    monkeypatch.setattr(vendor_stays, "MAX_UPLOAD_IMAGE_BYTES", 100)
    monkeypatch.setattr(vendor_stays, "upload_image", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not upload")))
    assert client.post("/vendor/stays/images", files=[("files", ("big.png", b"0" * 500, "image/png"))]).status_code == 413
    assert client.post("/vendor/stays/images", files=[("files", ("e.png", b"", "image/png"))]).status_code == 400


def test_cloudinary_failure_is_a_502(monkeypatch):
    def boom(*a, **k):
        raise CloudinaryIntegrationError("down")

    monkeypatch.setattr(vendor_stays, "upload_image", boom)
    assert client.post("/vendor/stays/images", files=[("files", ("a.png", PNG, "image/png"))]).status_code == 502
