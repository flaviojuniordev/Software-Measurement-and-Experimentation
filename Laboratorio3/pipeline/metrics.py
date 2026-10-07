"""Calculos das metricas DORA de velocidade e estabilidade."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from statistics import median
from typing import Any, Iterable, Mapping


WEEKS_PER_YEAR = 52.1
MONTHS_PER_YEAR = 12
ONE_RELEASE_PER_MONTH_WEEKLY = MONTHS_PER_YEAR / WEEKS_PER_YEAR


class RunResult(str, Enum):
    """Resultado relevante de uma execucao de workflow."""

    SUCCESS = "success"
    FAILURE = "failure"
    IGNORED = "ignored"


class DoraLevel(str, Enum):
    """Categorias de desempenho adotadas pela disciplina."""

    ELITE = "Elite"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(frozen=True)
class FailureEpisode:
    """Episodio de falha de um unico workflow."""

    workflow_id: int | str
    started_at: datetime
    recovered_at: datetime | None
    recovery_hours: float | None
    censored: bool


@dataclass(frozen=True)
class RecoverySummary:
    """Agregacao dos episodios de recuperacao de um repositorio."""

    total_episodes: int
    recovered_episodes: int
    censored_episodes: int
    censored_proportion: float | None
    median_recovery_hours: float | None


SUCCESS_CONCLUSIONS = {"success"}
FAILURE_CONCLUSIONS = {"failure", "timed_out", "startup_failure"}


def parse_github_datetime(
    value: str | datetime, field_name: str = "datetime"
) -> datetime:
    """Converte uma data ISO 8601 timezone-aware e normaliza para UTC."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} possui data ISO 8601 invalida: {value!r}"
            ) from exc
    else:
        raise ValueError(f"{field_name} deve conter uma data ISO 8601")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} deve possuir timezone")
    return parsed.astimezone(timezone.utc)


def deployment_frequency(
    releases: Iterable[dict[str, Any]], start_date: date, end_date: date
) -> float:
    """Retorna releases publicadas por semana na janela inclusiva."""

    if start_date > end_date:
        raise ValueError("start_date deve ser anterior ou igual a end_date")
    release_count = sum(
        1
        for release in releases
        if _is_main_release_in_window(release, start_date, end_date)
    )
    weeks = ((end_date - start_date).days + 1) / 7
    return release_count / weeks


def lead_time_values(
    comparisons: Iterable[dict[str, Any]],
) -> tuple[list[float], list[float]]:
    """Calcula lead time em horas por release e por commit."""

    per_release: list[float] = []
    per_commit: list[float] = []
    for comparison in comparisons:
        published_at = comparison.get("release_published_at")
        commits = comparison.get("commits", [])
        if not published_at or not commits:
            continue
        release_date = parse_github_datetime(published_at, "release_published_at")
        commit_dates = [
            parse_github_datetime(commit["author_date"], "author_date")
            for commit in commits
            if commit.get("author_date")
        ]
        if not commit_dates:
            continue
        values = [
            (release_date - commit_date).total_seconds() / 3_600
            for commit_date in commit_dates
        ]
        per_release.append(max(values))
        per_commit.extend(values)
    return per_release, per_commit


def lead_time_summary(comparisons: Iterable[dict[str, Any]]) -> dict[str, Any]:
    per_release, per_commit = lead_time_values(comparisons)
    return {
        "lead_time_release_median_hours": median(per_release)
        if per_release
        else None,
        "lead_time_commit_median_hours": median(per_commit) if per_commit else None,
        "lead_time_release_observations": len(per_release),
        "lead_time_commit_observations": len(per_commit),
    }


def classify_run_conclusion(conclusion: object) -> RunResult:
    """Classifica uma conclusao; estados desconhecidos sao ignorados."""

    if not isinstance(conclusion, str):
        return RunResult.IGNORED
    normalized = conclusion.strip().lower()
    if normalized in SUCCESS_CONCLUSIONS:
        return RunResult.SUCCESS
    if normalized in FAILURE_CONCLUSIONS:
        return RunResult.FAILURE
    return RunResult.IGNORED


def count_valid_workflow_runs(runs: Iterable[Mapping[str, Any]]) -> int:
    """Conta somente sucessos e falhas que entram nas metricas."""

    return sum(
        classify_run_conclusion(run.get("conclusion")) is not RunResult.IGNORED
        for run in runs
    )


def calculate_ci_change_failure_rate(
    runs: Iterable[Mapping[str, Any]],
) -> float | None:
    """Calcula CFR de CI em 0.0--1.0 ou ``None`` se nao houver run valida."""

    successes = 0
    failures = 0
    for run in runs:
        result = classify_run_conclusion(run.get("conclusion"))
        if result is RunResult.SUCCESS:
            successes += 1
        elif result is RunResult.FAILURE:
            failures += 1
    denominator = successes + failures
    return failures / denominator if denominator else None


def find_failure_episodes(
    runs: Iterable[Mapping[str, Any]],
) -> list[FailureEpisode]:
    """Encontra episodios por workflow conforme a definicao oficial da RQ04.

    Um episodio e aberto pela primeira falha posterior a um sucesso observado.
    Falhas consecutivas permanecem no mesmo episodio e runs ignoradas nao alteram
    o estado do workflow.
    """

    grouped: dict[
        int | str, list[tuple[datetime, str, Mapping[str, Any]]]
    ] = defaultdict(list)
    for run in runs:
        result = classify_run_conclusion(run.get("conclusion"))
        if result is RunResult.IGNORED:
            continue
        workflow_id = run.get("workflow_id")
        if workflow_id is None:
            raise ValueError("workflow_id e obrigatorio para calcular recuperacao")
        started_at = parse_github_datetime_value(
            run.get("run_started_at"), "run_started_at"
        )
        run_id = str(run.get("id", ""))
        grouped[workflow_id].append((started_at, run_id, run))

    episodes: list[FailureEpisode] = []
    for workflow_id, workflow_runs in grouped.items():
        workflow_runs.sort(key=lambda item: (item[0], item[1]))
        seen_success = False
        open_failure: datetime | None = None
        for started_at, _run_id, run in workflow_runs:
            result = classify_run_conclusion(run.get("conclusion"))
            if result is RunResult.SUCCESS:
                if open_failure is not None:
                    recovered_at = parse_github_datetime_value(
                        run.get("updated_at"), "updated_at"
                    )
                    recovery_hours = (
                        recovered_at - open_failure
                    ).total_seconds() / 3_600
                    if recovery_hours < 0:
                        raise ValueError(
                            "updated_at do sucesso antecede o inicio da falha"
                        )
                    episodes.append(
                        FailureEpisode(
                            workflow_id=workflow_id,
                            started_at=open_failure,
                            recovered_at=recovered_at,
                            recovery_hours=recovery_hours,
                            censored=False,
                        )
                    )
                    open_failure = None
                seen_success = True
            elif seen_success and open_failure is None:
                open_failure = started_at
        if open_failure is not None:
            episodes.append(
                FailureEpisode(
                    workflow_id=workflow_id,
                    started_at=open_failure,
                    recovered_at=None,
                    recovery_hours=None,
                    censored=True,
                )
            )
    return sorted(
        episodes, key=lambda episode: (episode.started_at, str(episode.workflow_id))
    )


def parse_github_datetime_value(value: object, field_name: str) -> datetime:
    """Valida valores de dicionarios antes de usar o parser publico tipado."""

    if not isinstance(value, (str, datetime)):
        raise ValueError(f"{field_name} deve conter uma data ISO 8601")
    return parse_github_datetime(value, field_name)


def summarize_recovery(episodes: Iterable[FailureEpisode]) -> RecoverySummary:
    """Resume recuperacao sem atribuir duracao artificial aos censurados."""

    episode_list = list(episodes)
    recovered_hours = [
        episode.recovery_hours
        for episode in episode_list
        if not episode.censored and episode.recovery_hours is not None
    ]
    censored = sum(episode.censored for episode in episode_list)
    total = len(episode_list)
    return RecoverySummary(
        total_episodes=total,
        recovered_episodes=len(recovered_hours),
        censored_episodes=censored,
        censored_proportion=censored / total if total else None,
        median_recovery_hours=median(recovered_hours) if recovered_hours else None,
    )


def _validate_nonnegative(value: float, metric_name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{metric_name} deve ser um numero finito e nao negativo")
    return numeric


def classify_deployment_frequency(
    releases_per_week: float | None,
) -> DoraLevel | None:
    """Classifica releases por semana; 1/mes equivale a 12/52,1 por semana."""

    if releases_per_week is None:
        return None
    value = _validate_nonnegative(releases_per_week, "deployment frequency")
    if value >= 7:
        return DoraLevel.ELITE
    if value >= 1:
        return DoraLevel.HIGH
    if value >= ONE_RELEASE_PER_MONTH_WEEKLY:
        return DoraLevel.MEDIUM
    return DoraLevel.LOW


def classify_lead_time(lead_time_hours: float | None) -> DoraLevel | None:
    """Classifica o lead time mediano, recebido em horas."""

    if lead_time_hours is None:
        return None
    value = _validate_nonnegative(lead_time_hours, "lead time")
    if value < 24:
        return DoraLevel.ELITE
    if value < 24 * 7:
        return DoraLevel.HIGH
    if value < 24 * 30:
        return DoraLevel.MEDIUM
    return DoraLevel.LOW


def classify_change_failure_rate(cfr: float | None) -> DoraLevel | None:
    """Classifica CFR recebido como proporcao entre 0.0 e 1.0."""

    if cfr is None:
        return None
    value = _validate_nonnegative(cfr, "change failure rate")
    if value > 1:
        raise ValueError("change failure rate deve estar entre 0.0 e 1.0")
    if value <= 0.15:
        return DoraLevel.ELITE
    if value <= 0.30:
        return DoraLevel.HIGH
    if value <= 0.45:
        return DoraLevel.MEDIUM
    return DoraLevel.LOW


def classify_recovery_time(recovery_hours: float | None) -> DoraLevel | None:
    """Classifica a mediana do tempo de recuperacao, recebida em horas."""

    if recovery_hours is None:
        return None
    value = _validate_nonnegative(recovery_hours, "recovery time")
    if value < 1:
        return DoraLevel.ELITE
    if value < 24:
        return DoraLevel.HIGH
    if value < 168:
        return DoraLevel.MEDIUM
    return DoraLevel.LOW


_DORA_SCORES = {
    DoraLevel.ELITE: 4,
    DoraLevel.HIGH: 3,
    DoraLevel.MEDIUM: 2,
    DoraLevel.LOW: 1,
}
_SCORES_TO_DORA = {score: level for level, score in _DORA_SCORES.items()}


def classify_overall_dora(
    deployment_frequency_level: DoraLevel | None,
    lead_time_level: DoraLevel | None,
    change_failure_rate_level: DoraLevel | None,
    recovery_time_level: DoraLevel | None,
) -> DoraLevel | None:
    """Classifica pela mediana das quatro notas, arredondada para baixo."""

    levels = [
        deployment_frequency_level,
        lead_time_level,
        change_failure_rate_level,
        recovery_time_level,
    ]
    if any(level is None for level in levels):
        return None
    try:
        scores = sorted(
            _DORA_SCORES[level] for level in levels if level is not None
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("categoria DORA invalida") from exc
    median_score = math.floor((scores[1] + scores[2]) / 2)
    return _SCORES_TO_DORA[median_score]


def _is_main_release_in_window(
    release: dict[str, Any], start_date: date, end_date: date
) -> bool:
    published_at = release.get("published_at")
    if release.get("draft") or release.get("prerelease") or not published_at:
        return False
    published_date = parse_github_datetime(published_at, "published_at").date()
    return start_date <= published_date <= end_date
