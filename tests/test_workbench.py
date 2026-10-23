"""Tests for the local workbench."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from simulator import TrialSimulator
from workbench import _run_dir, assert_bind_host, create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path, n_boot=8))


def _csrf(client: TestClient) -> str:
    page = client.get("/runs/new")
    assert page.status_code == 200
    marker = 'name="csrf_token" value="'
    start = page.text.index(marker) + len(marker)
    return page.text[start : page.text.index('"', start)]


def _pair(tmp_path: Path) -> tuple[bytes, bytes]:
    simulator = TrialSimulator(seed=6)
    history = tmp_path / "history.csv"
    trial = tmp_path / "trial.csv"
    simulator.historical_controls(24).to_csv(history, index=False)
    simulator.trial(16, 12).to_csv(trial, index=False)
    return history.read_bytes(), trial.read_bytes()


def test_pages_have_one_heading_labels_and_a_skip_link(client: TestClient):
    home = client.get("/")
    upload = client.get("/runs/new")

    assert home.status_code == 200
    assert "<h1>Local workbench</h1>" in home.text
    assert 'href="#main"' in home.text
    assert 'lang="en"' in home.text
    assert "<label for=\"history\">Historical controls</label>" in upload.text
    assert "<label for=\"trial\">Trial table</label>" in upload.text
    assert "Research estimate for method review" in home.text


def test_simulator_files_reach_an_aggregate_result(client: TestClient, tmp_path: Path):
    history, trial = _pair(tmp_path)
    token = _csrf(client)
    created = client.post(
        "/runs",
        data={"csrf_token": token},
        files={
            "history": ("history.csv", history, "text/csv"),
            "trial": ("trial.csv", trial, "text/csv"),
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    mapped = client.get(created.headers["location"])
    assert "Columns match the contract" in mapped.text
    token = _csrf_from(mapped.text)
    execute_url = created.headers["location"].removesuffix("/map") + "/execute"
    finished = client.post(execute_url, data={"csrf_token": token}, follow_redirects=False)
    assert finished.status_code == 303
    results = client.get(finished.headers["location"])
    assert results.status_code == 200
    assert "Virtual control arm estimate" in results.text
    assert "ANCOVA effect" in results.text
    assert "Baseline-score ANCOVA" in results.text
    assert "<h2>Twin check on concurrent controls</h2>" in results.text
    assert "<h2>Baseline characteristics</h2>" in results.text
    assert "<h2>Run record</h2>" in results.text
    assert "<h2>Follow-up</h2>" in results.text
    assert "Bootstrap SE" in results.text

    report = client.get(finished.headers["location"] + "/report")
    body = report.json()
    assert "patient_id" not in json.dumps(body)
    assert isinstance(body["ancova_effect"], float)
    assert body["manifest"]["history_file"]["sha256"] in results.text
    assert body["twin_check"]["n_controls"] == 12


def test_results_page_renders_a_report_without_diagnostics(client: TestClient, tmp_path: Path):
    run_id = "legacyRunWithoutDiagnostic1"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    legacy = {
        "schema_version": 1,
        "library_version": "0.1.0",
        "ancova_effect": 5.0,
        "ancova_se": 1.0,
        "ancova_p": 0.001,
        "unadjusted_effect": 4.0,
        "unadjusted_se": 2.0,
        "unadjusted_p": 0.05,
        "counterfactual_effect": 4.5,
        "counterfactual_se": 0.9,
        "counterfactual_p": 0.001,
        "mean_engagement": [{"arm": "treatment", "week": 0, "mean": 55.0}],
    }
    (run_dir / "report.json").write_text(json.dumps(legacy), encoding="utf-8")

    page = client.get(f"/runs/{run_id}")

    assert page.status_code == 200
    assert "Baseline-score ANCOVA" not in page.text
    assert "<h2>Run record</h2>" not in page.text


def _csrf_from(html: str) -> str:
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def test_name_column_is_refused_and_no_report_is_written(client: TestClient, tmp_path: Path):
    planted = "CELL-TOKEN-SHOULD-NOT-RENDER"
    content = (
        "patient_id,week,treated,age,baseline_score,engagement_score,"
        "gaze_fixation,vocal_variability,patient_name\n"
        f"SYN-001,0,0,8,50,50,0.4,1.2,{planted}\n"
        f"SYN-001,1,0,8,50,51,0.4,1.2,{planted}\n"
    ).encode()
    history, _trial = _pair(tmp_path)
    token = _csrf(client)
    response = client.post(
        "/runs",
        data={"csrf_token": token},
        files={
            "history": ("history.csv", content, "text/csv"),
            "trial": ("trial.csv", history, "text/csv"),
        },
    )
    assert response.status_code == 422
    assert "identifier_column" in response.text
    assert planted not in response.text
    assert list(tmp_path.rglob("report.json")) == []


def test_parent_directory_run_id_is_not_found(client: TestClient, tmp_path: Path):
    assert client.get("/runs/%2e%2e").status_code == 404
    assert client.get("/runs/%2e%2e%2fsecret/report").status_code == 404
    with pytest.raises(HTTPException) as caught:
        _run_dir(tmp_path, "../secret")
    assert caught.value.status_code == 404


def test_post_without_csrf_token_is_rejected(client: TestClient, tmp_path: Path):
    history, trial = _pair(tmp_path)
    client.get("/runs/new")
    response = client.post(
        "/runs",
        data={"csrf_token": "not-the-cookie"},
        files={
            "history": ("history.csv", history, "text/csv"),
            "trial": ("trial.csv", trial, "text/csv"),
        },
    )
    assert response.status_code == 400
    assert list(tmp_path.rglob("report.json")) == []


def test_public_bind_is_refused():
    with pytest.raises(RuntimeError, match="127.0.0.1"):
        assert_bind_host("0.0.0.0")
    assert assert_bind_host("127.0.0.1") == "127.0.0.1"


def test_oversized_upload_is_discarded(client: TestClient, tmp_path: Path):
    client.app.state.upload_limit = 32
    token = _csrf(client)
    response = client.post(
        "/runs",
        data={"csrf_token": token},
        files={
            "history": ("history.csv", b"x" * 40, "text/csv"),
            "trial": ("trial.csv", b"y" * 10, "text/csv"),
        },
    )
    assert response.status_code == 413
    assert "upload_limit" in response.text
    assert "x" * 40 not in response.text
    assert list(tmp_path.rglob("history.csv")) == []
