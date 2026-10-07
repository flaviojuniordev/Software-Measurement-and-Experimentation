from pipeline.output import build_funnel


def test_build_funnel_counts_stages_and_reasons():
    rows = [
        {
            "workflows_count": 2,
            "task1_included": True,
            "discard_reason": None,
        },
        {
            "workflows_count": 0,
            "task1_included": False,
            "discard_reason": "no_github_actions",
        },
        {
            "workflows_count": 1,
            "task1_included": False,
            "discard_reason": "insufficient_releases",
        },
    ]

    result = build_funnel(rows)

    assert result["stages"] == [
        {"stage": "candidates_processed", "count": 3},
        {"stage": "with_github_actions", "count": 2},
        {"stage": "with_minimum_releases", "count": 1},
        {"stage": "ready_for_task2", "count": 1},
    ]
    assert result["discard_reasons"] == {
        "insufficient_releases": 1,
        "no_github_actions": 1,
    }
