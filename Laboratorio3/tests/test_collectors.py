from datetime import date

from pipeline.collectors import (
    collect_release_comparisons,
    collect_releases,
    count_contributors,
    discover_repositories,
    main_releases_in_window,
)
from pipeline.github_client import GitHubAPIError, GitHubResponse
from pipeline.git_metadata import GitCollectionError


class FakeClient:
    def __init__(self):
        self.responses = []
        self.paginated = []
        self.iterated = []

    def get(self, path, params=None):
        return self.responses.pop(0)

    def iter_responses(self, path, params=None):
        self.iterated.append((path, params))
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


def test_discover_repositories_removes_pagination_duplicates():
    client = FakeClient()
    client.paginated = [[
        {"full_name": "a/one"},
        {"full_name": "a/one"},
        {"full_name": "b/two"},
    ]]

    result = discover_repositories(client, minimum_stars=1000, limit=2)

    assert result == [{"full_name": "a/one"}, {"full_name": "b/two"}]


def test_discover_repositories_slices_search_after_first_thousand():
    class SearchClient:
        def __init__(self):
            self.calls = []

        def paginate(self, path, params, *, item_key=None, limit=None):
            self.calls.append(dict(params))
            if len(self.calls) == 1:
                return [
                    {"full_name": f"org/repo-{number}", "stargazers_count": 5000}
                    for number in range(1_000)
                ]
            return [
                {"full_name": f"next/repo-{number}", "stargazers_count": 4999}
                for number in range(10)
            ]

    client = SearchClient()
    result = discover_repositories(client, minimum_stars=1000, limit=1_010)

    assert len(result) == 1_010
    assert client.calls[1]["q"] == "stars:1001..5000"


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


def test_count_contributors_marks_oversized_history_as_unavailable():
    class OversizedHistoryClient:
        def get(self, path, params=None):
            raise GitHubAPIError(
                403,
                "https://api.github.com/repos/a/b/contributors",
                "The history or contributor list is too large to list contributors "
                "for this repository via the API.",
            )

    assert count_contributors(OversizedHistoryClient(), "a/b") is None


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

    assert client.iterated[0][1] == {"per_page": 30}
    assert [item["tag_name"] for item in releases] == ["v1", "rc", "v2"]
    assert [item["tag_name"] for item in main_releases_in_window(
        releases, date(2025, 1, 1), date(2025, 12, 31)
    )] == ["v2"]


def test_collect_releases_prefers_graphql_minimal_fields():
    class GraphQLClient:
        def graphql(self, query, variables):
            return GitHubResponse(
                url="graphql",
                status=200,
                headers={},
                data={
                    "repository": {
                        "releases": {
                            "nodes": [
                                {
                                    "tagName": "v2",
                                    "publishedAt": "2025-02-01T00:00:00Z",
                                    "isDraft": False,
                                    "isPrerelease": False,
                                    "description": "notes",
                                    "url": "https://github.com/a/b/releases/v2",
                                },
                                {
                                    "tagName": "v1",
                                    "publishedAt": "2024-12-01T00:00:00Z",
                                    "isDraft": False,
                                    "isPrerelease": False,
                                    "description": "old",
                                    "url": "https://github.com/a/b/releases/v1",
                                },
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                },
            )

    releases = collect_releases(
        GraphQLClient(),
        "a/b",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    assert [release["tag_name"] for release in releases] == ["v1", "v2"]
    assert releases[1]["body"] == "notes"


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


def test_collect_release_comparisons_falls_back_to_rest_when_git_fails():
    class BrokenGit:
        def commits_between(self, *_args):
            raise GitCollectionError("tag removida")

    client = FakeClient()
    client.paginated = [[{
        "sha": "abc",
        "commit": {"author": {"date": "2025-02-01T00:00:00Z"}, "message": "fix"},
    }]]
    releases = [
        make_release("v1", "2024-12-20T00:00:00Z"),
        make_release("v2", "2025-02-10T00:00:00Z"),
    ]

    result = collect_release_comparisons(
        client,
        "a/b",
        releases,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        git_collector=BrokenGit(),
    )

    assert result[0]["commits"][0]["sha"] == "abc"
    assert result[0]["error"] is None


def test_collect_release_comparisons_prepares_all_main_tags_once():
    class PreparedGit:
        prepared = None

        def prepare_tags(self, full_name, tag_names):
            self.prepared = (full_name, tag_names)

        def commits_between(self, *_args):
            return []

    git_collector = PreparedGit()
    releases = [
        make_release("v1", "2024-12-20T00:00:00Z"),
        make_release("v2", "2025-02-10T00:00:00Z"),
        make_release("v3", "2025-03-10T00:00:00Z"),
    ]

    result = collect_release_comparisons(
        FakeClient(),
        "a/b",
        releases,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        git_collector=git_collector,
    )

    assert git_collector.prepared == ("a/b", ["v1", "v2", "v3"])
    assert len(result) == 2
