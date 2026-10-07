"""Orquestracao da parte de coleta atribuida ao Flavio."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from .collectors import (
    collect_release_comparisons,
    collect_releases,
    collect_tags,
    collect_workflows,
    count_contributors,
    discover_repositories,
    main_releases_in_window,
)
from .config import PipelineConfig
from .github_client import GitHubAPIError, GitHubClient
from .metrics import deployment_frequency, lead_time_summary, parse_github_datetime
from .output import checkpoint, save_repository_payload


def run_pipeline(
    config: PipelineConfig,
    client: GitHubClient,
    *,
    progress: Callable[[str], None] = print,
) -> dict[str, int]:
    candidates = discover_repositories(
        client,
        minimum_stars=config.minimum_stars,
        limit=config.candidate_limit,
    )
    selection_rows: list[dict[str, Any]] = []
    repository_rows: list[dict[str, Any]] = []

    for position, repository in enumerate(candidates, start=1):
        full_name = repository["full_name"]
        progress(f"[{position}/{len(candidates)}] {full_name}")
        selection = _base_selection(repository, config.end_date)

        try:
            workflows = collect_workflows(client, full_name)
            selection["workflows_count"] = len(workflows)
            if not workflows:
                selection["discard_reason"] = "no_github_actions"
                selection_rows.append(selection)
                checkpoint(config.output_dir, selection_rows, repository_rows)
                continue

            selection["contributors_count"] = count_contributors(client, full_name)
            releases = collect_releases(
                client,
                full_name,
                start_date=config.start_date,
                end_date=config.end_date,
            )
            releases_in_window = main_releases_in_window(
                releases, config.start_date, config.end_date
            )
            selection["releases_in_window"] = len(releases_in_window)
            if len(releases_in_window) < config.minimum_releases:
                selection["discard_reason"] = "insufficient_releases"
                selection_rows.append(selection)
                checkpoint(config.output_dir, selection_rows, repository_rows)
                continue

            tags = collect_tags(client, full_name) if config.collect_tags else []
            comparisons = collect_release_comparisons(
                client,
                full_name,
                releases,
                start_date=config.start_date,
                end_date=config.end_date,
            )
            metric_values = lead_time_summary(comparisons)
            row = {
                **selection,
                "tags_count": len(tags),
                "deployment_frequency_per_week": deployment_frequency(
                    releases, config.start_date, config.end_date
                ),
                **metric_values,
                "compare_errors": sum(
                    bool(comparison.get("error")) for comparison in comparisons
                ),
            }
            selection["task1_included"] = True
            row["task1_included"] = True
            repository_rows.append(row)
            selection_rows.append(selection)
            save_repository_payload(
                config.output_dir,
                full_name,
                {
                    "repository": _repository_metadata(repository),
                    "workflows": workflows,
                    "releases": releases,
                    "tags": tags,
                    "comparisons": comparisons,
                },
            )
        except (GitHubAPIError, ValueError, KeyError) as exc:
            selection["discard_reason"] = "collection_error"
            selection["collection_error"] = str(exc)
            selection_rows.append(selection)
            progress(f"  erro: {exc}")

        checkpoint(config.output_dir, selection_rows, repository_rows)

    return {
        "candidates": len(candidates),
        "processed": len(selection_rows),
        "ready_for_task2": len(repository_rows),
    }


def _base_selection(repository: dict[str, Any], window_end: date) -> dict[str, Any]:
    created_at = repository.get("created_at")
    age_days = (
        (window_end - parse_github_datetime(created_at).date()).days
        if created_at
        else None
    )
    return {
        "full_name": repository.get("full_name"),
        "stars": repository.get("stargazers_count"),
        "language": repository.get("language"),
        "created_at": created_at,
        "age_days_at_window_end": age_days,
        "default_branch": repository.get("default_branch"),
        "contributors_count": None,
        "workflows_count": 0,
        "releases_in_window": 0,
        "task1_included": False,
        "discard_reason": None,
        "collection_error": None,
    }


def _repository_metadata(repository: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id",
        "full_name",
        "html_url",
        "stargazers_count",
        "language",
        "created_at",
        "updated_at",
        "default_branch",
        "archived",
        "fork",
    )
    return {field: repository.get(field) for field in fields}
