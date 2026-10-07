from datetime import date

from pipeline.collectors import (
    collect_release_comparisons,
    collect_releases,
    count_contributors,
    discover_repositories,
    main_releases_in_window,
)
from pipeline.github_client import GitHubResponse


class FakeClient:
    def __init__(self):
        self.responses = []
        self.paginated = []

    def get(self, path, params=None):
        return self.responses.pop(0)

    def iter_responses(self, path, params=None):
        yield from self.responses

    def paginate(self, path, params=None, *, item_key=None, limit=None):
        values = self.paginated.pop(0)
        return values if limit is None else values[:limit]


def make_release(tag, published_at, *, draft=False, prerelease=False):
    return {
        "tag_name": tag,
        "published_at": published_at,
        "draft": draft,
        "prerelease": prerelease,
    }


def test_discover_repositories_applies_limit():
    client = FakeClient()
    client.paginated = [[{"full_name": "a/one"}, {"full_name": "b/two"}]]

    result = discover_repositories(client, minimum_stars=1000, limit=1)

    assert result == [{"full_name": "a/one"}]


def test_count_contributors_uses_last_page():
    client = FakeClient()
    client.responses = [
        GitHubResponse(
            url="https://api.github.com/repos/a/b/contributors",
            status=200,
            headers={
                "link": (
                    '<https://api.github.com/repos/a/b/contributors?per_page=1&page=42>; '
                    'rel="last"'
                )
            },
            data=[{"login": "first"}],
        )
    ]

    assert count_contributors(client, "a/b") == 42


def test_collect_releases_keeps_window_and_one_previous_main_release():
    client = FakeClient()
    client.responses = [
        GitHubResponse(
            url="releases",
            status=200,
            headers={},
            data=[
                make_release("future", "2026-01-10T00:00:00Z"),
                make_release("v2", "2025-10-10T00:00:00Z"),
                make_release("rc", "2025-06-01T00:00:00Z", prerelease=True),
                make_release("v1", "2024-12-20T00:00:00Z"),
                make_release("older", "2024-01-01T00:00:00Z"),
            ],
        )
    ]

    releases = collect_releases(
        client,
        "a/b",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    assert [item["tag_name"] for item in releases] == ["v1", "rc", "v2"]
    assert [item["tag_name"] for item in main_releases_in_window(
        releases, date(2025, 1, 1), date(2025, 12, 31)
    )] == ["v2"]


def test_collect_release_comparisons_normalises_commits():
    client = FakeClient()
    client.paginated = [
        [
            {
                "sha": "abc",
                "commit": {
                    "author": {"date": "2025-02-01T00:00:00Z"},
                    "message": "feat: change",
                },
            }
        ]
    ]
    releases = [
        make_release("v1", "2024-12-20T00:00:00Z"),
        make_release("v2", "2025-02-10T00:00:00Z"),
    ]

    comparisons = collect_release_comparisons(
        client,
        "a/b",
        releases,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    assert comparisons == [
        {
            "base_tag": "v1",
            "head_tag": "v2",
            "release_published_at": "2025-02-10T00:00:00Z",
            "commits": [
                {
                    "sha": "abc",
                    "author_date": "2025-02-01T00:00:00Z",
                    "message": "feat: change",
                }
            ],
            "error": None,
        }
    ]
