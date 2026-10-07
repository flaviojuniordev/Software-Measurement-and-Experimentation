"""Orquestracao do pipeline integrado da Sprint 1."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from .collectors import (
    collect_release_comparisons,
    collect_releases,
    collect_tags,
    collect_workflow_runs,
    collect_workflows,
    count_contributors,
    discover_repositories,
    main_releases_in_window,
    WorkflowRunWindowLimitError,
)
from .config import PipelineConfig
from .github_client import GitHubAPIError, GitHubClient
from .metrics import (
    DoraLevel,
    calculate_ci_change_failure_rate,
    classify_change_failure_rate,
    classify_deployment_frequency,
    classify_lead_time,
    classify_overall_dora,
    classify_recovery_time,
    count_valid_workflow_runs,
    deployment_frequency,
    find_failure_episodes,
    lead_time_summary,
    parse_github_datetime,
    summarize_recovery,
)
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

            selection["task1_included"] = True
            default_branch = repository.get("default_branch")
            if not isinstance(default_branch, str) or not default_branch:
                raise ValueError("repositorio sem default_branch")
            workflow_runs = collect_workflow_runs(
                client,
                full_name,
                default_branch=default_branch,
                start_date=config.start_date,
                end_date=config.end_date,
            )
            selection["workflow_runs_count"] = len(workflow_runs)
            selection["valid_workflow_runs_count"] = count_valid_workflow_runs(
                workflow_runs
            )
            if (
                selection["valid_workflow_runs_count"]
                < config.minimum_workflow_runs
            ):
                selection["discard_reason"] = "insufficient_workflow_runs"
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
            lead_time_values = lead_time_summary(comparisons)
            deployment_frequency_value = deployment_frequency(
                releases, config.start_date, config.end_date
            )
            cfr = calculate_ci_change_failure_rate(workflow_runs)
            recovery = summarize_recovery(find_failure_episodes(workflow_runs))
            deployment_level = classify_deployment_frequency(
                deployment_frequency_value
            )
            lead_time_level = classify_lead_time(
                lead_time_values["lead_time_release_median_hours"]
            )
            cfr_level = classify_change_failure_rate(cfr)
            recovery_level = classify_recovery_time(
                recovery.median_recovery_hours
            )
            overall_level = classify_overall_dora(
                deployment_level,
                lead_time_level,
                cfr_level,
                recovery_level,
            )
            row = {
                **selection,
                "tags_count": len(tags),
                "deployment_frequency_per_week": deployment_frequency_value,
                **lead_time_values,
                "compare_errors": sum(
                    bool(comparison.get("error")) for comparison in comparisons
                ),
                "ci_change_failure_rate": cfr,
                "failure_episodes_total": recovery.total_episodes,
                "failure_episodes_recovered": recovery.recovered_episodes,
                "failure_episodes_censored": recovery.censored_episodes,
                "censored_episodes_proportion": recovery.censored_proportion,
                "median_recovery_hours": recovery.median_recovery_hours,
                "deployment_frequency_dora": _level_value(deployment_level),
                "lead_time_dora": _level_value(lead_time_level),
                "change_failure_rate_dora": _level_value(cfr_level),
                "recovery_time_dora": _level_value(recovery_level),
                "overall_dora": _level_value(overall_level),
            }
            selection["s01_included"] = True
            row["s01_included"] = True
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
                    "workflow_runs": workflow_runs,
                },
            )
        except (
            GitHubAPIError,
            WorkflowRunWindowLimitError,
            ValueError,
            KeyError,
        ) as exc:
            selection["discard_reason"] = "collection_error"
            selection["collection_error"] = str(exc)
            selection_rows.append(selection)
            progress(f"  erro: {exc}")

        checkpoint(config.output_dir, selection_rows, repository_rows)

    return {
        "candidates": len(candidates),
        "processed": len(selection_rows),
        "included": len(repository_rows),
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
        "workflow_runs_count": 0,
        "valid_workflow_runs_count": 0,
        "task1_included": False,
        "s01_included": False,
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


def _level_value(level: DoraLevel | None) -> str | None:
    return level.value if level is not None else None
