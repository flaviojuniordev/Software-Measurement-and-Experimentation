"""Coletores de repositorios, releases, tags, commits e workflow runs."""

from __future__ import annotations

from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Iterator
from urllib.parse import parse_qs, parse_qsl, quote, urlencode, urlsplit, urlunsplit

from .git_metadata import GitCollectionError, GitMetadataCollector
from .github_client import GitHubAPIError, GitHubClient, GitHubResponse, parse_link_header
from .metrics import parse_github_datetime


GITHUB_FILTERED_QUERY_LIMIT = 1_000


class WorkflowRunWindowLimitError(RuntimeError):
    """Indica que um mes atingiu o teto de resultados da consulta do GitHub."""


@dataclass(frozen=True)
class DateInterval:
    """Intervalo inclusivo de datas usado no filtro ``created``."""

    start: date
    end: date

    @property
    def github_created_filter(self) -> str:
        return f"{self.start.isoformat()}..{self.end.isoformat()}"


def monthly_intervals(start_date: date, end_date: date) -> list[DateInterval]:
    """Divide uma janela inclusiva em meses reais do calendario."""

    if type(start_date) is not date or type(end_date) is not date:
        raise TypeError("start_date e end_date devem ser datas")
    if start_date > end_date:
        raise ValueError("start_date nao pode ser posterior a end_date")

    intervals: list[DateInterval] = []
    current = start_date
    while current <= end_date:
        last_day = monthrange(current.year, current.month)[1]
        month_end = date(current.year, current.month, last_day)
        interval_end = min(month_end, end_date)
        intervals.append(DateInterval(current, interval_end))
        current = interval_end + timedelta(days=1)
    return intervals


def discover_repositories(
    client: GitHubClient, *, minimum_stars: int, limit: int
) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    maximum_stars: int | None = None

    while len(unique) < limit:
        query = (
            f"stars:>{minimum_stars}"
            if maximum_stars is None
            else f"stars:{minimum_stars + 1}..{maximum_stars}"
        )
        page_limit = min(1_000, limit + 100) if maximum_stars is None else 1_000
        candidates = client.paginate(
            "/search/repositories",
            {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": 100,
            },
            item_key="items",
            limit=page_limit,
        )
        if not candidates:
            break

        added = 0
        last_stars: int | None = None
        for repository in candidates:
            stars = repository.get("stargazers_count")
            if isinstance(stars, int):
                last_stars = stars if last_stars is None else min(last_stars, stars)
            full_name = repository.get("full_name")
            if not isinstance(full_name, str) or not full_name or full_name in seen:
                continue
            seen.add(full_name)
            unique.append(repository)
            added += 1
            if len(unique) >= limit:
                break

        if len(candidates) < 1_000 or last_stars is None:
            break
        next_maximum = last_stars if added else last_stars - 1
        if maximum_stars is not None and next_maximum >= maximum_stars:
            next_maximum = maximum_stars - 1
        if next_maximum <= minimum_stars:
            break
        maximum_stars = next_maximum
    return unique


def collect_workflows(client: GitHubClient, full_name: str) -> list[dict[str, Any]]:
    owner, repository = _split_full_name(full_name)
    workflows = client.paginate(
        f"/repos/{quote(owner)}/{quote(repository)}/actions/workflows",
        {"per_page": 100},
        item_key="workflows",
    )
    fields = ("id", "name", "path", "state", "html_url")
    return [{field: item.get(field) for field in fields} for item in workflows]


def collect_workflow_runs(
    client: GitHubClient,
    full_name: str,
    *,
    default_branch: str,
    start_date: date,
    end_date: date,
    subdivide_large_windows: bool = True,
    max_runs: int | None = None,
    workers: int = 4,
    progress: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Coleta runs de push com subdivisao e paginacao concorrentes.

    A concorrencia e limitada e usa o mesmo cliente, cache, rate limit e retry.
    O filtro local protege os calculos se a API devolver dados fora dos
    parametros solicitados.
    """

    if not default_branch.strip():
        raise ValueError("default_branch e obrigatorio")
    if max_runs is not None and max_runs < 1:
        raise ValueError("max_runs deve ser positivo")
    if workers < 1:
        raise ValueError("workers deve ser positivo")
    owner, repository = _split_full_name(full_name)
    path = f"/repos/{quote(owner)}/{quote(repository)}/actions/runs"
    unique_runs: dict[object, dict[str, Any]] = {}

    interval_pages = _partition_workflow_run_intervals(
        client,
        path,
        default_branch=default_branch,
        initial=DateInterval(start_date, end_date),
        subdivide_large_windows=subdivide_large_windows,
        max_runs=max_runs,
        workers=workers,
        progress=progress,
    )
    raw_runs = _iter_workflow_run_pages(
        client,
        interval_pages,
        workers=workers,
        progress=progress,
    )

    for item in raw_runs:
        run = _normalise_workflow_run(item)
        if run.get("event") != "push":
            continue
        if run.get("head_branch") != default_branch:
            continue
        run_id = run.get("id")
        if run_id is None:
            raise ValueError("workflow run sem id nao pode ser deduplicado")
        unique_runs.setdefault(run_id, run)
    if max_runs is not None and len(unique_runs) > max_runs:
        raise WorkflowRunWindowLimitError(
            f"O repositorio ultrapassou {max_runs} workflow runs no modo "
            "de amostra parcial."
        )

    return list(unique_runs.values())


def _partition_workflow_run_intervals(
    client: GitHubClient,
    path: str,
    *,
    default_branch: str,
    initial: DateInterval,
    subdivide_large_windows: bool,
    max_runs: int | None,
    workers: int,
    progress: Callable[[str], None] | None,
) -> list[tuple[DateInterval, GitHubResponse]]:
    pending = [initial]
    safe: list[tuple[DateInterval, GitHubResponse]] = []
    consulted = 0
    chunk_size = max(workers * 4, 1)

    while pending:
        batch, pending = pending[:chunk_size], pending[chunk_size:]
        requests = [
            (
                path,
                {
                    "branch": default_branch,
                    "event": "push",
                    "created": interval.github_created_filter,
                    "exclude_pull_requests": True,
                    "per_page": 100,
                },
            )
            for interval in batch
        ]
        responses = _parallel_get(client, requests, workers)
        consulted += len(responses)

        for interval, response in zip(batch, responses):
            _, total_count = _workflow_run_page(response)
            if (
                max_runs is not None
                and total_count is not None
                and total_count > max_runs
            ):
                raise WorkflowRunWindowLimitError(
                    f"O repositorio ultrapassou {max_runs} workflow runs no modo "
                    "de amostra parcial."
                )
            reached_limit = (
                total_count is not None
                and total_count >= GITHUB_FILTERED_QUERY_LIMIT
            )
            if reached_limit and not subdivide_large_windows:
                raise WorkflowRunWindowLimitError(
                    f"O intervalo {interval.github_created_filter} atingiu o "
                    f"teto de {GITHUB_FILTERED_QUERY_LIMIT} runs no modo de "
                    "amostra parcial."
                )
            if reached_limit and interval.start == interval.end:
                raise WorkflowRunWindowLimitError(
                    f"O dia {interval.github_created_filter} atingiu o teto de "
                    f"{GITHUB_FILTERED_QUERY_LIMIT} runs e nao pode ser subdividido."
                )
            if reached_limit:
                midpoint = interval.start + (interval.end - interval.start) // 2
                pending.extend(
                    [
                        DateInterval(interval.start, midpoint),
                        DateInterval(midpoint + timedelta(days=1), interval.end),
                    ]
                )
            else:
                safe.append((interval, response))

        if progress is not None:
            progress(
                f"{consulted} intervalos consultados; "
                f"{len(safe)} abaixo do teto; {len(pending)} pendentes"
            )

    return sorted(safe, key=lambda item: item[0].start)


def _iter_workflow_run_pages(
    client: GitHubClient,
    interval_pages: list[tuple[DateInterval, GitHubResponse]],
    *,
    workers: int,
    progress: Callable[[str], None] | None,
) -> Iterator[dict[str, Any]]:
    page_urls: list[str] = []
    linked_pages: list[str] = []

    for _, first in interval_pages:
        page, _ = _workflow_run_page(first)
        yield from page
        urls = _remaining_page_urls(first)
        if urls is None:
            next_url = parse_link_header(first.headers.get("link")).get("next")
            if next_url:
                linked_pages.append(next_url)
        else:
            page_urls.extend(urls)

    chunk_size = max(workers * 4, 1)
    for offset in range(0, len(page_urls), chunk_size):
        batch = page_urls[offset : offset + chunk_size]
        responses = _parallel_get(
            client, [(url, None) for url in batch], workers
        )
        for response in responses:
            page, _ = _workflow_run_page(response)
            yield from page
        if progress is not None:
            done = min(offset + len(batch), len(page_urls))
            progress(f"{done}/{len(page_urls)} paginas adicionais coletadas")

    for next_url in linked_pages:
        while next_url:
            response = client.get(next_url)
            page, _ = _workflow_run_page(response)
            yield from page
            next_url = parse_link_header(response.headers.get("link")).get("next")


def _parallel_get(
    client: GitHubClient,
    requests: list[tuple[str, dict[str, Any] | None]],
    workers: int,
) -> list[GitHubResponse]:
    if workers == 1 or len(requests) <= 1:
        return [client.get(path, params) for path, params in requests]
    with ThreadPoolExecutor(max_workers=min(workers, len(requests))) as executor:
        futures = [
            executor.submit(client.get, path, params) for path, params in requests
        ]
        return [future.result() for future in futures]


def _remaining_page_urls(response: GitHubResponse) -> list[str] | None:
    links = parse_link_header(response.headers.get("link"))
    next_url = links.get("next")
    if not next_url:
        return []
    last_url = links.get("last")
    if not last_url:
        return None
    split = urlsplit(last_url)
    query = parse_qsl(split.query, keep_blank_values=True)
    pages = [value for key, value in query if key == "page"]
    if not pages or not pages[-1].isdigit():
        return None
    last_page = int(pages[-1])
    urls: list[str] = []
    for page_number in range(2, last_page + 1):
        page_query = [
            (key, str(page_number) if key == "page" else value)
            for key, value in query
        ]
        urls.append(
            urlunsplit(
                (
                    split.scheme,
                    split.netloc,
                    split.path,
                    urlencode(page_query),
                    split.fragment,
                )
            )
        )
    return urls


def _workflow_run_page(
    response: GitHubResponse,
) -> tuple[list[dict[str, Any]], int | None]:
    if not isinstance(response.data, dict):
        raise GitHubAPIError(
            response.status, response.url, "resposta de workflow runs invalida"
        )
    page = response.data.get("workflow_runs")
    if not isinstance(page, list):
        raise GitHubAPIError(
            response.status, response.url, "workflow_runs nao contem uma lista"
        )
    total = response.data.get("total_count")
    return page, int(total) if isinstance(total, int) else None


def _normalise_workflow_run(run: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id",
        "workflow_id",
        "event",
        "head_branch",
        "conclusion",
        "status",
        "created_at",
        "run_started_at",
        "updated_at",
        "html_url",
    )
    return {field: run.get(field) for field in fields}


def count_contributors(client: GitHubClient, full_name: str) -> int | None:
    owner, repository = _split_full_name(full_name)
    try:
        response = client.get(
            f"/repos/{quote(owner)}/{quote(repository)}/contributors",
            {"per_page": 1, "anon": True},
        )
    except GitHubAPIError as exc:
        if exc.status == 403 and "too large to list contributors" in str(exc):
            return None
        raise
    if not isinstance(response.data, list):
        return 0
    links = parse_link_header(response.headers.get("link"))
    last_url = links.get("last")
    if last_url:
        pages = parse_qs(urlsplit(last_url).query).get("page")
        if pages and pages[-1].isdigit():
            return int(pages[-1])
    return len(response.data)


def collect_releases(
    client: GitHubClient,
    full_name: str,
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Coleta a janela e uma release principal anterior para comparacao."""

    try:
        return _collect_releases_graphql(
            client,
            full_name,
            start_date=start_date,
            end_date=end_date,
        )
    except (AttributeError, GitHubAPIError):
        return _collect_releases_rest(
            client,
            full_name,
            start_date=start_date,
            end_date=end_date,
        )


def _collect_releases_graphql(
    client: GitHubClient,
    full_name: str,
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    owner, repository = _split_full_name(full_name)
    query = """
    query Lab03Releases($owner: String!, $name: String!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        releases(
          first: 30,
          after: $cursor,
          orderBy: {field: CREATED_AT, direction: DESC}
        ) {
          nodes {
            tagName
            publishedAt
            isDraft
            isPrerelease
            description
            url
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    cursor: str | None = None
    collected: list[dict[str, Any]] = []
    found_previous_main = False
    while True:
        response = client.graphql(
            query,
            {"owner": owner, "name": repository, "cursor": cursor},
        )
        repository_data = (response.data or {}).get("repository")
        if not isinstance(repository_data, dict):
            raise GitHubAPIError(
                response.status, response.url, "repositorio ausente no GraphQL"
            )
        connection = repository_data.get("releases")
        if not isinstance(connection, dict) or not isinstance(
            connection.get("nodes"), list
        ):
            raise GitHubAPIError(
                response.status, response.url, "releases invalidas no GraphQL"
            )
        for node in connection["nodes"]:
            if not isinstance(node, dict):
                continue
            release = {
                "tag_name": node.get("tagName"),
                "published_at": node.get("publishedAt"),
                "draft": bool(node.get("isDraft")),
                "prerelease": bool(node.get("isPrerelease")),
                "body": node.get("description") or "",
                "html_url": node.get("url"),
            }
            published_at = release["published_at"]
            if not published_at:
                continue
            published_date = parse_github_datetime(published_at).date()
            if published_date > end_date:
                continue
            if published_date >= start_date:
                collected.append(release)
                continue
            if not release["draft"] and not release["prerelease"]:
                collected.append(release)
                found_previous_main = True
                break
        if found_previous_main:
            break
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            raise GitHubAPIError(
                response.status, response.url, "cursor GraphQL ausente"
            )
    return sorted(collected, key=lambda item: item.get("published_at") or "")


def _collect_releases_rest(
    client: GitHubClient,
    full_name: str,
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:

    owner, repository = _split_full_name(full_name)
    collected: list[dict[str, Any]] = []
    found_previous_main = False

    for response in client.iter_responses(
        f"/repos/{quote(owner)}/{quote(repository)}/releases", {"per_page": 30}
    ):
        if not isinstance(response.data, list):
            raise GitHubAPIError(
                response.status, response.url, "lista de releases invalida"
            )
        for release in response.data:
            published_at = release.get("published_at")
            if not published_at:
                continue
            published_date = parse_github_datetime(published_at).date()
            if published_date > end_date:
                continue
            if published_date >= start_date:
                collected.append(release)
                continue
            if not release.get("draft") and not release.get("prerelease"):
                collected.append(release)
                found_previous_main = True
                break
        if found_previous_main:
            break

    return sorted(collected, key=lambda item: item.get("published_at") or "")


def main_releases_in_window(
    releases: list[dict[str, Any]], start_date: date, end_date: date
) -> list[dict[str, Any]]:
    return [
        release
        for release in releases
        if not release.get("draft")
        and not release.get("prerelease")
        and release.get("published_at")
        and start_date
        <= parse_github_datetime(release["published_at"]).date()
        <= end_date
    ]


def collect_tags(
    client: GitHubClient,
    full_name: str,
    *,
    git_collector: GitMetadataCollector | None = None,
) -> list[dict[str, Any]]:
    if git_collector is not None:
        try:
            return git_collector.collect_tags(full_name)
        except GitCollectionError:
            pass
    owner, repository = _split_full_name(full_name)
    return client.paginate(
        f"/repos/{quote(owner)}/{quote(repository)}/tags", {"per_page": 100}
    )


def collect_release_comparisons(
    client: GitHubClient,
    full_name: str,
    releases: list[dict[str, Any]],
    *,
    start_date: date,
    end_date: date,
    git_collector: GitMetadataCollector | None = None,
) -> list[dict[str, Any]]:
    """Compara cada release principal da janela com sua antecessora."""

    owner, repository = _split_full_name(full_name)
    main_releases = sorted(
        (
            release
            for release in releases
            if not release.get("draft")
            and not release.get("prerelease")
            and release.get("published_at")
            and release.get("tag_name")
        ),
        key=lambda item: item["published_at"],
    )
    comparisons: list[dict[str, Any]] = []

    if git_collector is not None:
        prepare_tags = getattr(git_collector, "prepare_tags", None)
        if callable(prepare_tags):
            try:
                prepare_tags(
                    full_name,
                    [release["tag_name"] for release in main_releases],
                )
            except GitCollectionError:
                # Mantem o fallback individual REST/Git de cada comparacao.
                pass

    for previous, current in zip(main_releases, main_releases[1:]):
        published_date = parse_github_datetime(current["published_at"]).date()
        if not start_date <= published_date <= end_date:
            continue
        try:
            if git_collector is not None:
                commits = git_collector.commits_between(
                    full_name, previous["tag_name"], current["tag_name"]
                )
            else:
                commits = _collect_comparison_rest(
                    client,
                    owner,
                    repository,
                    previous["tag_name"],
                    current["tag_name"],
                )
            comparisons.append(
                {
                    "base_tag": previous["tag_name"],
                    "head_tag": current["tag_name"],
                    "release_published_at": current["published_at"],
                    "commits": [
                        commit
                        if "author_date" in commit
                        else _normalise_commit(commit)
                        for commit in commits
                    ],
                    "error": None,
                }
            )
        except GitCollectionError:
            try:
                commits = _collect_comparison_rest(
                    client,
                    owner,
                    repository,
                    previous["tag_name"],
                    current["tag_name"],
                )
                comparisons.append(
                    {
                        "base_tag": previous["tag_name"],
                        "head_tag": current["tag_name"],
                        "release_published_at": current["published_at"],
                        "commits": [_normalise_commit(commit) for commit in commits],
                        "error": None,
                    }
                )
            except GitHubAPIError as exc:
                comparisons.append(
                    {
                        "base_tag": previous["tag_name"],
                        "head_tag": current["tag_name"],
                        "release_published_at": current["published_at"],
                        "commits": [],
                        "error": str(exc),
                        "error_status": exc.status,
                    }
                )
        except GitHubAPIError as exc:
            comparisons.append(
                {
                    "base_tag": previous["tag_name"],
                    "head_tag": current["tag_name"],
                    "release_published_at": current["published_at"],
                    "commits": [],
                    "error": str(exc),
                    "error_status": exc.status,
                }
            )
    return comparisons


def _collect_comparison_rest(
    client: GitHubClient,
    owner: str,
    repository: str,
    base_tag: str,
    head_tag: str,
) -> list[dict[str, Any]]:
    base = quote(base_tag, safe="")
    head = quote(head_tag, safe="")
    path = f"/repos/{quote(owner)}/{quote(repository)}/compare/{base}...{head}"
    return client.paginate(path, {"per_page": 100}, item_key="commits")


def _normalise_commit(commit: dict[str, Any]) -> dict[str, Any]:
    payload = commit.get("commit") or {}
    author = payload.get("author") or {}
    committer = payload.get("committer") or {}
    return {
        "sha": commit.get("sha"),
        "author_date": author.get("date") or committer.get("date"),
        "message": payload.get("message"),
    }


def _split_full_name(full_name: str) -> tuple[str, str]:
    try:
        owner, repository = full_name.split("/", 1)
    except ValueError as exc:
        raise ValueError(f"Nome de repositorio invalido: {full_name}") from exc
    if not owner or not repository:
        raise ValueError(f"Nome de repositorio invalido: {full_name}")
    return owner, repository
