from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import logging_config
from app.main import app
from app.pii import hash_user_id


def _chat_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "user_id": "student-01",
        "session_id": "session-01",
        "feature": "qa",
        "message": "Explain observability",
    }
    payload.update(overrides)
    return payload


def _read_api_events(log_path: Path) -> list[dict]:
    return [
        event
        for event in (
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
        )
        if event.get("service") == "api"
    ]


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "user_id": "student-01",
                "session_id": "session-01",
                "feature": "qa",
                "message": "Explain observability",
            },
        )

    assert response.status_code == 200
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert response_event["quality_score"] == response.json()["quality_score"]


def test_chat_generates_and_returns_correlation_id(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        response = client.post("/chat", json=_chat_payload())

    assert response.status_code == 200
    correlation_id = response.json()["correlation_id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", correlation_id)
    assert response.headers["x-request-id"] == correlation_id
    assert response.headers["x-response-time-ms"].isdigit()
    assert {event["correlation_id"] for event in _read_api_events(log_path)} == {
        correlation_id
    }


def test_chat_propagates_client_correlation_id(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json=_chat_payload(),
            headers={"x-request-id": "req-client-01"},
        )

    assert response.status_code == 200
    assert response.json()["correlation_id"] == "req-client-01"
    assert response.headers["x-request-id"] == "req-client-01"
    assert {event["correlation_id"] for event in _read_api_events(log_path)} == {
        "req-client-01"
    }
