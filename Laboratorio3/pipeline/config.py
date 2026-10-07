"""Carregamento e validacao da configuracao do pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Indica uma configuracao ausente ou invalida."""


def parse_date(value: str | None, field_name: str) -> date:
    if not value:
        raise ConfigError(
            f"Informe {field_name} no config ou pela linha de comando (AAAA-MM-DD)."
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"{field_name} deve usar o formato AAAA-MM-DD.") from exc


@dataclass(frozen=True)
class PipelineConfig:
    start_date: date
    end_date: date
    candidate_limit: int = 300
    minimum_stars: int = 1_000
    minimum_releases: int = 5
    cache_dir: Path = Path(".cache/github")
    output_dir: Path = Path("data")
    collect_tags: bool = True
    max_retries: int = 5
    request_timeout_seconds: int = 30

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        candidate_limit: int | None = None,
    ) -> "PipelineConfig":
        config_path = Path(path).resolve()
        try:
            raw: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"Arquivo de configuracao nao encontrado: {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"JSON invalido em {config_path}: {exc}") from exc

        observation = raw.get("observation", {})
        collection = raw.get("collection", {})
        runtime = raw.get("runtime", {})
        base_dir = config_path.parent

        config = cls(
            start_date=parse_date(
                start_date or observation.get("start_date"), "start_date"
            ),
            end_date=parse_date(end_date or observation.get("end_date"), "end_date"),
            candidate_limit=int(
                candidate_limit
                if candidate_limit is not None
                else collection.get("candidate_limit", 300)
            ),
            minimum_stars=int(collection.get("minimum_stars", 1_000)),
            minimum_releases=int(collection.get("minimum_releases", 5)),
            cache_dir=_resolve_path(base_dir, runtime.get("cache_dir", ".cache/github")),
            output_dir=_resolve_path(base_dir, runtime.get("output_dir", "data")),
            collect_tags=bool(collection.get("collect_tags", True)),
            max_retries=int(runtime.get("max_retries", 5)),
            request_timeout_seconds=int(runtime.get("request_timeout_seconds", 30)),
        )
        config.validate()
        return config

    def with_limit(self, candidate_limit: int) -> "PipelineConfig":
        updated = replace(self, candidate_limit=candidate_limit)
        updated.validate()
        return updated

    def validate(self) -> None:
        if self.start_date > self.end_date:
            raise ConfigError("start_date deve ser anterior ou igual a end_date.")
        if self.candidate_limit < 1 or self.candidate_limit > 1_000:
            raise ConfigError("candidate_limit deve estar entre 1 e 1000.")
        if self.minimum_stars < 0:
            raise ConfigError("minimum_stars nao pode ser negativo.")
        if self.minimum_releases < 1:
            raise ConfigError("minimum_releases deve ser positivo.")
        if self.max_retries < 0:
            raise ConfigError("max_retries nao pode ser negativo.")
        if self.request_timeout_seconds < 1:
            raise ConfigError("request_timeout_seconds deve ser positivo.")


def _resolve_path(base_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()
