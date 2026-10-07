from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

import pytest

from pipeline.collectors import (
    WorkflowRunWindowLimitError,
    collect_workflow_runs,
    monthly_intervals,
)


class FakeGitHubClient:
    def __init__(self, responses: list[list[dict[str, Any]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str | int]]] = []

    def paginate(
        self,
        path: str,
        params: Mapping[str, str | int],
        *,
        item_key: str | None = None,
        limit: int | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        self.calls.append((path, dict(params)))
        return self.responses[len(self.calls) - 1]


def run(run_id: int, *, event: str = "push", branch: str = "main") -> dict[str, Any]:
    return {"id": run_id, "event": event, "head_branch": branch, "conclusion": "success"}


def test_intervalos_mensais_comecam_e_terminam_no_meio_do_mes() -> None:
    intervals = monthly_intervals(date(2025, 1, 15), date(2025, 3, 10))

    assert [(item.start, item.end) for item in intervals] == [
        (date(2025, 1, 15), date(2025, 1, 31)),
        (date(2025, 2, 1), date(2025, 2, 28)),
        (date(2025, 3, 1), date(2025, 3, 10)),
    ]


def test_intervalos_mensais_cobrem_mudanca_de_ano_e_fevereiro_bissexto() -> None:
    intervals = monthly_intervals(date(2023, 12, 20), date(2024, 3, 2))

    assert intervals[0].end == date(2023, 12, 31)
    assert intervals[1].start == date(2024, 1, 1)
    assert intervals[2].end == date(2024, 2, 29)
    assert intervals[3].end == date(2024, 3, 2)


def test_intervalo_rejeita_ordem_invalida() -> None:
    with pytest.raises(ValueError, match="posterior"):
        monthly_intervals(date(2025, 2, 1), date(2025, 1, 1))


def test_coletor_envia_filtros_mensais_deduplica_e_refiltra() -> None:
    client = FakeGitHubClient(
        [
            [run(1), run(2), run(90, event="pull_request"), run(91, branch="dev")],
            [run(2), run(3)],
        ]
    )
    result = collect_workflow_runs(
        client,
        "acme/project",
        default_branch="main",
        start_date=date(2025, 1, 15),
        end_date=date(2025, 2, 20),
    )

    assert [item["id"] for item in result] == [1, 2, 3]
    assert [call[1]["created"] for call in client.calls] == [
        "2025-01-15..2025-01-31",
        "2025-02-01..2025-02-20",
    ]
    assert all(call[0] == "/repos/acme/project/actions/runs" for call in client.calls)
    assert all(call[1]["branch"] == "main" for call in client.calls)
    assert all(call[1]["event"] == "push" for call in client.calls)


def test_coletor_rejeita_run_sem_id() -> None:
    client = FakeGitHubClient([[{"event": "push", "head_branch": "main"}]])
    with pytest.raises(ValueError, match="sem id"):
        collect_workflow_runs(
            client,
            "acme/project",
            default_branch="main",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
        )


def test_coletor_detecta_mes_no_teto_da_api() -> None:
    client = FakeGitHubClient([[run(item) for item in range(1_000)]])
    with pytest.raises(WorkflowRunWindowLimitError, match="atingiu o teto"):
        collect_workflow_runs(
            client,
            "acme/project",
            default_branch="main",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )
