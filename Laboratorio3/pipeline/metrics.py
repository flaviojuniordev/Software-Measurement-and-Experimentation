"""Calculos das metricas de velocidade sob responsabilidade da Task 1."""

from __future__ import annotations

from datetime import date, datetime, timezone
from statistics import median
from typing import Any, Iterable


def parse_github_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
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

        release_date = parse_github_datetime(published_at)
        commit_dates = [
            parse_github_datetime(commit["author_date"])
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


def _is_main_release_in_window(
    release: dict[str, Any], start_date: date, end_date: date
) -> bool:
    published_at = release.get("published_at")
    if release.get("draft") or release.get("prerelease") or not published_at:
        return False
    published_date = parse_github_datetime(published_at).date()
    return start_date <= published_date <= end_date
