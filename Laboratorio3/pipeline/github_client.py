"""Cliente REST do GitHub com cache, paginacao e resiliencia."""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import time
from dataclasses import dataclass
from http.client import IncompleteRead
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPSHandler, Request, build_opener

import certifi


JsonValue = Any


class GitHubAPIError(RuntimeError):
    """Erro permanente retornado pela API do GitHub."""

    def __init__(self, status: int | None, url: str, message: str) -> None:
        super().__init__(f"GitHub API ({status or 'rede'}) em {url}: {message}")
        self.status = status
        self.url = url


@dataclass(frozen=True)
class GitHubResponse:
    url: str
    status: int
    headers: dict[str, str]
    data: JsonValue
    from_cache: bool = False


def parse_link_header(value: str | None) -> dict[str, str]:
    links: dict[str, str] = {}
    if not value:
        return links
    for part in value.split(","):
        sections = [section.strip() for section in part.split(";")]
        if not sections or not sections[0].startswith("<"):
            continue
        url = sections[0].strip("<>")
        for section in sections[1:]:
            if section.startswith("rel="):
                links[section.removeprefix("rel=").strip('"')] = url
    return links


class GitHubClient:
    """Cliente pequeno e testavel, sem bibliotecas prontas do GitHub."""

    api_url = "https://api.github.com"

    def __init__(
        self,
        token: str | None,
        cache_dir: str | Path,
        *,
        max_retries: int = 5,
        timeout_seconds: int = 30,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.token = token
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        if opener is None:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self._opener = build_opener(HTTPSHandler(context=ssl_context)).open
        else:
            self._opener = opener
        self._sleep = sleeper
        self._clock = clock
        self._blocked_until = 0.0

    @classmethod
    def from_environment(
        cls,
        cache_dir: str | Path,
        *,
        max_retries: int = 5,
        timeout_seconds: int = 30,
    ) -> "GitHubClient":
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise RuntimeError(
                "Defina GITHUB_TOKEN antes de executar a coleta. "
                "O token nunca deve ser salvo no repositorio."
            )
        return cls(
            token,
            cache_dir,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

    def get(
        self,
        path_or_url: str,
        params: Mapping[str, Any] | None = None,
    ) -> GitHubResponse:
        url = self._build_url(path_or_url, params)
        cached = self._read_cache(url)
        if cached is not None:
            return cached

        last_error = "falha desconhecida"
        for attempt in range(self.max_retries + 1):
            self._wait_if_needed()
            try:
                response = self._request(url)
            except HTTPError as exc:
                headers = _normalise_headers(exc.headers)
                body = exc.read().decode("utf-8", errors="replace")
                last_error = _api_message(body) or str(exc)
                if self._is_retryable(exc.code, headers) and attempt < self.max_retries:
                    self._wait_before_retry(attempt, headers)
                    continue
                raise GitHubAPIError(exc.code, url, last_error) from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    self._sleep(2**attempt)
                    continue
                raise GitHubAPIError(None, url, last_error) from exc

            self._observe_rate_limit(response.headers)
            self._write_cache(response)
            return response

        raise GitHubAPIError(None, url, last_error)

    def iter_responses(
        self,
        path_or_url: str,
        params: Mapping[str, Any] | None = None,
    ) -> Iterator[GitHubResponse]:
        current: str | None = path_or_url
        current_params = params
        while current:
            response = self.get(current, current_params)
            yield response
            current = parse_link_header(response.headers.get("link")).get("next")
            current_params = None

    def paginate(
        self,
        path_or_url: str,
        params: Mapping[str, Any] | None = None,
        *,
        item_key: str | None = None,
        limit: int | None = None,
    ) -> list[JsonValue]:
        items: list[JsonValue] = []
        for response in self.iter_responses(path_or_url, params):
            page = response.data.get(item_key, []) if item_key else response.data
            if not isinstance(page, list):
                raise GitHubAPIError(
                    response.status,
                    response.url,
                    "resposta paginada nao contem uma lista",
                )
            remaining = None if limit is None else max(limit - len(items), 0)
            items.extend(page if remaining is None else page[:remaining])
            if limit is not None and len(items) >= limit:
                break
        return items

    def _request(self, url: str) -> GitHubResponse:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lab03-dora-miner",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers, method="GET")
        raw = self._opener(request, timeout=self.timeout_seconds)
        try:
            try:
                body = raw.read().decode("utf-8")
            except IncompleteRead as exc:
                raise URLError("resposta HTTP incompleta durante leitura") from exc
            data = json.loads(body) if body else None
            return GitHubResponse(
                url=url,
                status=getattr(raw, "status", 200),
                headers=_normalise_headers(getattr(raw, "headers", {})),
                data=data,
            )
        finally:
            close = getattr(raw, "close", None)
            if close:
                close()

    def _build_url(
        self, path_or_url: str, params: Mapping[str, Any] | None
    ) -> str:
        url = (
            path_or_url
            if path_or_url.startswith(("http://", "https://"))
            else f"{self.api_url}/{path_or_url.lstrip('/')}"
        )
        if not params:
            return url
        split = urlsplit(url)
        query = parse_qsl(split.query, keep_blank_values=True)
        query.extend(
            (
                key,
                str(value).lower() if isinstance(value, bool) else str(value),
            )
            for key, value in params.items()
        )
        return urlunsplit(
            (split.scheme, split.netloc, split.path, urlencode(query), split.fragment)
        )

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, url: str) -> GitHubResponse | None:
        path = self._cache_path(url)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return GitHubResponse(
                url=raw["url"],
                status=int(raw["status"]),
                headers=dict(raw.get("headers", {})),
                data=raw.get("data"),
                from_cache=True,
            )
        except (OSError, ValueError, KeyError, TypeError):
            path.unlink(missing_ok=True)
            return None

    def _write_cache(self, response: GitHubResponse) -> None:
        path = self._cache_path(response.url)
        temporary = path.with_suffix(".tmp")
        payload = {
            "url": response.url,
            "status": response.status,
            "headers": response.headers,
            "data": response.data,
        }
        temporary.write_text(
            json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(path)

    def _observe_rate_limit(self, headers: Mapping[str, str]) -> None:
        if headers.get("x-ratelimit-remaining") != "0":
            return
        try:
            self._blocked_until = max(
                self._blocked_until, float(headers["x-ratelimit-reset"]) + 1
            )
        except (KeyError, ValueError):
            self._blocked_until = max(self._blocked_until, self._clock() + 60)

    def _wait_if_needed(self) -> None:
        delay = self._blocked_until - self._clock()
        if delay > 0:
            self._sleep(delay)

    def _wait_before_retry(
        self, attempt: int, headers: Mapping[str, str]
    ) -> None:
        if headers.get("x-ratelimit-remaining") == "0":
            self._observe_rate_limit(headers)
            self._wait_if_needed()
            return
        retry_after = headers.get("retry-after")
        self._sleep(float(retry_after) if retry_after else 2**attempt)

    @staticmethod
    def _is_retryable(status: int, headers: Mapping[str, str]) -> bool:
        return (
            status == 429
            or 500 <= status <= 599
            or (status == 403 and headers.get("x-ratelimit-remaining") == "0")
        )


def _normalise_headers(headers: Any) -> dict[str, str]:
    if hasattr(headers, "items"):
        return {str(key).lower(): str(value) for key, value in headers.items()}
    return {}


def _api_message(body: str) -> str:
    try:
        data = json.loads(body)
        if isinstance(data, dict) and data.get("message"):
            return str(data["message"])
    except json.JSONDecodeError:
        pass
    return body[:500]
