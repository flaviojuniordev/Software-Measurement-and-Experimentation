from datetime import date

import pytest

from pipeline.metrics import (
    deployment_frequency,
    lead_time_summary,
    lead_time_values,
    parse_github_datetime,
)


def release(published_at, *, draft=False, prerelease=False):
    return {
        "published_at": published_at,
        "draft": draft,
        "prerelease": prerelease,
    }


def test_parse_github_datetime_normalises_utc():
    assert parse_github_datetime("2025-01-01T10:00:00Z").isoformat() == (
        "2025-01-01T10:00:00+00:00"
    )


def test_deployment_frequency_uses_only_main_releases_in_window():
    releases = [
        release("2025-01-10T00:00:00Z"),
        release("2025-06-10T00:00:00Z"),
        release("2025-08-10T00:00:00Z", prerelease=True),
        release("2024-12-31T00:00:00Z"),
        release(None),
    ]

    value = deployment_frequency(releases, date(2025, 1, 1), date(2025, 12, 31))

    assert value == pytest.approx(2 / (365 / 7))


def test_deployment_frequency_rejects_inverted_window():
    with pytest.raises(ValueError, match="start_date"):
        deployment_frequency([], date(2025, 2, 1), date(2025, 1, 1))


def test_lead_time_has_release_and_commit_variants():
    comparisons = [
        {
            "release_published_at": "2025-03-15T00:00:00Z",
            "commits": [
                {"author_date": "2025-03-02T00:00:00Z"},
                {"author_date": "2025-03-10T00:00:00Z"},
                {"author_date": "2025-03-14T00:00:00Z"},
            ],
        }
    ]

    per_release, per_commit = lead_time_values(comparisons)
    summary = lead_time_summary(comparisons)

    assert per_release == [13 * 24]
    assert per_commit == [13 * 24, 5 * 24, 24]
    assert summary["lead_time_release_median_hours"] == 13 * 24
    assert summary["lead_time_commit_median_hours"] == 5 * 24
    assert summary["lead_time_release_observations"] == 1
    assert summary["lead_time_commit_observations"] == 3


def test_lead_time_ignores_release_without_commits_or_dates():
    comparisons = [
        {"release_published_at": "2025-03-15T00:00:00Z", "commits": []},
        {
            "release_published_at": "2025-03-15T00:00:00Z",
            "commits": [{"author_date": None}],
        },
        {"release_published_at": None, "commits": [{"author_date": "2025-01-01"}]},
    ]

    assert lead_time_values(comparisons) == ([], [])
    assert lead_time_summary(comparisons) == {
        "lead_time_release_median_hours": None,
        "lead_time_commit_median_hours": None,
        "lead_time_release_observations": 0,
        "lead_time_commit_observations": 0,
    }
