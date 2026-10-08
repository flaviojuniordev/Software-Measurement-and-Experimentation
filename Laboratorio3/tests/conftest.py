from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.fixture
def make_run():
    def factory(
        conclusion: str | None,
        started_hour: float,
        *,
        workflow_id: int = 10,
        run_id: int | None = None,
        updated_hour: float | None = None,
    ) -> dict[str, object]:
        hour = int(started_hour)
        minute = int(round((started_hour - hour) * 60))
        started = datetime(2026, 1, 10, hour, minute, tzinfo=timezone.utc)
        if updated_hour is None:
            updated_hour = started_hour
        updated_h = int(updated_hour)
        updated_m = int(round((updated_hour - updated_h) * 60))
        updated = datetime(2026, 1, 10, updated_h, updated_m, tzinfo=timezone.utc)
        return {
            "id": run_id if run_id is not None else int(started_hour * 100),
            "workflow_id": workflow_id,
            "event": "push",
            "head_branch": "main",
            "conclusion": conclusion,
            "run_started_at": started.isoformat().replace("+00:00", "Z"),
            "updated_at": updated.isoformat().replace("+00:00", "Z"),
        }

    return factory
