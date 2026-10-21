import pandas as pd

from analysis.analyze_lab03 import cliffs_delta, descriptive_statistics


def test_cliffs_delta_reports_direction_and_magnitude():
    assert cliffs_delta([3, 4, 5], [0, 1, 2]) == 1.0
    assert cliffs_delta([0, 1, 2], [3, 4, 5]) == -1.0


def test_descriptive_statistics_uses_median_and_iqr():
    frame = pd.DataFrame(
        {
            column: [1.0, 2.0, 3.0, 100.0]
            for column in (
                "deployment_frequency_per_week",
                "lead_time_release_median_hours",
                "lead_time_commit_median_hours",
                "ci_change_failure_rate",
                "release_change_failure_rate",
                "median_recovery_hours",
                "censored_episodes_proportion",
            )
        }
    )

    result = descriptive_statistics(frame)

    assert set(result["median"]) == {2.5}
    assert set(result["n"]) == {4}
    assert set(result["missing"]) == {0}
