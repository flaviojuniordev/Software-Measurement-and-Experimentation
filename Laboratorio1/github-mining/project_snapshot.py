#!/usr/bin/env python3
"""
Exporta snapshot do GitHub Projects v2 para CSV.

Uso:
  python3 project_snapshot.py --owner usuario --project-number 1
  python3 project_snapshot.py --owner org --owner-type org --project-number 3
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
DEFAULT_OUTPUT = BASE_DIR / "snapshots" / "lab01s03_project_snapshot.csv"
MAX_REQUEST_ATTEMPTS = 3
RETRY_HTTP_CODES = {502, 503, 504}

CSV_COLUMNS = [
    "snapshot_at",
    "project_title",
    "project_url",
    "item_id",
    "content_type",
    "repository",
    "issue_number",
    "title",
    "url",
    "state",
    "assignees",
    "status",
    "field_values_json",
]


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def load_token() -> str:
    load_dotenv()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("Erro: defina GITHUB_TOKEN no .env ou no ambiente.", file=sys.stderr)
        sys.exit(1)
    return token.strip()


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


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
            "User-Agent": "lab01-project-snapshot",
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


def project_query(owner_type: str) -> str:
    owner_field = "organization" if owner_type == "org" else "user"
    return f"""
query ProjectSnapshot($owner: String!, $number: Int!, $after: String) {{
  owner: {owner_field}(login: $owner) {{
    projectV2(number: $number) {{
      title
      url
      items(first: 100, after: $after) {{
        pageInfo {{
          hasNextPage
          endCursor
        }}
        nodes {{
          id
          type
          content {{
            ... on Issue {{
              number
              title
              url
              state
              repository {{
                nameWithOwner
              }}
              assignees(first: 10) {{
                nodes {{
                  login
                }}
              }}
            }}
            ... on PullRequest {{
              number
              title
              url
              state
              repository {{
                nameWithOwner
              }}
              assignees(first: 10) {{
                nodes {{
                  login
                }}
              }}
            }}
            ... on DraftIssue {{
              title
            }}
          }}
          fieldValues(first: 20) {{
            nodes {{
              ... on ProjectV2ItemFieldTextValue {{
                text
                field {{
                  ... on ProjectV2FieldCommon {{
                    name
                  }}
                }}
              }}
              ... on ProjectV2ItemFieldNumberValue {{
                number
                field {{
                  ... on ProjectV2FieldCommon {{
                    name
                  }}
                }}
              }}
              ... on ProjectV2ItemFieldDateValue {{
                date
                field {{
                  ... on ProjectV2FieldCommon {{
                    name
                  }}
                }}
              }}
              ... on ProjectV2ItemFieldSingleSelectValue {{
                name
                field {{
                  ... on ProjectV2FieldCommon {{
                    name
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""


def collect_project_items(
    *,
    owner: str,
    owner_type: str,
    project_number: int,
    token: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    query = project_query(owner_type)
    after: str | None = None
    items: list[dict[str, Any]] = []
    project: dict[str, Any] | None = None

    while True:
        data = graphql_request(
            query,
            {"owner": owner, "number": project_number, "after": after},
            token,
        )
        owner_data = data.get("owner")
        if not owner_data:
            print(f"Erro: owner nao encontrado: {owner}", file=sys.stderr)
            sys.exit(1)
        project = owner_data.get("projectV2")
        if not project:
            print(f"Erro: Project v2 numero {project_number} nao encontrado.", file=sys.stderr)
            sys.exit(1)

        page = project.get("items") or {}
        items.extend(page.get("nodes") or [])
        page_info = page.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            break

    return project, items


def field_values_for(item: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for value in (item.get("fieldValues") or {}).get("nodes") or []:
        field = value.get("field") or {}
        field_name = field.get("name")
        if not field_name:
            continue
        if "text" in value:
            values[field_name] = value["text"]
        elif "number" in value:
            values[field_name] = value["number"]
        elif "date" in value:
            values[field_name] = value["date"]
        elif "name" in value:
            values[field_name] = value["name"]
    return values


def content_row(
    *,
    item: dict[str, Any],
    project: dict[str, Any],
    snapshot_at: str,
) -> dict[str, Any]:
    content = item.get("content") or {}
    field_values = field_values_for(item)
    assignees = [
        node["login"]
        for node in (content.get("assignees") or {}).get("nodes") or []
        if node and "login" in node
    ]
    repository = content.get("repository") or {}

    return {
        "snapshot_at": snapshot_at,
        "project_title": project["title"],
        "project_url": project["url"],
        "item_id": item.get("id"),
        "content_type": item.get("type"),
        "repository": repository.get("nameWithOwner"),
        "issue_number": content.get("number"),
        "title": content.get("title"),
        "url": content.get("url"),
        "state": content.get("state"),
        "assignees": ";".join(assignees),
        "status": field_values.get("Status"),
        "field_values_json": json.dumps(field_values, ensure_ascii=False, sort_keys=True),
    }


def save_snapshot(project: dict[str, Any], items: list[dict[str, Any]], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_at = datetime.now(timezone.utc).isoformat()

    with output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for item in items:
            writer.writerow(content_row(item=item, project=project, snapshot_at=snapshot_at))

    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta snapshot CSV do GitHub Projects v2.")
    parser.add_argument("--owner", required=True, help="Login do usuario ou organizacao dona do Project.")
    parser.add_argument(
        "--owner-type",
        choices=("user", "org"),
        default="user",
        help="Tipo do owner do Project.",
    )
    parser.add_argument("--project-number", type=int, required=True, help="Numero do Project v2.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Arquivo CSV de saida.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = load_token()
    project, items = collect_project_items(
        owner=args.owner,
        owner_type=args.owner_type,
        project_number=args.project_number,
        token=token,
    )
    output = save_snapshot(project, items, args.output)
    print(f"Snapshot salvo em: {output} ({len(items)} itens)")


if __name__ == "__main__":
    main()
