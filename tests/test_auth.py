"""Fail-closed hosted settings and append-only audit."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from audit import append_event, list_events
from auth import Actor, StaticTokenVerifier, load_hosted_settings
from simulator import TrialSimulator
from workbench import create_app

SECRET = "unit-test-client-secret-value"
HOSTED = {
    "VIRTUTRIAL_MODE": "hosted",
    "VIRTUTRIAL_OIDC_ISSUER": "https://issuer.example.test",
    "VIRTUTRIAL_OIDC_CLIENT_ID": "virtutrial-tests",
    "VIRTUTRIAL_OIDC_CLIENT_SECRET": SECRET,
}


def _verifier() -> StaticTokenVerifier:
    return StaticTokenVerifier(
        {
            "analyst-token": Actor("analyst-1", "analyst"),
            "admin-token": Actor("admin-1", "admin"),
            "auditor-token": Actor("auditor-1", "auditor"),
        }
    )


def _hosted(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(tmp_path, mode="hosted", env=HOSTED, verifier=_verifier(), n_boot=8)
    )


def _pair(tmp_path: Path) -> tuple[bytes, bytes]:
    simulator = TrialSimulator(seed=6)
    history = tmp_path / "history.csv"
    trial = tmp_path / "trial.csv"
    simulator.historical_controls(24).to_csv(history, index=False)
    simulator.trial(16, 12).to_csv(trial, index=False)
    return history.read_bytes(), trial.read_bytes()


def test_hosted_mode_without_oidc_fails_before_routes_serve(tmp_path: Path):
    with pytest.raises(RuntimeError) as caught:
        create_app(tmp_path, mode="hosted", env={"VIRTUTRIAL_MODE": "hosted"})

    message = str(caught.value)
    assert "VIRTUTRIAL_OIDC_ISSUER" in message
    assert "VIRTUTRIAL_OIDC_CLIENT_ID" in message
    assert "VIRTUTRIAL_OIDC_CLIENT_SECRET" in message


def test_secret_does_not_appear_in_errors_or_audit(tmp_path: Path):
    with pytest.raises(RuntimeError) as caught:
        load_hosted_settings(
            {
                "VIRTUTRIAL_OIDC_ISSUER": "https://issuer.example.test",
                "VIRTUTRIAL_OIDC_CLIENT_ID": "virtutrial-tests",
            }
        )
    assert SECRET not in str(caught.value)

    settings = load_hosted_settings(HOSTED)
    assert settings.client_secret == SECRET
    path = tmp_path / "audit.jsonl"
    append_event(
        path,
        {
            "ts": "2026-10-22T00:00:00+00:00",
            "actor": "analyst-1",
            "action": "run.created",
            "study_id": "runA",
            "run_id": "runA",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert SECRET not in text
    assert "run.created" in text


def test_two_appends_are_two_lines_and_cannot_be_removed(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    first = {
        "ts": "2026-10-22T00:00:00+00:00",
        "actor": "local-operator",
        "action": "run.created",
        "study_id": "aaaa",
        "run_id": "aaaa",
    }
    second = dict(first, action="run.executed", ts="2026-10-22T00:00:01+00:00")
    append_event(path, first)
    append_event(path, second)

    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    assert [event["action"] for event in list_events(path)] == ["run.created", "run.executed"]
    assert not hasattr(append_event, "delete")
    from audit import list_events as listed

    assert not hasattr(listed, "delete")


def test_auditor_cannot_download_predictions(tmp_path: Path):
    client = _hosted(tmp_path)
    history, trial = _pair(tmp_path)
    auth = {"Authorization": "Bearer analyst-token"}
    page = client.get("/runs/new", headers=auth)
    marker = 'name="csrf_token" value="'
    start = page.text.index(marker) + len(marker)
    token = page.text[start : page.text.index('"', start)]
    created = client.post(
        "/runs",
        headers=auth,
        data={"csrf_token": token},
        files={
            "history": ("history.csv", history, "text/csv"),
            "trial": ("trial.csv", trial, "text/csv"),
        },
        follow_redirects=False,
    )
    mapped = client.get(created.headers["location"], headers=auth)
    start = mapped.text.index(marker) + len(marker)
    token = mapped.text[start : mapped.text.index('"', start)]
    finished = client.post(
        created.headers["location"].removesuffix("/map") + "/execute",
        headers=auth,
        data={"csrf_token": token},
        follow_redirects=False,
    )
    result_url = finished.headers["location"]
    denied = client.get(
        result_url + "/predictions",
        headers={"Authorization": "Bearer auditor-token"},
    )
    allowed = client.get(result_url + "/predictions", headers=auth)

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert "patient_id" in allowed.text


def test_admin_delete_removes_files_and_keeps_the_audit_line(tmp_path: Path):
    client = _hosted(tmp_path)
    history, trial = _pair(tmp_path)
    auth = {"Authorization": "Bearer admin-token"}
    page = client.get("/runs/new", headers=auth)
    marker = 'name="csrf_token" value="'
    start = page.text.index(marker) + len(marker)
    token = page.text[start : page.text.index('"', start)]
    created = client.post(
        "/runs",
        headers=auth,
        data={"csrf_token": token},
        files={
            "history": ("history.csv", history, "text/csv"),
            "trial": ("trial.csv", trial, "text/csv"),
        },
        follow_redirects=False,
    )
    run_id = created.headers["location"].split("/")[2]
    mapped = client.get(created.headers["location"], headers=auth)
    start = mapped.text.index(marker) + len(marker)
    token = mapped.text[start : mapped.text.index('"', start)]
    client.post(
        f"/runs/{run_id}/delete",
        headers=auth,
        data={"csrf_token": token},
        follow_redirects=False,
    )

    assert client.get(f"/runs/{run_id}", headers=auth).status_code == 404
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "study.deleted" in lines
    assert "run.created" in lines
    assert SECRET not in lines
    assert not list(tmp_path.joinpath("runs", run_id).glob("*"))


def test_hosted_route_without_a_token_is_unauthorized(tmp_path: Path):
    client = _hosted(tmp_path)
    response = client.get("/runs/new")
    assert response.status_code == 401
    assert SECRET not in response.text
