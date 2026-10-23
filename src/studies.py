"""Study metadata on disk and deletion that leaves the audit log intact."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from audit import append_event, utc_now


class StudyStore(Protocol):
    def delete(self, run_id: str, actor: str) -> None:
        """Remove the run directory and append ``study.deleted``."""


class LocalStudyStore:
    """One run directory under ``root/runs``. Audit lines stay in ``audit.jsonl``."""

    def __init__(self, root: Path, resolve_run) -> None:
        self.root = Path(root)
        self.audit_path = self.root / "audit.jsonl"
        self._resolve_run = resolve_run

    def delete(self, run_id: str, actor: str) -> None:
        run_dir = self._resolve_run(self.root, run_id)
        shutil.rmtree(run_dir)
        append_event(
            self.audit_path,
            {
                "ts": utc_now(),
                "actor": actor,
                "action": "study.deleted",
                "study_id": run_id,
                "run_id": run_id,
            },
        )
