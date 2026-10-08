"""Coletores de repositorios, releases, tags, commits e workflow runs."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

from .github_client import GitHubAPIError, GitHubClient, parse_link_header
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
    query = f"stars:>{minimum_stars}"
    return client.paginate(
        "/search/repositories",
        {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 100,
        },
        item_key="items",
        limit=limit,
    )


def collect_workflows(client: GitHubClient, full_name: str) -> list[dict[str, Any]]:
    owner, repository = _split_full_name(full_name)
    return client.paginate(
        f"/repos/{quote(owner)}/{quote(repository)}/actions/workflows",
        {"per_page": 100},
        item_key="workflows",
    )


def collect_workflow_runs(
    client: GitHubClient,
    full_name: str,
    *,
    default_branch: str,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Coleta runs de push do default branch, por mes e sem duplicatas.

    ``GitHubClient.paginate`` fornece cache, retomada, paginacao, rate limit e
    backoff. O filtro local protege os calculos se a API devolver dados fora dos
    parametros solicitados.
    """

    if not default_branch.strip():
        raise ValueError("default_branch e obrigatorio")
    owner, repository = _split_full_name(full_name)
    path = f"/repos/{quote(owner)}/{quote(repository)}/actions/runs"
    unique_runs: dict[object, dict[str, Any]] = {}

    for interval in monthly_intervals(start_date, end_date):
        month_runs = client.paginate(
            path,
            {
                "branch": default_branch,
                "event": "push",
                "created": interval.github_created_filter,
                "per_page": 100,
            },
            item_key="workflow_runs",
        )
        if len(month_runs) >= GITHUB_FILTERED_QUERY_LIMIT:
            raise WorkflowRunWindowLimitError(
                f"O intervalo {interval.github_created_filter} atingiu o teto de "
                f"{GITHUB_FILTERED_QUERY_LIMIT} runs; subdivida-o para evitar "
                "dados truncados."
            )

        for item in month_runs:
            run = dict(item)
            if run.get("event") != "push":
                continue
            if run.get("head_branch") != default_branch:
                continue
            run_id = run.get("id")
            if run_id is None:
                raise ValueError("workflow run sem id nao pode ser deduplicado")
            unique_runs.setdefault(run_id, run)

    return list(unique_runs.values())


def count_contributors(client: GitHubClient, full_name: str) -> int:
    owner, repository = _split_full_name(full_name)
    response = client.get(
        f"/repos/{quote(owner)}/{quote(repository)}/contributors",
        {"per_page": 1, "anon": True},
    )
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


def collect_tags(client: GitHubClient, full_name: str) -> list[dict[str, Any]]:
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

    for previous, current in zip(main_releases, main_releases[1:]):
        published_date = parse_github_datetime(current["published_at"]).date()
        if not start_date <= published_date <= end_date:
            continue
        base = quote(previous["tag_name"], safe="")
        head = quote(current["tag_name"], safe="")
        path = (
            f"/repos/{quote(owner)}/{quote(repository)}/compare/{base}...{head}"
        )
        try:
            commits = client.paginate(path, {"per_page": 100}, item_key="commits")
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
    return comparisons


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
