"""Validacao manual e avaliacao da heuristica de releases corretivas."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import quote

from .collectors import collect_release_comparisons, collect_releases
from .github_client import GitHubAPIError, GitHubClient
from .metrics import (
    CorrectiveReleaseHeuristic,
    calculate_release_change_failure_rate,
    classify_corrective_release,
    parse_github_datetime,
)
from .output import write_csv, write_json


GOLD_SAMPLE_SIZE = 60
RELEASES_PER_REPOSITORY = 5
DEFAULT_RANDOM_STATE = 42
PROJECT_TYPES = (
    "biblioteca/framework",
    "aplicacao/servico",
    "ferramenta CLI",
    "outro",
)
DELIVERY_LABELS = ("sim", "nao", "incerto")
BINARY_LABELS = ("sim", "nao")
REPOSITORY_TEMPLATE_FIELDS = (
    "repository",
    "project_type",
    "releases_are_deliveries",
)
RELEASE_TEMPLATE_FIELDS = (
    "repository",
    "release_tag",
    "release_published_at",
    "release_url",
    "comparison_url",
    "is_corrective_manual",
)


class ValidationError(ValueError):
    """Indica entrada ausente ou inconsistente na validacao manual."""


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(path)
    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except FileNotFoundError as exc:
        raise ValidationError(f"arquivo nao encontrado: {csv_path}") from exc


def select_gold_repositories(
    rows: Sequence[Mapping[str, Any]],
    *,
    allow_partial: bool,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> list[str]:
    """Seleciona 60 repositorios ou todos os repositorios do modo parcial."""

    names = [str(row.get("full_name", "")).strip() for row in rows]
    if not names or any(not name for name in names):
        raise ValidationError("o dataset precisa da coluna full_name preenchida")
    if len(set(names)) != len(names):
        raise ValidationError("o dataset contem repositorios duplicados")
    names = sorted(names)
    if allow_partial:
        if len(names) >= GOLD_SAMPLE_SIZE:
            raise ValidationError(
                "--allow-partial e exclusivo para checkpoints com menos de 60 "
                "repositorios; execute o modo final neste dataset"
            )
        return names
    if len(names) < GOLD_SAMPLE_SIZE:
        raise ValidationError(
            f"modo final exige {GOLD_SAMPLE_SIZE} repositorios; "
            f"o dataset contem {len(names)}. Use --allow-partial somente para "
            "o checkpoint explicitamente parcial."
        )
    return random.Random(random_state).sample(names, GOLD_SAMPLE_SIZE)


def sample_repository_releases(
    repository: str,
    releases: Sequence[Mapping[str, Any]],
    *,
    start_date: date,
    end_date: date,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> list[Mapping[str, Any]]:
    """Sorteia cinco releases principais de forma estavel por repositorio."""

    eligible = sorted(
        (
            release
            for release in releases
            if not release.get("draft")
            and not release.get("prerelease")
            and release.get("published_at")
            and release.get("tag_name")
            and start_date
            <= parse_github_datetime(
                release["published_at"], "published_at"
            ).date()
            <= end_date
        ),
        key=lambda release: (
            parse_github_datetime(release["published_at"], "published_at"),
            str(release["tag_name"]),
        ),
    )
    if len(eligible) < RELEASES_PER_REPOSITORY:
        raise ValidationError(
            f"{repository} possui somente {len(eligible)} releases elegiveis; "
            f"sao necessarias {RELEASES_PER_REPOSITORY}"
        )
    digest = hashlib.sha256(
        f"{random_state}:{repository}".encode("utf-8")
    ).digest()
    repository_seed = int.from_bytes(digest[:8], "big")
    chosen = random.Random(repository_seed).sample(
        eligible, RELEASES_PER_REPOSITORY
    )
    return sorted(
        chosen,
        key=lambda release: (
            parse_github_datetime(release["published_at"], "published_at"),
            str(release["tag_name"]),
        ),
    )


def prepare_gold_sample(
    dataset_path: str | Path,
    raw_dir: str | Path,
    output_dir: str | Path,
    *,
    start_date: date,
    end_date: date,
    allow_partial: bool,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> tuple[Path, Path, Path, Path]:
    """Gera templates cegos e independentes para os dois avaliadores."""

    dataset_rows = read_csv_rows(dataset_path)
    repositories = select_gold_repositories(
        dataset_rows,
        allow_partial=allow_partial,
        random_state=random_state,
    )
    payloads = _load_raw_payloads(repositories, Path(raw_dir))
    repository_rows = [
        {
            "repository": repository,
            "project_type": "",
            "releases_are_deliveries": "",
        }
        for repository in repositories
    ]
    release_rows: list[dict[str, str]] = []
    for repository in repositories:
        selected = sample_repository_releases(
            repository,
            payloads[repository].get("releases", []),
            start_date=start_date,
            end_date=end_date,
            random_state=random_state,
        )
        for release in selected:
            tag = str(release["tag_name"])
            comparison = next(
                (
                    item
                    for item in payloads[repository].get("comparisons", [])
                    if item.get("head_tag") == tag
                ),
                {},
            )
            base_tag = str(comparison.get("base_tag") or "")
            release_rows.append(
                {
                    "repository": repository,
                    "release_tag": tag,
                    "release_published_at": str(release["published_at"]),
                    "release_url": str(
                        release.get("html_url")
                        or f"https://github.com/{repository}/releases/tag/"
                        f"{quote(tag, safe='')}"
                    ),
                    "comparison_url": (
                        f"https://github.com/{repository}/compare/"
                        f"{quote(base_tag, safe='')}...{quote(tag, safe='')}"
                        if base_tag
                        else ""
                    ),
                    "is_corrective_manual": "",
                }
            )

    suffix = "_partial" if allow_partial else ""
    destination = Path(output_dir)
    paths: list[Path] = []
    for rater in ("flavio", "luidi"):
        repository_path = destination / f"{rater}_repositories{suffix}.csv"
        release_path = destination / f"{rater}_releases{suffix}.csv"
        write_csv(repository_path, repository_rows, REPOSITORY_TEMPLATE_FIELDS)
        write_csv(release_path, release_rows, RELEASE_TEMPLATE_FIELDS)
        paths.extend((repository_path, release_path))
    return paths[0], paths[1], paths[2], paths[3]


def hydrate_gold_sample_payloads(
    dataset_path: str | Path,
    raw_dir: str | Path,
    client: GitHubClient,
    *,
    start_date: date,
    end_date: date,
    random_state: int = DEFAULT_RANDOM_STATE,
    progress: Callable[[str], None] = print,
) -> dict[str, int]:
    """Coleta somente releases e comparacoes exigidas pela amostra-ouro."""

    repositories = select_gold_repositories(
        read_csv_rows(dataset_path),
        allow_partial=False,
        random_state=random_state,
    )
    destination = Path(raw_dir)
    destination.mkdir(parents=True, exist_ok=True)
    hydrated = 0
    reused = 0
    failures: list[str] = []

    for position, repository in enumerate(repositories, start=1):
        progress(f"[{position}/{len(repositories)}] {repository}")
        path = destination / f"{repository.replace('/', '__')}.json"
        payload = _read_existing_payload(path, repository)
        try:
            releases = payload.get("releases", [])
            if not _has_gold_release_sample(
                repository,
                releases,
                start_date=start_date,
                end_date=end_date,
                random_state=random_state,
            ):
                releases = collect_releases(
                    client,
                    repository,
                    start_date=start_date,
                    end_date=end_date,
                )
            selected = sample_repository_releases(
                repository,
                releases,
                start_date=start_date,
                end_date=end_date,
                random_state=random_state,
            )
            comparisons = _collect_selected_comparisons(
                client,
                repository,
                releases,
                selected,
                payload.get("comparisons", []),
                start_date=start_date,
                end_date=end_date,
            )
            ready_payload = {
                **payload,
                "repository": {
                    **(payload.get("repository") or {}),
                    "full_name": repository,
                },
                "releases": releases,
                "comparisons": comparisons,
            }
            write_json(path, ready_payload, compact=True)
            if payload and _payload_has_selected_comparisons(
                releases,
                selected,
                payload.get("comparisons", []),
            ):
                reused += 1
                progress("  payload reutilizado")
            else:
                hydrated += 1
                progress("  payload preparado")
        except (GitHubAPIError, ValidationError, ValueError) as exc:
            failures.append(f"{repository}: {exc}")
            progress(f"  erro: {exc}")

    if failures:
        raise ValidationError(
            "nao foi possivel preparar toda a amostra-ouro: "
            + " | ".join(failures)
        )
    return {
        "repositories": len(repositories),
        "hydrated": hydrated,
        "reused": reused,
    }


def _read_existing_payload(path: Path, repository: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    payload_repository = (payload.get("repository") or {}).get("full_name")
    return payload if payload_repository == repository else {}


def _has_gold_release_sample(
    repository: str,
    releases: Sequence[Mapping[str, Any]],
    *,
    start_date: date,
    end_date: date,
    random_state: int,
) -> bool:
    try:
        sample_repository_releases(
            repository,
            releases,
            start_date=start_date,
            end_date=end_date,
            random_state=random_state,
        )
    except (ValidationError, ValueError, KeyError):
        return False
    return True


def _collect_selected_comparisons(
    client: GitHubClient,
    repository: str,
    releases: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    existing: Sequence[Mapping[str, Any]],
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    main_releases = sorted(
        (
            dict(release)
            for release in releases
            if not release.get("draft")
            and not release.get("prerelease")
            and release.get("published_at")
            and release.get("tag_name")
        ),
        key=lambda release: (
            parse_github_datetime(release["published_at"], "published_at"),
            str(release["tag_name"]),
        ),
    )
    existing_by_head = {
        str(item.get("head_tag")): dict(item)
        for item in existing
        if item.get("head_tag")
    }
    selected_tags = {str(release["tag_name"]) for release in selected}
    comparisons = [dict(item) for item in existing]
    for index, current in enumerate(main_releases):
        tag = str(current["tag_name"])
        if tag not in selected_tags or index == 0:
            continue
        previous = main_releases[index - 1]
        cached = existing_by_head.get(tag)
        if cached and cached.get("base_tag") == previous.get("tag_name"):
            continue
        collected = collect_release_comparisons(
            client,
            repository,
            [previous, current],
            start_date=start_date,
            end_date=end_date,
        )
        comparisons.extend(collected)
    return comparisons


def _payload_has_selected_comparisons(
    releases: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    comparisons: Sequence[Mapping[str, Any]],
) -> bool:
    ordered_tags = [
        str(release["tag_name"])
        for release in sorted(
            (
                release
                for release in releases
                if not release.get("draft")
                and not release.get("prerelease")
                and release.get("published_at")
                and release.get("tag_name")
            ),
            key=lambda release: (
                parse_github_datetime(release["published_at"], "published_at"),
                str(release["tag_name"]),
            ),
        )
    ]
    required = {
        str(release["tag_name"])
        for release in selected
        if ordered_tags.index(str(release["tag_name"])) > 0
    }
    available = {
        str(comparison.get("head_tag"))
        for comparison in comparisons
        if comparison.get("head_tag")
    }
    return required <= available


def categorical_agreement(
    rater_a: Sequence[str],
    rater_b: Sequence[str],
    categories: Sequence[str],
) -> dict[str, float | int | None]:
    """Calcula concordancia observada, kappa de Cohen e kappa de Fleiss."""

    if len(rater_a) != len(rater_b) or not rater_a:
        raise ValidationError("os avaliadores precisam rotular os mesmos itens")
    allowed = set(categories)
    if any(label not in allowed for label in (*rater_a, *rater_b)):
        raise ValidationError("foi encontrado um rotulo ausente ou invalido")
    total = len(rater_a)
    observed = sum(a == b for a, b in zip(rater_a, rater_b)) / total
    counts_a = Counter(rater_a)
    counts_b = Counter(rater_b)
    expected_cohen = sum(
        counts_a[category] / total * counts_b[category] / total
        for category in categories
    )
    cohen = (
        (observed - expected_cohen) / (1 - expected_cohen)
        if expected_cohen < 1
        else None
    )

    item_agreements = []
    combined = Counter()
    for a, b in zip(rater_a, rater_b):
        item_counts = Counter((a, b))
        combined.update((a, b))
        item_agreements.append(
            (sum(count * count for count in item_counts.values()) - 2) / 2
        )
    mean_item_agreement = sum(item_agreements) / total
    expected_fleiss = sum(
        (combined[category] / (2 * total)) ** 2 for category in categories
    )
    fleiss = (
        (mean_item_agreement - expected_fleiss) / (1 - expected_fleiss)
        if expected_fleiss < 1
        else None
    )
    return {
        "items": total,
        "observed_agreement": observed,
        "cohen_kappa": cohen,
        "fleiss_kappa": fleiss,
    }


def calculate_agreement_files(
    flavio_repositories: str | Path,
    flavio_releases: str | Path,
    luidi_repositories: str | Path,
    luidi_releases: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Calcula os kappas e cria pendencias sem resolver divergencias."""

    flavio_repo_rows = read_csv_rows(flavio_repositories)
    luidi_repo_rows = read_csv_rows(luidi_repositories)
    flavio_release_rows = read_csv_rows(flavio_releases)
    luidi_release_rows = read_csv_rows(luidi_releases)
    repo_pairs = _pair_rows(flavio_repo_rows, luidi_repo_rows, ("repository",))
    release_pairs = _pair_rows(
        flavio_release_rows,
        luidi_release_rows,
        ("repository", "release_tag"),
    )

    project_a = _labels(repo_pairs, 0, "project_type", PROJECT_TYPES)
    project_b = _labels(repo_pairs, 1, "project_type", PROJECT_TYPES)
    delivery_a = _labels(
        repo_pairs, 0, "releases_are_deliveries", DELIVERY_LABELS
    )
    delivery_b = _labels(
        repo_pairs, 1, "releases_are_deliveries", DELIVERY_LABELS
    )
    corrective_a = _labels(
        release_pairs, 0, "is_corrective_manual", BINARY_LABELS
    )
    corrective_b = _labels(
        release_pairs, 1, "is_corrective_manual", BINARY_LABELS
    )
    report = {
        "raters": 2,
        "majority_resolution": False,
        "project_type": categorical_agreement(
            project_a, project_b, PROJECT_TYPES
        ),
        "releases_are_deliveries": categorical_agreement(
            delivery_a, delivery_b, DELIVERY_LABELS
        ),
        "corrective_releases": categorical_agreement(
            corrective_a, corrective_b, BINARY_LABELS
        ),
    }

    pending_repositories = []
    for flavio, luidi in repo_pairs:
        if (
            flavio["project_type"] != luidi["project_type"]
            or flavio["releases_are_deliveries"]
            != luidi["releases_are_deliveries"]
        ):
            pending_repositories.append(
                {
                    "repository": flavio["repository"],
                    "flavio_project_type": flavio["project_type"],
                    "luidi_project_type": luidi["project_type"],
                    "consensus_project_type": "",
                    "flavio_releases_are_deliveries": flavio[
                        "releases_are_deliveries"
                    ],
                    "luidi_releases_are_deliveries": luidi[
                        "releases_are_deliveries"
                    ],
                    "consensus_releases_are_deliveries": "",
                }
            )
    pending_releases = [
        {
            "repository": flavio["repository"],
            "release_tag": flavio["release_tag"],
            "flavio_is_corrective": flavio["is_corrective_manual"],
            "luidi_is_corrective": luidi["is_corrective_manual"],
            "consensus_is_corrective": "",
        }
        for flavio, luidi in release_pairs
        if flavio["is_corrective_manual"] != luidi["is_corrective_manual"]
    ]
    destination = Path(output_dir)
    write_json(destination / "agreement.json", report)
    write_csv(
        destination / "pending_repositories.csv",
        pending_repositories,
        (
            "repository",
            "flavio_project_type",
            "luidi_project_type",
            "consensus_project_type",
            "flavio_releases_are_deliveries",
            "luidi_releases_are_deliveries",
            "consensus_releases_are_deliveries",
        ),
    )
    write_csv(
        destination / "pending_releases.csv",
        pending_releases,
        (
            "repository",
            "release_tag",
            "flavio_is_corrective",
            "luidi_is_corrective",
            "consensus_is_corrective",
        ),
    )
    return report


def build_consensus_files(
    flavio_repositories: str | Path,
    flavio_releases: str | Path,
    luidi_repositories: str | Path,
    luidi_releases: str | Path,
    repository_resolutions: str | Path,
    release_resolutions: str | Path,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Consolida acordos e exige resolucao humana para cada divergencia."""

    repo_pairs = _pair_rows(
        read_csv_rows(flavio_repositories),
        read_csv_rows(luidi_repositories),
        ("repository",),
    )
    release_pairs = _pair_rows(
        read_csv_rows(flavio_releases),
        read_csv_rows(luidi_releases),
        ("repository", "release_tag"),
    )
    _labels(repo_pairs, 0, "project_type", PROJECT_TYPES)
    _labels(repo_pairs, 1, "project_type", PROJECT_TYPES)
    _labels(repo_pairs, 0, "releases_are_deliveries", DELIVERY_LABELS)
    _labels(repo_pairs, 1, "releases_are_deliveries", DELIVERY_LABELS)
    _labels(release_pairs, 0, "is_corrective_manual", BINARY_LABELS)
    _labels(release_pairs, 1, "is_corrective_manual", BINARY_LABELS)
    repo_resolution_rows = read_csv_rows(repository_resolutions)
    release_resolution_rows = read_csv_rows(release_resolutions)
    repo_resolutions = {
        row.get("repository", ""): row for row in repo_resolution_rows
    }
    release_resolutions_map = {
        (row.get("repository", ""), row.get("release_tag", "")): row
        for row in release_resolution_rows
    }

    repository_consensus = []
    for flavio, luidi in repo_pairs:
        repository = flavio["repository"]
        resolution = repo_resolutions.get(repository, {})
        project_type = _resolve_label(
            flavio["project_type"],
            luidi["project_type"],
            resolution.get("consensus_project_type", ""),
            PROJECT_TYPES,
            f"tipo do projeto de {repository}",
        )
        deliveries = _resolve_label(
            flavio["releases_are_deliveries"],
            luidi["releases_are_deliveries"],
            resolution.get("consensus_releases_are_deliveries", ""),
            DELIVERY_LABELS,
            f"entregas de {repository}",
        )
        repository_consensus.append(
            {
                "repository": repository,
                "project_type_consensus": project_type,
                "releases_are_deliveries_consensus": deliveries,
            }
        )

    release_consensus = []
    for flavio, luidi in release_pairs:
        key = (flavio["repository"], flavio["release_tag"])
        resolution = release_resolutions_map.get(key, {})
        label = _resolve_label(
            flavio["is_corrective_manual"],
            luidi["is_corrective_manual"],
            resolution.get("consensus_is_corrective", ""),
            BINARY_LABELS,
            f"release {key[0]} {key[1]}",
        )
        release_consensus.append(
            {
                "repository": key[0],
                "release_tag": key[1],
                "release_published_at": luidi.get("release_published_at", ""),
                "release_url": luidi.get("release_url", ""),
                "is_corrective_consensus": label,
            }
        )

    destination = Path(output_dir)
    repository_path = destination / "consensus_repositories.csv"
    release_path = destination / "consensus_releases.csv"
    write_csv(
        repository_path,
        repository_consensus,
        (
            "repository",
            "project_type_consensus",
            "releases_are_deliveries_consensus",
        ),
    )
    write_csv(
        release_path,
        release_consensus,
        (
            "repository",
            "release_tag",
            "release_published_at",
            "release_url",
            "is_corrective_consensus",
        ),
    )
    return repository_path, release_path


def classification_metrics(
    expected: Sequence[bool], predicted: Sequence[bool]
) -> dict[str, Any]:
    """Calcula precisao, recall, F1 e matriz de confusao binaria."""

    if len(expected) != len(predicted) or not expected:
        raise ValidationError("esperado e previsto precisam ter os mesmos itens")
    true_positive = sum(e and p for e, p in zip(expected, predicted))
    false_positive = sum(not e and p for e, p in zip(expected, predicted))
    true_negative = sum(not e and not p for e, p in zip(expected, predicted))
    false_negative = sum(e and not p for e, p in zip(expected, predicted))
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = (
        true_positive / precision_denominator if precision_denominator else 0.0
    )
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "observations": len(expected),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "true_negative": true_negative,
            "false_negative": false_negative,
        },
    }


def evaluate_heuristic_from_consensus(
    consensus_releases: str | Path,
    raw_dir: str | Path,
    history_path: str | Path,
    *,
    heuristic: CorrectiveReleaseHeuristic,
) -> dict[str, Any]:
    """Avalia uma versao da heuristica e acrescenta o resultado ao historico."""

    rows = read_csv_rows(consensus_releases)
    repositories = sorted({row.get("repository", "") for row in rows})
    if not repositories or "" in repositories:
        raise ValidationError("o consenso de releases esta vazio ou invalido")
    expected_labels = [row.get("is_corrective_consensus", "") for row in rows]
    if any(label not in BINARY_LABELS for label in expected_labels):
        raise ValidationError("o consenso possui rotulo ausente ou invalido")
    payloads = _load_raw_payloads(repositories, Path(raw_dir))
    predicted = [
        _predict_release(
            payloads[row["repository"]], row["release_tag"], heuristic
        )
        for row in rows
    ]
    metrics = classification_metrics(
        [label == "sim" for label in expected_labels], predicted
    )
    evaluation = {
        "heuristic": heuristic.criteria(),
        **metrics,
        "refinement_required": metrics["f1"] < 0.70,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    history_file = Path(history_path)
    history = {"evaluations": []}
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValidationError(f"historico invalido: {history_file}") from exc
    evaluations = history.get("evaluations")
    if not isinstance(evaluations, list):
        raise ValidationError("historico de avaliacoes invalido")
    if any(
        item.get("heuristic", {}).get("version") == heuristic.version
        for item in evaluations
        if isinstance(item, dict)
    ):
        raise ValidationError(
            f"a versao {heuristic.version!r} ja existe; use um novo nome "
            "para preservar a comparacao"
        )
    evaluations.append(evaluation)
    write_json(history_file, history)
    return evaluation


def enrich_dataset_with_release_cfr(
    dataset_path: str | Path,
    raw_dir: str | Path,
    output_path: str | Path,
    *,
    start_date: date,
    end_date: date,
) -> Path:
    """Acrescenta o CFR por entrega a uma copia do dataset existente."""

    source = Path(dataset_path).resolve()
    destination = Path(output_path).resolve()
    if source == destination:
        raise ValidationError("a saida nao pode sobrescrever o dataset de entrada")
    rows = read_csv_rows(source)
    repositories = [row.get("full_name", "") for row in rows]
    payloads = _load_raw_payloads(repositories, Path(raw_dir))
    enriched = []
    for row in rows:
        payload = payloads[row["full_name"]]
        summary = calculate_release_change_failure_rate(
            payload.get("releases", []),
            payload.get("comparisons", []),
            start_date,
            end_date,
        )
        enriched.append({**row, **summary.as_dict()})
    fields = list(rows[0]) if rows else []
    for field in (
        "release_change_failure_rate",
        "release_cfr_evaluated",
        "release_cfr_failed",
        "release_cfr_censored",
    ):
        if field not in fields:
            fields.append(field)
    write_csv(destination, enriched, fields)
    return destination


def _load_raw_payloads(
    repositories: Iterable[str], raw_dir: Path
) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for repository in repositories:
        path = raw_dir / f"{repository.replace('/', '__')}.json"
        if not path.exists():
            missing.append(repository)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValidationError(f"payload bruto invalido: {path}") from exc
        payload_repository = (payload.get("repository") or {}).get("full_name")
        if payload_repository != repository:
            raise ValidationError(
                f"payload {path} pertence a {payload_repository!r}, nao a "
                f"{repository!r}"
            )
        payloads[repository] = payload
    if missing:
        raise ValidationError(
            "faltam payloads brutos para: " + ", ".join(sorted(missing))
        )
    return payloads


def _pair_rows(
    rows_a: Sequence[dict[str, str]],
    rows_b: Sequence[dict[str, str]],
    key_fields: tuple[str, ...],
) -> list[tuple[dict[str, str], dict[str, str]]]:
    def keyed(rows: Sequence[dict[str, str]]) -> dict[tuple[str, ...], dict[str, str]]:
        result: dict[tuple[str, ...], dict[str, str]] = {}
        for row in rows:
            key = tuple(row.get(field, "").strip() for field in key_fields)
            if any(not value for value in key):
                raise ValidationError("arquivo de rotulos possui chave vazia")
            if key in result:
                raise ValidationError(f"item duplicado no arquivo de rotulos: {key}")
            result[key] = row
        return result

    keyed_a = keyed(rows_a)
    keyed_b = keyed(rows_b)
    if set(keyed_a) != set(keyed_b):
        raise ValidationError("os avaliadores nao possuem exatamente os mesmos itens")
    return [(keyed_a[key], keyed_b[key]) for key in sorted(keyed_a)]


def _labels(
    pairs: Sequence[tuple[dict[str, str], dict[str, str]]],
    rater_index: int,
    field: str,
    categories: Sequence[str],
) -> list[str]:
    labels = [pair[rater_index].get(field, "").strip() for pair in pairs]
    allowed = set(categories)
    if any(label not in allowed for label in labels):
        raise ValidationError(f"a coluna {field} possui rotulo ausente ou invalido")
    return labels


def _resolve_label(
    flavio: str,
    luidi: str,
    resolution: str,
    categories: Sequence[str],
    description: str,
) -> str:
    if flavio == luidi:
        return flavio
    resolved = resolution.strip()
    if resolved not in set(categories):
        raise ValidationError(f"consenso humano pendente ou invalido para {description}")
    return resolved


def _predict_release(
    payload: Mapping[str, Any],
    release_tag: str,
    heuristic: CorrectiveReleaseHeuristic,
) -> bool:
    releases = sorted(
        (
            release
            for release in payload.get("releases", [])
            if not release.get("draft")
            and not release.get("prerelease")
            and release.get("published_at")
            and release.get("tag_name")
        ),
        key=lambda release: parse_github_datetime(
            release["published_at"], "published_at"
        ),
    )
    for index, current in enumerate(releases):
        if current["tag_name"] != release_tag:
            continue
        previous = releases[index - 1] if index else {}
        comparison = next(
            (
                item
                for item in payload.get("comparisons", [])
                if item.get("head_tag") == release_tag
            ),
            {},
        )
        messages = [
            commit.get("message")
            for commit in comparison.get("commits", [])
            if isinstance(commit, Mapping)
        ]
        return classify_corrective_release(
            previous, current, messages, heuristic=heuristic
        )
    repository = (payload.get("repository") or {}).get("full_name", "desconhecido")
    raise ValidationError(f"release {repository} {release_tag} nao encontrada no bruto")


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use datas no formato AAAA-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validacao da heuristica de releases corretivas"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    cfr = subparsers.add_parser("cfr", help="calcula o CFR por entrega")
    cfr.add_argument("--dataset", required=True)
    cfr.add_argument("--raw-dir", required=True)
    cfr.add_argument("--output", required=True)
    cfr.add_argument("--start-date", required=True, type=_iso_date)
    cfr.add_argument("--end-date", required=True, type=_iso_date)

    hydrate = subparsers.add_parser(
        "hydrate-gold-sample",
        help="coleta os payloads minimos dos 60 repositorios sorteados",
    )
    hydrate.add_argument("--dataset", required=True)
    hydrate.add_argument("--raw-dir", required=True)
    hydrate.add_argument("--cache-dir", default=".cache/github")
    hydrate.add_argument("--start-date", required=True, type=_iso_date)
    hydrate.add_argument("--end-date", required=True, type=_iso_date)
    hydrate.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE)

    gold = subparsers.add_parser(
        "gold-sample", help="gera templates cegos dos dois avaliadores"
    )
    gold.add_argument("--dataset", required=True)
    gold.add_argument("--raw-dir", required=True)
    gold.add_argument("--output-dir", required=True)
    gold.add_argument("--start-date", required=True, type=_iso_date)
    gold.add_argument("--end-date", required=True, type=_iso_date)
    gold.add_argument("--allow-partial", action="store_true")
    gold.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE)

    agreement = subparsers.add_parser("agreement", help="calcula concordancia")
    _add_rater_arguments(agreement)
    agreement.add_argument("--output-dir", required=True)

    consensus = subparsers.add_parser("consensus", help="gera consenso validado")
    _add_rater_arguments(consensus)
    consensus.add_argument("--repository-resolutions", required=True)
    consensus.add_argument("--release-resolutions", required=True)
    consensus.add_argument("--output-dir", required=True)

    evaluate = subparsers.add_parser("evaluate", help="avalia a heuristica")
    evaluate.add_argument("--consensus-releases", required=True)
    evaluate.add_argument("--raw-dir", required=True)
    evaluate.add_argument("--history", required=True)
    evaluate.add_argument("--version", default="v1")
    evaluate.add_argument("--keywords", default="fix,hotfix,revert")
    evaluate.add_argument("--no-patch-rule", action="store_true")
    return parser


def _add_rater_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--flavio-repositories", required=True)
    parser.add_argument("--flavio-releases", required=True)
    parser.add_argument("--luidi-repositories", required=True)
    parser.add_argument("--luidi-releases", required=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "cfr":
            result: Any = enrich_dataset_with_release_cfr(
                args.dataset,
                args.raw_dir,
                args.output,
                start_date=args.start_date,
                end_date=args.end_date,
            )
        elif args.command == "hydrate-gold-sample":
            result = hydrate_gold_sample_payloads(
                args.dataset,
                args.raw_dir,
                GitHubClient.from_environment(args.cache_dir),
                start_date=args.start_date,
                end_date=args.end_date,
                random_state=args.random_state,
            )
        elif args.command == "gold-sample":
            result = prepare_gold_sample(
                args.dataset,
                args.raw_dir,
                args.output_dir,
                start_date=args.start_date,
                end_date=args.end_date,
                allow_partial=args.allow_partial,
                random_state=args.random_state,
            )
        elif args.command == "agreement":
            result = calculate_agreement_files(
                args.flavio_repositories,
                args.flavio_releases,
                args.luidi_repositories,
                args.luidi_releases,
                args.output_dir,
            )
        elif args.command == "consensus":
            result = build_consensus_files(
                args.flavio_repositories,
                args.flavio_releases,
                args.luidi_repositories,
                args.luidi_releases,
                args.repository_resolutions,
                args.release_resolutions,
                args.output_dir,
            )
        else:
            keywords = tuple(
                keyword.strip()
                for keyword in args.keywords.split(",")
                if keyword.strip()
            )
            result = evaluate_heuristic_from_consensus(
                args.consensus_releases,
                args.raw_dir,
                args.history,
                heuristic=CorrectiveReleaseHeuristic(
                    version=args.version,
                    keywords=keywords,
                    patch_only=not args.no_patch_rule,
                ),
            )
    except (ValidationError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    if isinstance(result, tuple):
        rendered = [str(item) for item in result]
    elif isinstance(result, Path):
        rendered = str(result)
    else:
        rendered = result
    print(json.dumps(rendered, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
