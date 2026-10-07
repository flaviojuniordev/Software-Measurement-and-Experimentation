import csv
import json
from datetime import date

from pipeline.config import PipelineConfig
from pipeline.runner import run_pipeline


def make_release(tag, published_at):
    return {
        "tag_name": tag,
        "published_at": published_at,
        "draft": False,
        "prerelease": False,
    }


def test_runner_integrates_funnel_metrics_and_checkpoints(tmp_path, monkeypatch):
    candidates = [
        {
            "full_name": "org/included",
            "stargazers_count": 5000,
            "language": "Python",
            "created_at": "2020-01-01T00:00:00Z",
            "default_branch": "main",
        },
        {
            "full_name": "org/no-actions",
            "stargazers_count": 4000,
            "language": "Go",
            "created_at": "2021-01-01T00:00:00Z",
            "default_branch": "main",
        },
    ]
    releases = [make_release("v0", "2024-12-20T00:00:00Z")] + [
        make_release(f"v{number}", f"2025-0{number}-10T00:00:00Z")
        for number in range(1, 6)
    ]

    monkeypatch.setattr(
        "pipeline.runner.discover_repositories", lambda *args, **kwargs: candidates
    )
    monkeypatch.setattr(
        "pipeline.runner.collect_workflows",
        lambda client, full_name: [{"id": 1}]
        if full_name == "org/included"
        else [],
    )
    monkeypatch.setattr(
        "pipeline.runner.count_contributors", lambda *args, **kwargs: 12
    )
    monkeypatch.setattr(
        "pipeline.runner.collect_releases", lambda *args, **kwargs: releases
    )
    monkeypatch.setattr(
        "pipeline.runner.collect_tags", lambda *args, **kwargs: [{"name": "v1"}]
    )
    monkeypatch.setattr(
        "pipeline.runner.collect_release_comparisons",
        lambda *args, **kwargs: [
            {
                "release_published_at": "2025-01-10T00:00:00Z",
                "commits": [{"author_date": "2025-01-09T00:00:00Z"}],
                "error": None,
            }
        ],
    )
    monkeypatch.setattr(
        "pipeline.runner.collect_workflow_runs",
        lambda *args, **kwargs: [
            {
                "id": number,
                "workflow_id": 10,
                "event": "push",
                "head_branch": "main",
                "conclusion": "success",
                "run_started_at": f"2025-06-{(number % 28) + 1:02d}T10:00:00Z",
                "updated_at": f"2025-06-{(number % 28) + 1:02d}T10:05:00Z",
            }
            for number in range(50)
        ],
    )

    config = PipelineConfig(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        candidate_limit=2,
        cache_dir=tmp_path / "cache",
        output_dir=tmp_path / "data",
    )
    messages = []
    summary = run_pipeline(config, object(), progress=messages.append)

    assert summary == {"candidates": 2, "processed": 2, "included": 1}
    assert len(messages) == 2

    with (config.output_dir / "repositories_s01.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        repository_rows = list(csv.DictReader(handle))
    assert len(repository_rows) == 1
    assert repository_rows[0]["full_name"] == "org/included"
    assert float(repository_rows[0]["lead_time_release_median_hours"]) == 24
    assert float(repository_rows[0]["ci_change_failure_rate"]) == 0
    assert int(repository_rows[0]["valid_workflow_runs_count"]) == 50

    funnel = json.loads(
        (config.output_dir / "selection_funnel.json").read_text(encoding="utf-8")
    )
    assert funnel["discard_reasons"] == {"no_github_actions": 1}
    assert (config.output_dir / "raw" / "org__included.json").exists()


def test_runner_discards_repository_below_minimum_valid_runs(tmp_path, monkeypatch):
    candidate = {
        "full_name": "org/few-runs",
        "stargazers_count": 5000,
        "language": "Python",
        "created_at": "2020-01-01T00:00:00Z",
        "default_branch": "main",
    }
    releases = [make_release("v0", "2024-12-20T00:00:00Z")] + [
        make_release(f"v{number}", f"2025-0{number}-10T00:00:00Z")
        for number in range(1, 6)
    ]
    monkeypatch.setattr(
        "pipeline.runner.discover_repositories",
        lambda *args, **kwargs: [candidate],
    )
    monkeypatch.setattr(
        "pipeline.runner.collect_workflows", lambda *args, **kwargs: [{"id": 1}]
    )
    monkeypatch.setattr(
        "pipeline.runner.count_contributors", lambda *args, **kwargs: 3
    )
    monkeypatch.setattr(
        "pipeline.runner.collect_releases", lambda *args, **kwargs: releases
    )
    monkeypatch.setattr(
        "pipeline.runner.collect_workflow_runs",
        lambda *args, **kwargs: [
            {"id": number, "conclusion": "success"} for number in range(49)
        ],
    )
    config = PipelineConfig(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        candidate_limit=1,
        cache_dir=tmp_path / "cache",
        output_dir=tmp_path / "data",
    )

    summary = run_pipeline(config, object(), progress=lambda _message: None)

    assert summary == {"candidates": 1, "processed": 1, "included": 0}
    with (config.output_dir / "selection_funnel.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["discard_reason"] == "insufficient_workflow_runs"
    assert rows[0]["valid_workflow_runs_count"] == "49"
