#!/usr/bin/env python3
"""
Lab01 — Flavio de Souza Ferreira Jr e Luidi Cadete
Coleta GraphQL dos campos das RQ01 a RQ06.

Uso:
  # Coloque o token em .env (GITHUB_TOKEN=...) ou exporte no shell
  python3 query.py                  # amostra padrao (10)
  python3 query.py --limit 10       # validacao individual
  python3 query.py --limit 100      # coleta definitiva S01
  python3 query.py --limit 1000     # coleta paginada S02 em CSV

Requisitos:
  - Token com permissao de leitura publica (classic: public_repo ou fine-grained: Contents read)
  - Sem bibliotecas de mineracao de terceiros; HTTP via stdlib
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
DEFAULT_LIMIT = 10
MAX_LIMIT = 1000
PAGE_SIZE = 50
RELEASES_IN_PRIMARY_QUERY_LIMIT = 10
RELEASES_BATCH_SIZE = 10
MAX_REQUEST_ATTEMPTS = 3
RETRY_HTTP_CODES = {502, 503, 504}
BASE_DIR = Path(__file__).resolve().parent
QUERY_FILE = BASE_DIR / "queries" / "rq01_rq02_rq06.graphql"
OUTPUT_DIR = BASE_DIR / "output"
ENV_FILE = BASE_DIR / ".env"

TEAM_NAME = "Flavio de Souza Ferreira Jr e Luidi Cadete"
AMOSTRA_FILE = "amostra_10_flavio.json"
COLETA_100_FILE = "coleta_100.json"
COLETA_1000_FILE = "coleta_1000.csv"

CSV_COLUMNS = [
    "sprint",
    "kind",
    "limit",
    "collected_at",
    "repository_rank",
    "name_with_owner",
    "url",
    "stargazer_count",
    "created_at",
    "age_days",
    "merged_pull_requests",
    "releases_count",
    "updated_at",
    "days_since_update",
    "primary_language",
    "issues_total",
    "issues_closed",
    "closed_issues_ratio",
]


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


@dataclass(frozen=True)
class RepoMetrics:
    name_with_owner: str
    url: str
    stargazer_count: int
    created_at: str
    merged_pull_requests: int
    releases_count: int
    updated_at: str
    primary_language: str | None
    issues_total: int
    issues_closed: int

    @property
    def age_days(self) -> float:
        created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - created).total_seconds() / 86400.0

    @property
    def days_since_update(self) -> float:
        updated = datetime.fromisoformat(self.updated_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - updated).total_seconds() / 86400.0

    @property
    def closed_issues_ratio(self) -> float | None:
        if self.issues_total == 0:
            return None
        return self.issues_closed / self.issues_total


def load_token() -> str:
    load_dotenv()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print(
            "Erro: defina GITHUB_TOKEN no .env ou no ambiente.\n"
            "Ex.: echo 'GITHUB_TOKEN=ghp_seu_token' > .env",
            file=sys.stderr,
        )
        sys.exit(1)
    return token.strip()


def load_query() -> str:
    if not QUERY_FILE.is_file():
        print(f"Erro: query nao encontrada em {QUERY_FILE}", file=sys.stderr)
        sys.exit(1)
    return QUERY_FILE.read_text(encoding="utf-8")


def graphql_request(query: str, variables: dict[str, Any], token: str) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        GITHUB_GRAPHQL_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "lab01-github-mining-flavio-luidi",
        },
    )

    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=60, context=ssl_context()) as response:
                body = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in RETRY_HTTP_CODES and attempt < MAX_REQUEST_ATTEMPTS:
                wait_seconds = attempt * 2
                print(
                    f"GitHub retornou HTTP {exc.code}; nova tentativa em {wait_seconds}s.",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)
                continue
            print(f"Erro HTTP {exc.code}: {detail}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as exc:
            if attempt < MAX_REQUEST_ATTEMPTS:
                wait_seconds = attempt * 2
                print(
                    f"Erro de rede: {exc.reason}; nova tentativa em {wait_seconds}s.",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)
                continue
            print(f"Erro de rede: {exc.reason}", file=sys.stderr)
            sys.exit(1)

    if "errors" in body:
        print("Erros GraphQL:", file=sys.stderr)
        print(json.dumps(body["errors"], indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    return body["data"]


def parse_repositories(data: dict[str, Any]) -> list[RepoMetrics]:
    nodes = data.get("search", {}).get("nodes") or []
    repos: list[RepoMetrics] = []

    for node in nodes:
        if not node or "nameWithOwner" not in node:
            continue

        repos.append(
            RepoMetrics(
                name_with_owner=node["nameWithOwner"],
                url=node["url"],
                stargazer_count=int(node["stargazerCount"]),
                created_at=node["createdAt"],
                merged_pull_requests=int(node["mergedPullRequests"]["totalCount"]),
                releases_count=int(node["releases"]["totalCount"]),
                updated_at=node["updatedAt"],
                primary_language=(node.get("primaryLanguage") or {}).get("name"),
                issues_total=int(node["issues"]["totalCount"]),
                issues_closed=int(node["closedIssues"]["totalCount"]),
            )
        )

    return repos


def collect_search_nodes(
    total_limit: int,
    *,
    include_releases: bool,
    query: str,
    token: str,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    after: str | None = None

    while len(nodes) < total_limit:
        page_size = min(PAGE_SIZE, total_limit - len(nodes))
        data = graphql_request(
            query,
            {
                "first": page_size,
                "after": after,
                "includeReleases": include_releases,
            },
            token,
        )
        search = data.get("search", {})
        page_nodes = [
            node
            for node in search.get("nodes") or []
            if node and "nameWithOwner" in node
        ]
        nodes.extend(page_nodes)

        page_info = search.get("pageInfo") or {}
        if len(nodes) >= total_limit or not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            break

        print(
            f"Pagina coletada: {len(nodes)}/{total_limit} repositorios",
            file=sys.stderr,
        )

    return nodes[:total_limit]


def release_counts_query(names_with_owner: list[str]) -> str:
    """Monta uma consulta GraphQL para um lote pequeno de contagens de releases."""
    fields: list[str] = []
    for index, name_with_owner in enumerate(names_with_owner):
        owner, name = name_with_owner.split("/", 1)
        fields.append(
            f"repo_{index}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
            "{ releases(first: 1) { totalCount } }"
        )
    return "query ReleaseCounts { " + " ".join(fields) + " }"


def fetch_release_counts(names_with_owner: list[str], token: str) -> dict[str, int]:
    """Obtem RQ03 em lotes para evitar timeout do GitHub ao consultar muitas conexoes."""
    counts: dict[str, int] = {}
    total = len(names_with_owner)

    for start in range(0, total, RELEASES_BATCH_SIZE):
        batch = names_with_owner[start : start + RELEASES_BATCH_SIZE]
        data = graphql_request(release_counts_query(batch), {}, token)
        for index, name_with_owner in enumerate(batch):
            repository = data.get(f"repo_{index}")
            if repository is None:
                print(
                    f"Erro: repositorio nao encontrado ao coletar RQ03: {name_with_owner}",
                    file=sys.stderr,
                )
                sys.exit(1)
            counts[name_with_owner] = int(repository["releases"]["totalCount"])

        if total > RELEASES_BATCH_SIZE:
            print(
                f"Releases coletadas: {min(start + len(batch), total)}/{total}",
                file=sys.stderr,
            )

    return counts


def print_validation_table(repos: list[RepoMetrics]) -> None:
    header = (
        f"{'#':<3} {'repositorio':<36} {'stars':>8} {'idade_d':>9} "
        f"{'PRs_M':>7} {'releases':>9} {'ult_upd_d':>9} {'linguagem':<16} "
        f"{'issues':>7} {'fechadas':>8} {'%fech':>7}"
    )
    print(header)
    print("-" * len(header))

    rows_to_show = repos if len(repos) <= 100 else repos[:20]
    for index, repo in enumerate(rows_to_show, start=1):
        ratio = repo.closed_issues_ratio
        ratio_txt = f"{ratio * 100:6.1f}%" if ratio is not None else "   n/a"
        print(
            f"{index:<3} {repo.name_with_owner:<36} {repo.stargazer_count:>8} "
            f"{repo.age_days:>9.0f} {repo.merged_pull_requests:>7} "
            f"{repo.releases_count:>9} {repo.days_since_update:>9.1f} "
            f"{(repo.primary_language or 'n/a'):<16.16} {repo.issues_total:>7} "
            f"{repo.issues_closed:>8} {ratio_txt:>7}"
        )

    if len(repos) > len(rows_to_show):
        print(f"... {len(repos) - len(rows_to_show)} repositorios omitidos da tabela.")


def validate_sample(repos: list[RepoMetrics], expected_limit: int) -> list[str]:
    problems: list[str] = []

    if not repos:
        problems.append("Nenhum repositorio retornado.")
        return problems
    if len(repos) != expected_limit:
        problems.append(f"Esperados {expected_limit} repositorios, mas vieram {len(repos)}.")

    seen_names: set[str] = set()
    for repo in repos:
        if repo.name_with_owner in seen_names:
            problems.append(f"{repo.name_with_owner}: repositorio duplicado.")
        seen_names.add(repo.name_with_owner)
        if not repo.created_at:
            problems.append(f"{repo.name_with_owner}: createdAt ausente (RQ01).")
        if repo.merged_pull_requests < 0:
            problems.append(f"{repo.name_with_owner}: PRs merged invalido (RQ02).")
        if repo.releases_count < 0:
            problems.append(f"{repo.name_with_owner}: releases invalido (RQ03).")
        if not repo.updated_at:
            problems.append(f"{repo.name_with_owner}: updatedAt ausente (RQ04).")
        if repo.days_since_update < -1:
            problems.append(f"{repo.name_with_owner}: updatedAt no futuro (RQ04).")
        if repo.issues_closed > repo.issues_total:
            problems.append(
                f"{repo.name_with_owner}: issues fechadas ({repo.issues_closed}) "
                f"> total ({repo.issues_total}) (RQ06)."
            )
        if repo.issues_total < 0 or repo.issues_closed < 0:
            problems.append(f"{repo.name_with_owner}: contagem de issues negativa (RQ06).")

    return problems


def sprint_for(limit: int) -> str:
    return "Lab01S02" if limit == 1000 else "Lab01S01"


def kind_for(limit: int) -> str:
    if limit == 10:
        return "amostra"
    if limit == 100:
        return "coleta_s01"
    if limit == 1000:
        return "coleta_s02"
    return "custom"


def json_path_for(limit: int) -> Path:
    if limit == 10:
        return OUTPUT_DIR / AMOSTRA_FILE
    if limit == 100:
        return OUTPUT_DIR / COLETA_100_FILE
    return OUTPUT_DIR / f"popular_repos_limit{limit}.json"


def csv_path_for(limit: int) -> Path:
    if limit == 1000:
        return OUTPUT_DIR / COLETA_1000_FILE
    return OUTPUT_DIR / f"popular_repos_limit{limit}.csv"


def repo_record(
    repo: RepoMetrics,
    *,
    rank: int,
    limit: int,
    collected_at: str,
) -> dict[str, Any]:
    return {
        "sprint": sprint_for(limit),
        "kind": kind_for(limit),
        "limit": limit,
        "collected_at": collected_at,
        "repository_rank": rank,
        **asdict(repo),
        "age_days": round(repo.age_days, 2),
        "days_since_update": round(repo.days_since_update, 2),
        "closed_issues_ratio": (
            None if repo.closed_issues_ratio is None else round(repo.closed_issues_ratio, 6)
        ),
    }


def save_json(repos: list[RepoMetrics], limit: int, collected_at: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = json_path_for(limit)
    payload = {
        "sprint": sprint_for(limit),
        "owner": TEAM_NAME,
        "rqs": ["RQ01", "RQ02", "RQ03", "RQ04", "RQ05", "RQ06"],
        "kind": kind_for(limit),
        "limit": limit,
        "collected_at": collected_at,
        "repositories": [
            repo_record(repo, rank=index, limit=limit, collected_at=collected_at)
            for index, repo in enumerate(repos, start=1)
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def save_csv(repos: list[RepoMetrics], limit: int, collected_at: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = csv_path_for(limit)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for index, repo in enumerate(repos, start=1):
            record = repo_record(repo, rank=index, limit=limit, collected_at=collected_at)
            writer.writerow({column: record[column] for column in CSV_COLUMNS})
    return path


def default_output_format(limit: int) -> str:
    return "csv" if limit == 1000 else "json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lab01 — coleta GraphQL paginada dos dados das RQ01 a RQ06"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Quantidade de repositorios (10=amostra, 100=S01, 1000=S02)",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help=f"Gera {AMOSTRA_FILE} e {COLETA_100_FILE} da S01",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv", "both"),
        default=None,
        help="Formato de saida. Padrao: CSV para 1000, JSON para demais limites.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Nao gravar arquivos em output/",
    )
    return parser.parse_args()


def run_collection(
    limit: int,
    *,
    save: bool,
    output_format: str | None,
) -> list[RepoMetrics]:
    token = load_token()
    query = load_query()
    include_releases = limit <= RELEASES_IN_PRIMARY_QUERY_LIMIT
    nodes = collect_search_nodes(
        limit,
        include_releases=include_releases,
        query=query,
        token=token,
    )

    if not include_releases:
        names = [node["nameWithOwner"] for node in nodes]
        release_counts = fetch_release_counts(names, token)
        for node in nodes:
            node["releases"] = {"totalCount": release_counts[node["nameWithOwner"]]}

    repos = parse_repositories({"search": {"nodes": nodes}})

    print(
        f"\n=== limit={limit} | coletados={len(repos)} | RQs: 01, 02, 03, 04, 05, 06 ===\n"
    )
    print_validation_table(repos)

    problems = validate_sample(repos, expected_limit=limit)
    print()
    if problems:
        print("Validacao automatica: problemas encontrados")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)

    print("Validacao automatica: OK (campos presentes e consistentes)")
    print("Lembrete: a validacao oficial da sprint tambem exige revisao manual e Issue.")

    if save:
        collected_at = datetime.now(timezone.utc).isoformat()
        selected_format = output_format or default_output_format(limit)
        output_paths: list[Path] = []
        if selected_format in ("json", "both"):
            output_paths.append(save_json(repos, limit, collected_at))
        if selected_format in ("csv", "both"):
            output_paths.append(save_csv(repos, limit, collected_at))
        for path in output_paths:
            print(f"Arquivo salvo em: {path}")

    return repos


def main() -> None:
    args = parse_args()

    if args.both:
        limits = [10, 100]
    elif args.limit is not None:
        limits = [args.limit]
    else:
        limits = [DEFAULT_LIMIT]

    for limit in limits:
        if limit < 1 or limit > MAX_LIMIT:
            print(f"Erro: --limit deve estar entre 1 e {MAX_LIMIT}.", file=sys.stderr)
            sys.exit(1)
        run_collection(limit, save=not args.no_save, output_format=args.format)


if __name__ == "__main__":
    main()
