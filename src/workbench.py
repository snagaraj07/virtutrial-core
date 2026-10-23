"""Workbench. Local mode has no login. Hosted mode fails closed without OIDC."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
from pathlib import Path
from typing import Mapping

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from audit import append_event, list_events, utc_now
from auth import (
    Actor,
    RejectAllVerifier,
    TokenVerifier,
    load_hosted_settings,
    parse_mode,
)
from privacy import PrivacyError
from runner import library_version, run_study
from schema import TrajectorySchemaError, read_trajectories
from studies import LocalStudyStore

ALLOWED_HOST = "127.0.0.1"
UPLOAD_LIMIT_BYTES = 50 * 1024 * 1024
_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_SUFFIXES = {".csv", ".parquet"}
_CSRF_COOKIE = "vt_csrf"
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

_TEMPLATES.env.filters["effect"] = lambda value: f"{float(value):.2f}"
_TEMPLATES.env.filters["pvalue"] = lambda value: (
    "< 0.001" if float(value) < 0.001 else f"{float(value):.3f}"
)


class UploadTooLarge(Exception):
    """The upload passed the local size limit."""


def assert_bind_host(host: str) -> str:
    """Return the only host the local workbench is allowed to bind."""

    if host != ALLOWED_HOST:
        raise RuntimeError("The local workbench listens on 127.0.0.1 only.")
    return ALLOWED_HOST


def create_app(
    data_dir: Path,
    *,
    mode: str | None = None,
    env: Mapping[str, str] | None = None,
    verifier: TokenVerifier | None = None,
    n_boot: int = 20,
) -> FastAPI:
    """Files stay under data_dir. Hosted mode raises before routes if OIDC is missing."""

    environ = env if env is not None else os.environ
    resolved_mode = parse_mode(mode if mode is not None else environ.get("VIRTUTRIAL_MODE"))
    settings = None
    if resolved_mode == "hosted":
        settings = load_hosted_settings(environ)
        if verifier is None:
            verifier = RejectAllVerifier()

    root = Path(data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    app = FastAPI(
        title="VirtuTrial workbench",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.data_dir = root
    app.state.upload_limit = UPLOAD_LIMIT_BYTES
    app.state.mode = resolved_mode
    app.state.settings = settings
    app.state.verifier = verifier
    app.state.audit_path = root / "audit.jsonl"
    app.state.store = LocalStudyStore(root, _run_dir)
    app.state.n_boot = int(n_boot)

    @app.get("/assets/workbench.css")
    def stylesheet() -> FileResponse:
        return FileResponse(
            Path(__file__).resolve().parent / "templates" / "workbench.css",
            media_type="text/css",
        )

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        actor = _actor(request, app)
        return _page(
            request,
            "home.html",
            page_title="Local workbench — VirtuTrial",
            version=library_version(),
            data_dir=str(request.app.state.data_dir),
            mode=app.state.mode,
            actor=actor,
            nav="home",
        )

    @app.get("/runs/new", response_class=HTMLResponse)
    def new_run(request: Request) -> HTMLResponse:
        actor = _actor(request, app)
        _require(actor, "analyst", "admin")
        return _page(
            request,
            "upload.html",
            page_title="Start a run — VirtuTrial",
            actor=actor,
            nav="new",
        )

    @app.post("/runs", response_class=HTMLResponse)
    async def create_run(
        request: Request,
        history: UploadFile = File(...),
        trial: UploadFile = File(...),
        csrf_token: str = Form(""),
    ) -> HTMLResponse:
        actor = _actor(request, app)
        _require(actor, "analyst", "admin")
        _check_csrf(request, csrf_token)
        run_id = secrets.token_urlsafe(16)
        run_dir = _allocate_run(root, run_id)
        try:
            history_path = run_dir / f"history{_suffix(history)}"
            trial_path = run_dir / f"trial{_suffix(trial)}"
            await _store_upload(history, history_path, app.state.upload_limit)
            await _store_upload(trial, trial_path, app.state.upload_limit)
            read_trajectories(history_path)
            read_trajectories(trial_path)
        except UploadTooLarge:
            shutil.rmtree(run_dir, ignore_errors=True)
            return _page(
                request,
                "refusal.html",
                status_code=413,
                page_title="File was too large — VirtuTrial",
                rule_id="upload_limit",
                detail="Each file must be 50 MB or smaller.",
                actor=actor,
            )
        except (PrivacyError, TrajectorySchemaError) as exc:
            shutil.rmtree(run_dir, ignore_errors=True)
            rule_id = exc.rule_id if isinstance(exc, PrivacyError) else "schema"
            return _page(
                request,
                "refusal.html",
                status_code=422,
                page_title="File was not accepted — VirtuTrial",
                rule_id=rule_id,
                detail=str(exc),
                actor=actor,
            )
        except Exception:
            shutil.rmtree(run_dir, ignore_errors=True)
            return _page(
                request,
                "refusal.html",
                status_code=422,
                page_title="File was not accepted — VirtuTrial",
                rule_id="unreadable",
                detail="The file could not be read as a table.",
                actor=actor,
            )
        _record(app, actor, "run.created", run_id)
        return _redirect(request, f"/runs/{run_id}/map")

    @app.get("/runs/{run_id}/map", response_class=HTMLResponse)
    def map_columns(request: Request, run_id: str) -> HTMLResponse:
        actor = _actor(request, app)
        _require(actor, "analyst", "admin", "auditor")
        run_dir = _run_dir(root, run_id)
        if not (run_dir / "history.csv").exists() and not (run_dir / "history.parquet").exists():
            raise HTTPException(status_code=404)
        from schema import REQUIRED_COLUMNS

        return _page(
            request,
            "map.html",
            page_title="Confirm columns — VirtuTrial",
            run_id=run_id,
            columns=REQUIRED_COLUMNS,
            actor=actor,
            nav="new",
        )

    @app.post("/runs/{run_id}/execute", response_class=HTMLResponse)
    def execute(request: Request, run_id: str, csrf_token: str = Form("")) -> HTMLResponse:
        actor = _actor(request, app)
        _require(actor, "analyst", "admin")
        _check_csrf(request, csrf_token)
        run_dir = _run_dir(root, run_id)
        try:
            run_study(
                _stored_input(run_dir, "history"),
                _stored_input(run_dir, "trial"),
                run_dir,
                n_boot=app.state.n_boot,
            )
        except (PrivacyError, TrajectorySchemaError) as exc:
            rule_id = exc.rule_id if isinstance(exc, PrivacyError) else "schema"
            return _page(
                request,
                "refusal.html",
                status_code=422,
                page_title="Run was not completed — VirtuTrial",
                rule_id=rule_id,
                detail=str(exc),
                actor=actor,
            )
        _record(app, actor, "run.executed", run_id)
        return _redirect(request, f"/runs/{run_id}")

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def results(request: Request, run_id: str) -> HTMLResponse:
        actor = _actor(request, app)
        _require(actor, "analyst", "admin", "auditor")
        report = _read_report(_run_dir(root, run_id))
        return _page(
            request,
            "results.html",
            page_title="Results — VirtuTrial",
            run_id=run_id,
            report=report,
            weeks=_week_rows(report["mean_engagement"]),
            twin=report.get("twin_check"),
            baseline=report.get("baseline_comparison") or [],
            follow=report.get("follow_up"),
            manifest=report.get("manifest"),
            actor=actor,
            can_delete=actor.role == "admin",
            can_download_predictions=actor.role in {"analyst", "admin"},
        )

    @app.get("/runs/{run_id}/report")
    def report_file(request: Request, run_id: str) -> FileResponse:
        actor = _actor(request, app)
        _require(actor, "analyst", "admin", "auditor")
        path = _run_dir(root, run_id) / "report.json"
        if not path.is_file():
            raise HTTPException(status_code=404)
        _record(app, actor, "report.exported", run_id)
        return FileResponse(path, media_type="application/json", filename="report.json")

    @app.get("/runs/{run_id}/predictions")
    def predictions_file(request: Request, run_id: str) -> FileResponse:
        actor = _actor(request, app)
        _require(actor, "analyst", "admin")
        path = _run_dir(root, run_id) / "counterfactuals.csv"
        if not path.is_file():
            raise HTTPException(status_code=404)
        _record(app, actor, "predictions.exported", run_id)
        return FileResponse(path, media_type="text/csv", filename="counterfactuals.csv")

    @app.post("/runs/{run_id}/delete", response_class=HTMLResponse)
    def delete_run(request: Request, run_id: str, csrf_token: str = Form("")) -> HTMLResponse:
        actor = _actor(request, app)
        _require(actor, "admin")
        _check_csrf(request, csrf_token)
        app.state.store.delete(run_id, actor.subject)
        return _redirect(request, "/")

    @app.get("/audit", response_class=HTMLResponse)
    def audit_page(request: Request) -> HTMLResponse:
        actor = _actor(request, app)
        _require(actor, "admin", "auditor")
        return _page(
            request,
            "audit.html",
            page_title="Audit log — VirtuTrial",
            events=list_events(app.state.audit_path),
            actor=actor,
            nav="audit",
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
        if exc.status_code == 404:
            return _page(
                request,
                "error.html",
                status_code=404,
                page_title="Page not found — VirtuTrial",
                message="That page is not available.",
            )
        if exc.status_code == 401:
            return _page(
                request,
                "error.html",
                status_code=401,
                page_title="Sign-in required — VirtuTrial",
                message="This hosted route needs a verified bearer token.",
            )
        if exc.status_code == 403:
            return _page(
                request,
                "error.html",
                status_code=403,
                page_title="Not permitted — VirtuTrial",
                message="This role cannot use that action.",
            )
        return _page(
            request,
            "error.html",
            status_code=exc.status_code,
            page_title="Request error — VirtuTrial",
            message="The request could not be completed.",
        )

    return app


def main() -> None:
    mode = parse_mode(os.environ.get("VIRTUTRIAL_MODE"))
    host = os.environ.get("VIRTUTRIAL_HOST", ALLOWED_HOST)
    if mode == "local":
        assert_bind_host(host)
    elif host != ALLOWED_HOST and mode != "hosted":
        assert_bind_host(host)
    data_dir = Path(os.environ.get("VIRTUTRIAL_DATA_DIR", ".local-data"))
    import uvicorn

    uvicorn.run(create_app(data_dir), host=host if mode == "hosted" else ALLOWED_HOST, port=8000)


def _actor(request: Request, app: FastAPI) -> Actor:
    if app.state.mode == "local":
        return Actor(subject="local-operator", role="admin")
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401)
    token = header.split(" ", 1)[1].strip()
    try:
        return app.state.verifier.verify(token)
    except Exception:
        raise HTTPException(status_code=401) from None


def _require(actor: Actor, *roles: str) -> None:
    if actor.role not in roles:
        raise HTTPException(status_code=403)


def _record(app: FastAPI, actor: Actor, action: str, run_id: str) -> None:
    append_event(
        app.state.audit_path,
        {
            "ts": utc_now(),
            "actor": actor.subject,
            "action": action,
            "study_id": run_id,
            "run_id": run_id,
        },
    )


def _page(
    request: Request,
    template: str,
    status_code: int = 200,
    **context: object,
) -> HTMLResponse:
    token = request.cookies.get(_CSRF_COOKIE) or secrets.token_urlsafe(32)
    response = _TEMPLATES.TemplateResponse(
        request,
        template,
        {"csrf_token": token, **context},
        status_code=status_code,
    )
    response.set_cookie(
        _CSRF_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return response


def _redirect(request: Request, url: str) -> HTMLResponse:
    token = request.cookies.get(_CSRF_COOKIE) or secrets.token_urlsafe(32)
    response = HTMLResponse(status_code=303, headers={"Location": url})
    response.set_cookie(_CSRF_COOKIE, token, httponly=True, samesite="strict", path="/")
    return response


def _check_csrf(request: Request, form_token: str) -> None:
    cookie = request.cookies.get(_CSRF_COOKIE, "")
    if not cookie or not form_token or not secrets.compare_digest(cookie, form_token):
        raise HTTPException(status_code=400)


def _suffix(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in _SUFFIXES:
        raise TrajectorySchemaError("File suffix must be .csv or .parquet.")
    return suffix


async def _store_upload(upload: UploadFile, dest: Path, limit: int) -> None:
    written = 0
    try:
        with dest.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise UploadTooLarge()
                handle.write(chunk)
    except UploadTooLarge:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def _allocate_run(root: Path, run_id: str) -> Path:
    if not _RUN_ID.match(run_id):
        raise HTTPException(status_code=404)
    run_dir = (root / "runs" / run_id).resolve()
    runs_root = (root / "runs").resolve()
    if runs_root not in run_dir.parents:
        raise HTTPException(status_code=404)
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _run_dir(root: Path, run_id: str) -> Path:
    if not _RUN_ID.match(run_id):
        raise HTTPException(status_code=404)
    run_dir = (root / "runs" / run_id).resolve()
    runs_root = (root / "runs").resolve()
    if runs_root not in run_dir.parents or not run_dir.is_dir():
        raise HTTPException(status_code=404)
    return run_dir


def _stored_input(run_dir: Path, stem: str) -> Path:
    matches = [
        path
        for path in run_dir.glob(stem + ".*")
        if path.is_file() and path.suffix.lower() in _SUFFIXES and path.parent == run_dir
    ]
    if len(matches) != 1:
        raise HTTPException(status_code=404)
    return matches[0]


def _read_report(run_dir: Path) -> dict:
    path = run_dir / "report.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    report = json.loads(path.read_text(encoding="utf-8"))
    report.pop("patient_id", None)
    return report


def _week_rows(means: list[dict]) -> list[dict]:
    weeks: dict[int, dict[str, str]] = {}
    for item in means:
        week = int(item["week"])
        row = weeks.setdefault(week, {"week": str(week), "treatment": "—", "control": "—"})
        arm = str(item["arm"])
        if arm in {"treatment", "control"}:
            row[arm] = f"{float(item['mean']):.2f}"
    return [weeks[week] for week in sorted(weeks)]


if __name__ == "__main__":
    main()
