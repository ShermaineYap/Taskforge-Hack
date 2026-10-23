import io
import zipfile
from pathlib import Path

import pytest

from app import app

DEMO = Path(__file__).resolve().parents[1] / "demo" / "aina_fyp_chat.txt"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app.config["TESTING"] = True
    return app.test_client()


def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200 and b"While you were out" in r.data
    assert b'lang="en"' in r.data and b"Skip to main content" in r.data


def test_demo_endpoint(client):
    r = client.post("/api/demo", json={"engine": "rules"})
    body = r.get_json()
    assert r.status_code == 200 and body["demo"] and body["result"]["asked_of_you"]


def test_upload_txt(client):
    data = {"me": "Aina, Ain", "since": "last_spoke", "engine": "rules",
            "chat": (io.BytesIO(DEMO.read_bytes()), "WhatsApp Chat.txt")}
    r = client.post("/api/analyze", data=data, content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["stats"]["messages"] > 300


def test_upload_zip_export(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("WhatsApp Chat - FYP Group 7.txt", DEMO.read_text(encoding="utf-8"))
        zf.writestr("PTT-20261020-WA0007.opus", b"OggS fake audio")
    buf.seek(0)
    data = {"me": "Aina", "since": "last_spoke", "engine": "rules", "chat": (buf, "export.zip")}
    r = client.post("/api/analyze", data=data, content_type="multipart/form-data")
    body = r.get_json()
    assert r.status_code == 200
    assert body["voice"]["voice_notes"] == 7 and body["voice"]["transcribed"] == 0  # no key: not sent anywhere


def test_missing_file_is_a_clear_error(client):
    r = client.post("/api/analyze", data={"me": "Aina"}, content_type="multipart/form-data")
    assert r.status_code == 400 and "Choose your exported chat" in r.get_json()["error"]


def test_bad_file_is_a_clear_error(client):
    data = {"me": "Aina", "chat": (io.BytesIO(b"hello world"), "notes.txt")}
    r = client.post("/api/analyze", data=data, content_type="multipart/form-data")
    assert r.status_code == 422 and "Export chat" in r.get_json()["error"]


def test_ics_download(client):
    r = client.post("/api/ics", json={"deadlines": [{"what": "Draft", "iso": "2026-10-30T23:59"}]})
    assert r.status_code == 200 and r.mimetype == "text/calendar"
