from __future__ import annotations

from datetime import datetime

import pytest

from pipeline.metrics import (
    DoraLevel,
    RunResult,
    calculate_ci_change_failure_rate,
    classify_change_failure_rate,
    classify_deployment_frequency,
    classify_lead_time,
    classify_overall_dora,
    classify_recovery_time,
    classify_run_conclusion,
    find_failure_episodes,
    summarize_recovery,
)


@pytest.mark.parametrize(
    ("conclusion", "expected"),
    [
        ("success", RunResult.SUCCESS),
        ("failure", RunResult.FAILURE),
        ("timed_out", RunResult.FAILURE),
        ("startup_failure", RunResult.FAILURE),
        ("cancelled", RunResult.IGNORED),
        ("skipped", RunResult.IGNORED),
        ("neutral", RunResult.IGNORED),
        ("action_required", RunResult.IGNORED),
        ("stale", RunResult.IGNORED),
        (None, RunResult.IGNORED),
        ("", RunResult.IGNORED),
        ("in_progress", RunResult.IGNORED),
        ("desconhecido", RunResult.IGNORED),
    ],
)
def test_classificacao_de_conclusao(conclusion: object, expected: RunResult) -> None:
    assert classify_run_conclusion(conclusion) is expected


@pytest.mark.parametrize(
    ("conclusions", "expected"),
    [
        (["success", "success"], 0.0),
        (["failure", "timed_out"], 1.0),
        (["success", "success", "failure", "timed_out"], 0.5),
        (["success", "cancelled", "neutral"], 0.0),
        (["cancelled", "skipped"], None),
        ([], None),
    ],
)
def test_cfr_de_ci(conclusions: list[str], expected: float | None) -> None:
    result = calculate_ci_change_failure_rate({"conclusion": item} for item in conclusions)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def test_um_episodio_recuperado_usa_primeira_falha_e_fim_do_sucesso(make_run) -> None:
    runs = [
        make_run("success", 9),
        make_run("failure", 10),
        make_run("timed_out", 10.5),
        make_run("startup_failure", 10.75),
        make_run("success", 11.25, updated_hour=11 + 20 / 60),
    ]

    episodes = find_failure_episodes(runs)

    assert len(episodes) == 1
    assert episodes[0].recovery_hours == pytest.approx(4 / 3)
    assert episodes[0].censored is False


def test_falha_inicial_nao_abre_episodio_sem_sucesso_anterior(make_run) -> None:
    runs = [
        make_run("failure", 8),
        make_run("failure", 9),
        make_run("success", 10, updated_hour=10.25),
    ]

    assert find_failure_episodes(runs) == []


def test_episodio_sem_sucesso_posterior_e_censurado(make_run) -> None:
    episodes = find_failure_episodes(
        [make_run("success", 8), make_run("failure", 9), make_run("failure", 10)]
    )

    assert len(episodes) == 1
    assert episodes[0].censored is True
    assert episodes[0].recovered_at is None
    assert episodes[0].recovery_hours is None


def test_multiplos_episodios_workflows_e_runs_ignoradas(make_run) -> None:
    runs = [
        make_run("success", 8, workflow_id=1),
        make_run("failure", 9, workflow_id=1),
        make_run("cancelled", 9.25, workflow_id=1),
        make_run("neutral", 9.5, workflow_id=1),
        make_run("failure", 10, workflow_id=1),
        make_run("success", 11, workflow_id=1, updated_hour=11.5),
        make_run("failure", 12, workflow_id=1),
        make_run("success", 13, workflow_id=1, updated_hour=13.25),
        make_run("failure", 10, workflow_id=2),
        make_run("success", 8, workflow_id=2),
        make_run("failure", 9, workflow_id=2),
        make_run("success", 11, workflow_id=2, updated_hour=11.25),
    ]

    episodes = find_failure_episodes(reversed(runs))

    assert len(episodes) == 3
    assert [episode.workflow_id for episode in episodes] == [1, 2, 1]
    assert [episode.recovery_hours for episode in episodes] == pytest.approx([2.5, 2.25, 1.25])


def test_resumo_calcula_mediana_e_proporcao_censurada(make_run) -> None:
    runs = [
        make_run("success", 8, workflow_id=1),
        make_run("failure", 9, workflow_id=1),
        make_run("success", 10, workflow_id=1, updated_hour=11),
        make_run("failure", 12, workflow_id=1),
        make_run("success", 8, workflow_id=2),
        make_run("failure", 9, workflow_id=2),
        make_run("success", 12, workflow_id=2, updated_hour=13),
    ]

    summary = summarize_recovery(find_failure_episodes(runs))

    assert summary.total_episodes == 3
    assert summary.recovered_episodes == 2
    assert summary.censored_episodes == 1
    assert summary.censored_proportion == pytest.approx(1 / 3)
    assert summary.median_recovery_hours == pytest.approx(3.0)


def test_resumo_vazio_representa_ausencia_de_dados() -> None:
    summary = summarize_recovery([])

    assert summary.total_episodes == 0
    assert summary.censored_proportion is None
    assert summary.median_recovery_hours is None


def test_datas_sem_timezone_sao_rejeitadas(make_run) -> None:
    runs = [make_run("success", 8), make_run("failure", 9)]
    runs[1]["run_started_at"] = datetime(2026, 1, 10, 9).isoformat()

    with pytest.raises(ValueError, match="timezone"):
        find_failure_episodes(runs)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (7, DoraLevel.ELITE),
        (1, DoraLevel.HIGH),
        (12 / 52.1, DoraLevel.MEDIUM),
        (0.1, DoraLevel.LOW),
        (None, None),
    ],
)
def test_classificacao_deployment_frequency(value, expected) -> None:
    assert classify_deployment_frequency(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (23.99, DoraLevel.ELITE),
        (24, DoraLevel.HIGH),
        (168, DoraLevel.MEDIUM),
        (720, DoraLevel.LOW),
        (None, None),
    ],
)
def test_classificacao_lead_time(value, expected) -> None:
    assert classify_lead_time(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.15, DoraLevel.ELITE),
        (0.15001, DoraLevel.HIGH),
        (0.30, DoraLevel.HIGH),
        (0.30001, DoraLevel.MEDIUM),
        (0.45, DoraLevel.MEDIUM),
        (0.45001, DoraLevel.LOW),
        (None, None),
    ],
)
def test_classificacao_cfr(value, expected) -> None:
    assert classify_change_failure_rate(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.99, DoraLevel.ELITE),
        (1, DoraLevel.HIGH),
        (24, DoraLevel.MEDIUM),
        (168, DoraLevel.LOW),
        (None, None),
    ],
)
def test_classificacao_recuperacao(value, expected) -> None:
    assert classify_recovery_time(value) is expected


def test_classificacao_geral_e_mediana_fracionaria_arredondada_para_baixo() -> None:
    assert (
        classify_overall_dora(
            DoraLevel.ELITE, DoraLevel.ELITE, DoraLevel.HIGH, DoraLevel.LOW
        )
        is DoraLevel.HIGH
    )
    assert (
        classify_overall_dora(
            DoraLevel.ELITE, DoraLevel.HIGH, DoraLevel.MEDIUM, DoraLevel.LOW
        )
        is DoraLevel.MEDIUM
    )


def test_classificacao_geral_ausente_retorna_none() -> None:
    assert classify_overall_dora(DoraLevel.ELITE, DoraLevel.HIGH, None, DoraLevel.LOW) is None


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan")])
def test_classificacoes_rejeitam_valores_invalidos(value: float) -> None:
    with pytest.raises(ValueError):
        classify_recovery_time(value)


def test_cfr_rejeita_proporcao_acima_de_um() -> None:
    with pytest.raises(ValueError, match="entre 0.0 e 1.0"):
        classify_change_failure_rate(1.01)
