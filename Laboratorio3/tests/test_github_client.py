import io
import json
from http.client import IncompleteRead
from urllib.error import HTTPError

from pipeline.github_client import GitHubClient, parse_link_header


class FakeRaw:
    def __init__(self, data, *, headers=None, status=200):
        self._body = json.dumps(data).encode("utf-8")
        self.headers = headers or {}
        self.status = status

    def read(self):
        return self._body


def test_parse_link_header():
    value = (
        '<https://api.github.com/items?page=2>; rel="next", '
        '<https://api.github.com/items?page=4>; rel="last"'
    )

    assert parse_link_header(value) == {
        "next": "https://api.github.com/items?page=2",
        "last": "https://api.github.com/items?page=4",
    }


def test_cache_prevents_repeated_network_calls(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeRaw([{"id": 1}], headers={"X-RateLimit-Remaining": "10"})

    client = GitHubClient("token", tmp_path, opener=opener)
    first = client.get("/items", {"per_page": 1})
    second = client.get("/items", {"per_page": 1})

    assert first.from_cache is False
    assert second.from_cache is True
    assert len(calls) == 1


def test_pagination_follows_next_link(tmp_path):
    def opener(request, timeout):
        if "page=2" in request.full_url:
            return FakeRaw([{"id": 2}])
        return FakeRaw(
            [{"id": 1}],
            headers={
                "Link": '<https://api.github.com/items?page=2>; rel="next"'
            },
        )

    client = GitHubClient("token", tmp_path, opener=opener)

    assert client.paginate("/items", {"per_page": 1}) == [{"id": 1}, {"id": 2}]


def test_retries_server_error_with_exponential_backoff(tmp_path):
    attempts = 0
    sleeps = []

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPError(
                request.full_url,
                503,
                "unavailable",
                {},
                io.BytesIO(b'{"message":"temporario"}'),
            )
        return FakeRaw({"ok": True})

    client = GitHubClient(
        "token", tmp_path, opener=opener, sleeper=sleeps.append, max_retries=2
    )

    assert client.get("/health").data == {"ok": True}
    assert attempts == 2
    assert sleeps == [1]


def test_retries_incomplete_read_without_caching_partial_response(tmp_path):
    attempts = 0
    sleeps = []

    class IncompleteRaw(FakeRaw):
        def read(self):
            raise IncompleteRead(b'{"partial":', 20)

    def opener(request, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return IncompleteRaw(None)
        return FakeRaw({"complete": True})

    client = GitHubClient(
        "token", tmp_path, opener=opener, sleeper=sleeps.append, max_retries=2
    )

    first = client.get("/large-response")
    second = client.get("/large-response")

    assert first.data == {"complete": True}
    assert second.from_cache is True
    assert attempts == 2
    assert sleeps == [1]
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_waits_on_next_request_when_rate_limit_reaches_zero(tmp_path):
    sleeps = []
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        headers = (
            {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "110"}
            if calls == 1
            else {}
        )
        return FakeRaw({"call": calls}, headers=headers)

    client = GitHubClient(
        "token", tmp_path, opener=opener, sleeper=sleeps.append, clock=lambda: 100
    )
    client.get("/first")
    client.get("/second")

    assert sleeps == [11]
