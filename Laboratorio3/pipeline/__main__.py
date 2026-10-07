"""Entrada de linha de comando: python -m pipeline."""

from __future__ import annotations

import argparse
import json
import sys

from .config import ConfigError, PipelineConfig
from .github_client import GitHubClient
from .runner import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline DORA do Laboratorio 03")
    parser.add_argument("--config", default="config.json", help="arquivo JSON")
    parser.add_argument("--start-date", help="inicio oficial da janela (AAAA-MM-DD)")
    parser.add_argument("--end-date", help="fim oficial da janela (AAAA-MM-DD)")
    parser.add_argument(
        "--limit", type=int, help="numero de repositorios candidatos (padrao: 300)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = PipelineConfig.from_file(
            args.config,
            start_date=args.start_date,
            end_date=args.end_date,
            candidate_limit=args.limit,
        )
        client = GitHubClient.from_environment(
            config.cache_dir,
            max_retries=config.max_retries,
            timeout_seconds=config.request_timeout_seconds,
        )
        summary = run_pipeline(config, client)
    except (ConfigError, RuntimeError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
