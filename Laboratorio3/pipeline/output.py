"""Persistencia atomica dos artefatos derivados da coleta."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence


SELECTION_FIELDS = [
    "full_name",
    "stars",
    "language",
    "created_at",
    "age_days_at_window_end",
    "default_branch",
    "contributors_count",
    "workflows_count",
    "releases_in_window",
    "workflow_runs_count",
    "valid_workflow_runs_count",
    "task1_included",
    "s01_included",
    "discard_reason",
    "collection_error",
]

REPOSITORY_FIELDS = [
    "full_name",
    "stars",
    "language",
    "created_at",
    "age_days_at_window_end",
    "default_branch",
    "contributors_count",
    "workflows_count",
    "releases_in_window",
    "workflow_runs_count",
    "valid_workflow_runs_count",
    "tags_count",
    "deployment_frequency_per_week",
    "lead_time_release_median_hours",
    "lead_time_commit_median_hours",
    "lead_time_release_observations",
    "lead_time_commit_observations",
    "compare_errors",
    "ci_change_failure_rate",
    "failure_episodes_total",
    "failure_episodes_recovered",
    "failure_episodes_censored",
    "censored_episodes_proportion",
    "median_recovery_hours",
    "deployment_frequency_dora",
    "lead_time_dora",
    "change_failure_rate_dora",
    "recovery_time_dora",
    "overall_dora",
]


def checkpoint(
    output_dir: Path,
    selection_rows: Sequence[dict[str, Any]],
    repository_rows: Sequence[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "selection_funnel.csv", selection_rows, SELECTION_FIELDS)
    write_csv(
        output_dir / "repositories_s01.csv", repository_rows, REPOSITORY_FIELDS
    )
    funnel = build_funnel(selection_rows)
    write_json(output_dir / "selection_funnel.json", funnel)
    write_csv(
        output_dir / "selection_funnel_summary.csv",
        funnel["stages"],
        ["stage", "count"],
    )


def save_repository_payload(
    output_dir: Path, full_name: str, payload: dict[str, Any]
) -> None:
    safe_name = full_name.replace("/", "__")
    write_json(output_dir / "raw" / f"{safe_name}.json", payload)


def build_funnel(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    reasons = Counter(
        str(row.get("discard_reason"))
        for row in rows
        if row.get("discard_reason")
    )
    stages = [
        {"stage": "candidates_processed", "count": len(rows)},
        {
            "stage": "with_github_actions",
            "count": sum(int(row.get("workflows_count") or 0) > 0 for row in rows),
        },
        {
            "stage": "with_minimum_releases",
            "count": sum(bool(row.get("task1_included")) for row in rows),
        },
        {
            "stage": "with_minimum_workflow_runs",
            "count": sum(bool(row.get("s01_included")) for row in rows),
        },
        {
            "stage": "included_s01",
            "count": sum(bool(row.get("s01_included")) for row in rows),
        },
    ]
    return {"stages": stages, "discard_reasons": dict(sorted(reasons.items()))}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def write_csv(
    path: Path, rows: Iterable[dict[str, Any]], fieldnames: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
