"""API contract tests. These never call Vertex AI."""

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    assert client.get("/healthz").status_code == 200


def test_bootstrap_shape():
    body = client.get("/api/bootstrap").json()
    assert len(body["personas"]) == 3
    assert body["catalog"]
    assert 0 < body["discount"]["rate"] < 1
    assert body["discount"]["label"].endswith("%")


def test_bootstrap_exposes_no_model_details():
    """The UI must not be able to show a model name or provider."""
    raw = client.get("/api/bootstrap").text.lower()
    for leak in ("gemini", "vertex", "model", "project"):
        assert leak not in raw


def test_kit_stream_rejects_bad_payload():
    assert client.post("/api/kit/stream", json={}).status_code == 422
    assert client.post("/api/kit/stream", json={"persona_id": "x", "scale": 0}).status_code == 422


def test_kit_stream_emits_start_and_end():
    body = client.post(
        "/api/kit/stream",
        json={"persona_id": "hari", "cart": [{"id": "MACHINE-KEURIG-KEXPRESS", "qty": 1}]},
    ).text
    events = [json.loads(l[5:]) for l in body.splitlines() if l.startswith("data:")]
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert types[-1] == "end"


def test_parse_line_rejects_junk():
    from app.ai.stream import parse_line

    assert parse_line("```json") is None
    assert parse_line("not json") is None
    assert parse_line('{"type":"nope"}') is None
    assert parse_line('{"type":"thought","text":"hi"},') == {"type": "thought", "text": "hi"}
