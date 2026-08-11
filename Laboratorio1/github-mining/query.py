#!/usr/bin/env python3
"""
Lab01S01 — Flavio de Souza Ferreira Jr e Luidi Cadete
Coleta GraphQL dos campos das RQ01 a RQ06.

Uso:
  # Coloque o token em .env (GITHUB_TOKEN=...) ou exporte no shell
  python3 query.py                 # amostra padrão (10)
  python3 query.py --limit 10      # validação individual
  python3 query.py --limit 100     # coleta definitiva S01

Requisitos:
  - Token com permissão de leitura pública (classic: public_repo ou fine-grained: Contents read)
  - Sem bibliotecas de mineração de terceiros; HTTP via stdlib
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
DEFAULT_LIMIT = 10
RELEASES_IN_PRIMARY_QUERY_LIMIT = 10
RELEASES_BATCH_SIZE = 10
BASE_DIR = Path(__file__).resolve().parent
QUERY_FILE = BASE_DIR / "queries" / "rq01_rq02_rq06.graphql"
OUTPUT_DIR = BASE_DIR / "output"
ENV_FILE = BASE_DIR / ".env"


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
        print(f"Erro: query não encontrada em {QUERY_FILE}", file=sys.stderr)
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
            "User-Agent": "lab01s01-flavio-de-souza-ferreira-jr-github-mining",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=60, context=ssl_context()) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"Erro HTTP {exc.code}: {detail}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
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
    """Obtém RQ03 em lotes para evitar timeout do GitHub ao consultar 100 conexões."""
    counts: dict[str, int] = {}
    for start in range(0, len(names_with_owner), RELEASES_BATCH_SIZE):
        batch = names_with_owner[start : start + RELEASES_BATCH_SIZE]
        data = graphql_request(release_counts_query(batch), {}, token)
        for index, name_with_owner in enumerate(batch):
            repository = data.get(f"repo_{index}")
            if repository is None:
                print(
                    f"Erro: repositório não encontrado ao coletar RQ03: {name_with_owner}",
                    file=sys.stderr,
                )
                sys.exit(1)
            counts[name_with_owner] = int(repository["releases"]["totalCount"])
    return counts


def print_validation_table(repos: list[RepoMetrics]) -> None:
    header = (
        f"{'#':<3} {'repositório':<36} {'stars':>8} {'idade_d':>9} "
        f"{'PRs_M':>7} {'releases':>9} {'atualizado':<20} {'linguagem':<16} "
        f"{'issues':>7} {'fechadas':>8} {'%fech':>7}"
    )
    print(header)
    print("-" * len(header))

    for index, repo in enumerate(repos, start=1):
        ratio = repo.closed_issues_ratio
        ratio_txt = f"{ratio * 100:6.1f}%" if ratio is not None else "   n/a"
        print(
            f"{index:<3} {repo.name_with_owner:<36} {repo.stargazer_count:>8} "
            f"{repo.age_days:>9.0f} {repo.merged_pull_requests:>7} "
            f"{repo.releases_count:>9} {repo.updated_at:<20.19} "
            f"{(repo.primary_language or 'n/a'):<16.16} {repo.issues_total:>7} "
            f"{repo.issues_closed:>8} {ratio_txt:>7}"
        )


def validate_sample(repos: list[RepoMetrics]) -> list[str]:
    problems: list[str] = []

    if not repos:
        problems.append("Nenhum repositório retornado.")
        return problems

    for repo in repos:
        if not repo.created_at:
            problems.append(f"{repo.name_with_owner}: createdAt ausente (RQ01).")
        if repo.merged_pull_requests < 0:
            problems.append(f"{repo.name_with_owner}: PRs merged inválido (RQ02).")
        if repo.releases_count < 0:
            problems.append(f"{repo.name_with_owner}: releases inválido (RQ03).")
        if not repo.updated_at:
            problems.append(f"{repo.name_with_owner}: updatedAt ausente (RQ04).")
        if repo.issues_closed > repo.issues_total:
            problems.append(
                f"{repo.name_with_owner}: issues fechadas ({repo.issues_closed}) "
                f"> total ({repo.issues_total}) (RQ06)."
            )
        if repo.issues_total < 0 or repo.issues_closed < 0:
            problems.append(f"{repo.name_with_owner}: contagem de issues negativa (RQ06).")

    return problems


OWNER_NAME = "Luidi Cadete"
OWNER_SLUG = "luidi"
AMOSTRA_FILE = f"amostra_10_{OWNER_SLUG}.json"
COLETA_FILE = "coleta_100.json"


def output_path_for(limit: int) -> Path:
    """Nomes estáveis: amostra pessoal (10) e coleta do grupo (100)."""
    if limit == 10:
        return OUTPUT_DIR / AMOSTRA_FILE
    if limit == 100:
        return OUTPUT_DIR / COLETA_FILE
    return OUTPUT_DIR / f"popular_repos_limit{limit}.json"


def save_json(repos: list[RepoMetrics], limit: int) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = output_path_for(limit)
    kind = "amostra" if limit == 10 else "coleta" if limit == 100 else "custom"

    payload = {
        "sprint": "Lab01S01",
        "owner": OWNER_NAME,
        "rqs": ["RQ01", "RQ02", "RQ03", "RQ04", "RQ05", "RQ06"],
        "kind": kind,
        "limit": limit,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "repositories": [
            {
                **asdict(repo),
                "age_days": round(repo.age_days, 2),
                "closed_issues_ratio": (
                    None
                    if repo.closed_issues_ratio is None
                    else round(repo.closed_issues_ratio, 6)
                ),
            }
            for repo in repos
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lab01S01 — coleta GraphQL dos dados das RQ01 a RQ06"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Quantidade de repositórios (10=amostra, 100=coleta S01)",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help=f"Gera {AMOSTRA_FILE} e {COLETA_FILE}",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Não gravar JSON em output/",
    )
    return parser.parse_args()


def run_collection(limit: int, *, save: bool) -> list[RepoMetrics]:
    token = load_token()
    query = load_query()
    include_releases = limit <= RELEASES_IN_PRIMARY_QUERY_LIMIT
    data = graphql_request(
        query,
        {"first": limit, "includeReleases": include_releases},
        token,
    )

    if include_releases:
        repos = parse_repositories(data)
    else:
        names = [
            node["nameWithOwner"]
            for node in (data.get("search", {}).get("nodes") or [])
            if node and "nameWithOwner" in node
        ]
        release_counts = fetch_release_counts(names, token)
        for node in data.get("search", {}).get("nodes") or []:
            if node and "nameWithOwner" in node:
                node["releases"] = {
                    "totalCount": release_counts[node["nameWithOwner"]]
                }
        repos = parse_repositories(data)

    print(f"\n=== limit={limit} | coletados={len(repos)} | RQs: 01, 02, 03, 04, 05, 06 ===\n")
    print_validation_table(repos)

    problems = validate_sample(repos)
    print()
    if problems:
        print("Validação automática: problemas encontrados")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)

    print("Validação automática: OK (campos presentes e consistentes)")
    print("Lembrete: a validação oficial da sprint é manual e vai na Issue.")

    if save:
        out = save_json(repos, limit)
        print(f"JSON salvo em: {out}")

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
        if limit < 1 or limit > 100:
            print("Erro: --limit deve estar entre 1 e 100 (S01).", file=sys.stderr)
            sys.exit(1)
        run_collection(limit, save=not args.no_save)


if __name__ == "__main__":
    main()
