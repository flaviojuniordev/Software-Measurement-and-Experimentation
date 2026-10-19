from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import pytest

from pipeline.collectors import (
    WorkflowRunWindowLimitError,
    collect_workflow_runs,
    monthly_intervals,
)
from pipeline.github_client import GitHubResponse


class FakeGitHubClient:
    def __init__(self, responses: list[GitHubResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def get(
        self,
        path: str,
        params: Mapping[str, object] | None = None,
    ) -> GitHubResponse:
        self.calls.append((path, dict(params) if params else None))
        return self.responses.pop(0)


def page(
    runs: list[dict[str, Any]],
    *,
    total_count: int | None = None,
    next_url: str | None = None,
) -> GitHubResponse:
    headers = {"link": f'<{next_url}>; rel="next"'} if next_url else {}
    return GitHubResponse(
        url="runs",
        status=200,
        headers=headers,
        data={
            "total_count": len(runs) if total_count is None else total_count,
            "workflow_runs": runs,
        },
    )


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


def test_coletor_usa_janela_adaptativa_pagina_deduplica_e_refiltra() -> None:
    client = FakeGitHubClient(
        [
            page(
                [run(1), run(2), run(90, event="pull_request"), run(91, branch="dev")],
                total_count=6,
                next_url="https://api.github.com/next",
            ),
            page([run(2), run(3)], total_count=6),
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
    assert client.calls[0][1]["created"] == "2025-01-15..2025-02-20"
    assert client.calls[0][1]["branch"] == "main"
    assert client.calls[0][1]["event"] == "push"
    assert client.calls[0][1]["exclude_pull_requests"] is True
    assert client.calls[1] == ("https://api.github.com/next", None)


def test_coletor_rejeita_run_sem_id() -> None:
    client = FakeGitHubClient(
        [page([{"event": "push", "head_branch": "main"}])]
    )
    with pytest.raises(ValueError, match="sem id"):
        collect_workflow_runs(
            client,
            "acme/project",
            default_branch="main",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
        )


def test_coletor_subdivide_mes_no_teto_da_api() -> None:
    client = FakeGitHubClient(
        [
            page([run(999)], total_count=1_000),
            page([run(1)]),
            page([run(2)]),
        ]
    )

    result = collect_workflow_runs(
        client,
        "acme/project",
        default_branch="main",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )

    assert [item["id"] for item in result] == [1, 2]
    assert [call[1]["created"] for call in client.calls] == [
        "2025-01-01..2025-01-31",
        "2025-01-01..2025-01-16",
        "2025-01-17..2025-01-31",
    ]


def test_coletor_rejeita_um_unico_dia_no_teto_da_api() -> None:
    client = FakeGitHubClient([page([run(1)], total_count=1_000)])
    with pytest.raises(WorkflowRunWindowLimitError, match="atingiu o teto"):
        collect_workflow_runs(
            client,
            "acme/project",
            default_branch="main",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 1),
        )


def test_coletor_parcial_nao_subdivide_mes_no_teto_da_api() -> None:
    client = FakeGitHubClient([page([run(1)], total_count=1_000)])

    with pytest.raises(WorkflowRunWindowLimitError, match="amostra parcial"):
        collect_workflow_runs(
            client,
            "acme/project",
            default_branch="main",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            subdivide_large_windows=False,
        )

    assert len(client.calls) == 1


def test_coletor_parcial_rejeita_volume_total_acima_do_limite() -> None:
    client = FakeGitHubClient([page([run(1)], total_count=6)])

    with pytest.raises(WorkflowRunWindowLimitError, match="ultrapassou 4"):
        collect_workflow_runs(
            client,
            "acme/project",
            default_branch="main",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 28),
            max_runs=4,
        )
