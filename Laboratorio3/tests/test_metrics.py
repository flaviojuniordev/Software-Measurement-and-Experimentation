from datetime import date

import pytest

from pipeline.metrics import (
    calculate_release_change_failure_rate,
    classify_corrective_release,
    deployment_frequency,
    is_patch_only_semver,
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


def corrective_release(tag, published_at, *, body=""):
    return {
        "tag_name": tag,
        "published_at": published_at,
        "draft": False,
        "prerelease": False,
        "body": body,
    }


def test_corrective_heuristic_accepts_only_patch_increment():
    assert is_patch_only_semver("v2.3.0", "2.3.1") is True
    assert is_patch_only_semver("2.3.0", "2.4.0") is False
    assert is_patch_only_semver("2.3.0", "3.0.0") is False


@pytest.mark.parametrize("keyword", ["FIX", "HotFix", "revert"])
def test_corrective_heuristic_is_case_insensitive_for_required_terms(keyword):
    previous = corrective_release("release-a", "2025-01-01T00:00:00Z")
    current = corrective_release(
        "release-b", "2025-01-02T00:00:00Z", body=f"{keyword}: regression"
    )

    assert classify_corrective_release(previous, current) is True
    current["body"] = "feature release"
    assert classify_corrective_release(previous, current, [f"{keyword} crash"]) is True


def test_release_cfr_counts_correction_at_exactly_seven_days():
    releases = [
        corrective_release("v1.0.0", "2024-12-20T00:00:00Z"),
        corrective_release("v1.1.0", "2025-01-01T00:00:00Z"),
        corrective_release("v1.1.1", "2025-01-08T00:00:00Z"),
    ]

    summary = calculate_release_change_failure_rate(
        releases, [], date(2025, 1, 1), date(2025, 1, 31)
    )

    assert summary.release_cfr_evaluated == 2
    assert summary.release_cfr_failed == 1
    assert summary.release_change_failure_rate == 0.5


def test_release_cfr_rejects_correction_after_seven_days():
    releases = [
        corrective_release("v1.0.0", "2025-01-01T00:00:00Z"),
        corrective_release("v1.0.1", "2025-01-08T00:00:01Z"),
    ]

    summary = calculate_release_change_failure_rate(
        releases, [], date(2025, 1, 1), date(2025, 1, 31)
    )

    assert summary.release_cfr_failed == 0
    assert summary.release_change_failure_rate == 0.0


def test_release_cfr_censors_last_seven_calendar_days():
    releases = [
        corrective_release("v1.0.0", "2025-01-24T12:00:00Z"),
        corrective_release("v1.0.1", "2025-01-25T00:00:00Z"),
        corrective_release("v1.0.2", "2025-01-31T23:59:59Z"),
    ]

    summary = calculate_release_change_failure_rate(
        releases, [], date(2025, 1, 1), date(2025, 1, 31)
    )

    assert summary.release_cfr_evaluated == 1
    assert summary.release_cfr_censored == 2
    assert summary.release_cfr_failed == 1


def test_release_cfr_is_none_without_evaluable_releases():
    releases = [corrective_release("v1.0.0", "2025-01-30T00:00:00Z")]

    summary = calculate_release_change_failure_rate(
        releases, [], date(2025, 1, 1), date(2025, 1, 31)
    )

    assert summary.as_dict() == {
        "release_change_failure_rate": None,
        "release_cfr_evaluated": 0,
        "release_cfr_failed": 0,
        "release_cfr_censored": 1,
    }


def test_release_cfr_uses_commit_messages_and_calculates_rate():
    releases = [
        corrective_release("build-a", "2025-01-01T00:00:00Z"),
        corrective_release("build-b", "2025-01-03T00:00:00Z"),
        corrective_release("build-c", "2025-01-20T00:00:00Z"),
        corrective_release("build-d", "2025-01-28T00:00:00Z"),
    ]
    comparisons = [
        {
            "head_tag": "build-b",
            "commits": [{"message": "fix production crash"}],
        }
    ]

    summary = calculate_release_change_failure_rate(
        releases, comparisons, date(2025, 1, 1), date(2025, 1, 31)
    )

    assert summary.release_cfr_evaluated == 3
    assert summary.release_cfr_failed == 1
    assert summary.release_cfr_censored == 1
    assert summary.release_change_failure_rate == pytest.approx(1 / 3)
