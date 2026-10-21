import csv
import json
from datetime import date

import pytest

from pipeline.metrics import CorrectiveReleaseHeuristic
from pipeline.validation import (
    ValidationError,
    build_consensus_files,
    calculate_agreement_files,
    categorical_agreement,
    classification_metrics,
    evaluate_heuristic_from_consensus,
    hydrate_gold_sample_payloads,
    prepare_gold_sample,
    sample_repository_releases,
    select_gold_repositories,
)


def release(number, day):
    return {
        "tag_name": f"v1.0.{number}",
        "published_at": f"2025-01-{day:02d}T00:00:00Z",
        "html_url": f"https://github.com/org/repo/releases/tag/v1.0.{number}",
        "draft": False,
        "prerelease": False,
        "body": "",
    }


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_raw(path, repository, releases):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "repository": {"full_name": repository},
                "releases": releases,
                "comparisons": [],
            }
        ),
        encoding="utf-8",
    )


def test_release_sample_is_reproducible_and_has_five_items():
    releases = [release(number, number + 1) for number in range(8)]

    first = sample_repository_releases(
        "org/repo",
        releases,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        random_state=42,
    )
    second = sample_repository_releases(
        "org/repo",
        list(reversed(releases)),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        random_state=42,
    )

    assert [item["tag_name"] for item in first] == [
        item["tag_name"] for item in second
    ]
    assert len(first) == 5


def test_final_gold_sample_requires_at_least_sixty_repositories():
    rows = [{"full_name": f"org/repo-{number}"} for number in range(59)]

    with pytest.raises(ValidationError, match="modo final exige 60"):
        select_gold_repositories(rows, allow_partial=False)


def test_final_gold_sample_selects_exactly_sixty_reproducibly():
    rows = [{"full_name": f"org/repo-{number}"} for number in range(80)]

    first = select_gold_repositories(rows, allow_partial=False, random_state=42)
    second = select_gold_repositories(
        list(reversed(rows)), allow_partial=False, random_state=42
    )

    assert first == second
    assert len(first) == 60


def test_partial_templates_have_blank_human_labels_and_no_heuristic(tmp_path):
    dataset = tmp_path / "repositories.csv"
    raw_dir = tmp_path / "raw"
    rows = [{"full_name": "org/repo"}]
    write_csv(dataset, rows, ["full_name"])
    write_raw(
        raw_dir / "org__repo.json",
        "org/repo",
        [release(number, number + 1) for number in range(6)],
    )

    (
        flavio_repository_path,
        flavio_release_path,
        luidi_repository_path,
        luidi_release_path,
    ) = prepare_gold_sample(
        dataset,
        raw_dir,
        tmp_path / "validation",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        allow_partial=True,
    )

    assert flavio_repository_path.name == "flavio_repositories_partial.csv"
    assert flavio_release_path.name == "flavio_releases_partial.csv"
    assert luidi_repository_path.name == "luidi_repositories_partial.csv"
    assert luidi_release_path.name == "luidi_releases_partial.csv"
    with flavio_release_path.open(encoding="utf-8", newline="") as handle:
        release_rows = list(csv.DictReader(handle))
    assert len(release_rows) == 5
    assert all(row["is_corrective_manual"] == "" for row in release_rows)
    assert all("heuristic" not in row for row in release_rows)


def test_hydration_collects_only_selected_release_comparisons(tmp_path, monkeypatch):
    dataset = tmp_path / "repositories.csv"
    raw_dir = tmp_path / "raw"
    repositories = [f"org/repo-{number}" for number in range(60)]
    write_csv(
        dataset,
        [{"full_name": repository} for repository in repositories],
        ["full_name"],
    )
    releases = [release(number, number + 1) for number in range(6)]

    monkeypatch.setattr(
        "pipeline.validation.collect_releases",
        lambda *_args, **_kwargs: releases,
    )

    def collect_comparisons(_client, _repository, pair, **_kwargs):
        previous, current = pair
        return [
            {
                "base_tag": previous["tag_name"],
                "head_tag": current["tag_name"],
                "release_published_at": current["published_at"],
                "commits": [],
                "error": None,
            }
        ]

    monkeypatch.setattr(
        "pipeline.validation.collect_release_comparisons", collect_comparisons
    )

    result = hydrate_gold_sample_payloads(
        dataset,
        raw_dir,
        object(),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        progress=lambda _message: None,
    )

    assert result == {"repositories": 60, "hydrated": 60, "reused": 0}
    payload = json.loads(
        (raw_dir / "org__repo-0.json").read_text(encoding="utf-8")
    )
    assert len(payload["releases"]) == 6
    assert 4 <= len(payload["comparisons"]) <= 5


def test_classification_metrics_calculates_precision_recall_f1_and_matrix():
    result = classification_metrics(
        [True, True, False, False],
        [True, False, True, False],
    )

    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["confusion_matrix"] == {
        "true_positive": 1,
        "false_positive": 1,
        "true_negative": 1,
        "false_negative": 1,
    }


def test_categorical_agreement_reports_cohen_and_fleiss_kappa():
    result = categorical_agreement(
        ["sim", "sim", "nao", "nao"],
        ["sim", "nao", "sim", "nao"],
        ["sim", "nao"],
    )

    assert result["observed_agreement"] == 0.5
    assert result["cohen_kappa"] == 0.0
    assert result["fleiss_kappa"] == 0.0


def test_agreement_requires_filled_independent_labels_and_writes_pending(tmp_path):
    repo_fields = ["repository", "project_type", "releases_are_deliveries"]
    release_fields = ["repository", "release_tag", "is_corrective_manual"]
    flavio_repos = tmp_path / "flavio-repos.csv"
    luidi_repos = tmp_path / "luidi-repos.csv"
    flavio_releases = tmp_path / "flavio-releases.csv"
    luidi_releases = tmp_path / "luidi-releases.csv"
    write_csv(
        flavio_repos,
        [{"repository": "org/repo", "project_type": "outro", "releases_are_deliveries": "sim"}],
        repo_fields,
    )
    write_csv(
        luidi_repos,
        [{"repository": "org/repo", "project_type": "ferramenta CLI", "releases_are_deliveries": "sim"}],
        repo_fields,
    )
    write_csv(
        flavio_releases,
        [{"repository": "org/repo", "release_tag": "v1", "is_corrective_manual": "sim"}],
        release_fields,
    )
    write_csv(
        luidi_releases,
        [{"repository": "org/repo", "release_tag": "v1", "is_corrective_manual": "nao"}],
        release_fields,
    )

    report = calculate_agreement_files(
        flavio_repos,
        flavio_releases,
        luidi_repos,
        luidi_releases,
        tmp_path / "agreement",
    )

    assert report["majority_resolution"] is False
    pending = (tmp_path / "agreement" / "pending_releases.csv").read_text(
        encoding="utf-8"
    )
    assert "org/repo,v1,sim,nao," in pending


def test_consensus_does_not_resolve_two_rater_divergence_automatically(tmp_path):
    repo_fields = ["repository", "project_type", "releases_are_deliveries"]
    release_fields = ["repository", "release_tag", "is_corrective_manual"]
    files = {
        name: tmp_path / f"{name}.csv"
        for name in ("flavio_repos", "luidi_repos", "flavio_releases", "luidi_releases")
    }
    write_csv(
        files["flavio_repos"],
        [{"repository": "org/repo", "project_type": "outro", "releases_are_deliveries": "sim"}],
        repo_fields,
    )
    write_csv(
        files["luidi_repos"],
        [{"repository": "org/repo", "project_type": "ferramenta CLI", "releases_are_deliveries": "sim"}],
        repo_fields,
    )
    for name in ("flavio_releases", "luidi_releases"):
        write_csv(
            files[name],
            [{"repository": "org/repo", "release_tag": "v1", "is_corrective_manual": "nao"}],
            release_fields,
        )
    repository_resolutions = tmp_path / "pending-repos.csv"
    release_resolutions = tmp_path / "pending-releases.csv"
    write_csv(
        repository_resolutions,
        [{"repository": "org/repo", "consensus_project_type": "", "consensus_releases_are_deliveries": ""}],
        ["repository", "consensus_project_type", "consensus_releases_are_deliveries"],
    )
    write_csv(
        release_resolutions,
        [],
        ["repository", "release_tag", "consensus_is_corrective"],
    )

    with pytest.raises(ValidationError, match="consenso humano pendente"):
        build_consensus_files(
            files["flavio_repos"],
            files["flavio_releases"],
            files["luidi_repos"],
            files["luidi_releases"],
            repository_resolutions,
            release_resolutions,
            tmp_path / "consensus",
        )


def test_evaluation_preserves_previous_versions(tmp_path):
    consensus = tmp_path / "consensus.csv"
    raw_dir = tmp_path / "raw"
    history = tmp_path / "history.json"
    write_csv(
        consensus,
        [{"repository": "org/repo", "release_tag": "v1.0.1", "is_corrective_consensus": "sim"}],
        ["repository", "release_tag", "is_corrective_consensus"],
    )
    write_raw(
        raw_dir / "org__repo.json",
        "org/repo",
        [release(0, 1), release(1, 2)],
    )

    result = evaluate_heuristic_from_consensus(
        consensus,
        raw_dir,
        history,
        heuristic=CorrectiveReleaseHeuristic(version="v1"),
    )

    assert result["f1"] == 1.0
    with pytest.raises(ValidationError, match="ja existe"):
        evaluate_heuristic_from_consensus(
            consensus,
            raw_dir,
            history,
            heuristic=CorrectiveReleaseHeuristic(version="v1"),
        )
    stored = json.loads(history.read_text(encoding="utf-8"))
    assert len(stored["evaluations"]) == 1
