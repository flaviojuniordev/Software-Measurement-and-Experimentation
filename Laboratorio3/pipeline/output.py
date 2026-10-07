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
    "task1_included",
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
    "tags_count",
    "deployment_frequency_per_week",
    "lead_time_release_median_hours",
    "lead_time_commit_median_hours",
    "lead_time_release_observations",
    "lead_time_commit_observations",
    "compare_errors",
]


def checkpoint(
    output_dir: Path,
    selection_rows: Sequence[dict[str, Any]],
    repository_rows: Sequence[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "selection_funnel.csv", selection_rows, SELECTION_FIELDS)
    write_csv(
        output_dir / "repositories_task1.csv", repository_rows, REPOSITORY_FIELDS
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
            "stage": "ready_for_task2",
            "count": sum(bool(row.get("task1_included")) for row in rows),
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
