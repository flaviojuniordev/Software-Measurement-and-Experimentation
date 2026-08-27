#!/usr/bin/env python3
"""Analise reproduzivel da parte do Luidi na Sprint 3 do Laboratorio 1.

Le o CSV de 1.000 repositorios, calcula RQ03, RQ04, RQ05 e RQ07,
gera quatro graficos e combina os resultados com a analise do Flavio.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR / "output" / "coleta_1000.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output" / "sprint3"
COMBINED_RESULTS_FILENAME = "sprint3_results.json"
LUIDI_RESULTS_FILENAME = "luidi_results.json"
MIN_REPOSITORIES_PER_LANGUAGE = 10
NO_LANGUAGE = "Sem linguagem detectada"
OCTOVERSE_URL = (
    "https://github.blog/news-insights/octoverse/"
    "octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/"
)
OCTOVERSE_TOP_LANGUAGES = (
    "TypeScript",
    "Python",
    "JavaScript",
    "Java",
    "C#",
    "PHP",
    "Shell",
    "C++",
    "HCL",
    "Go",
)

os.environ.setdefault("MPLCONFIGDIR", str(BASE_DIR / ".matplotlib"))

REQUIRED_COLUMNS = {
    "name_with_owner",
    "merged_pull_requests",
    "releases_count",
    "days_since_update",
    "primary_language",
}

RELEASE_BUCKETS = (
    ("0", 0, 0),
    ("1 a 10", 1, 10),
    ("11 a 50", 11, 50),
    ("51 a 100", 51, 100),
    ("101 a 250", 101, 250),
    ("251 a 500", 251, 500),
    ("Mais de 500", 501, None),
)
def as_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"CSV nao encontrado: {path}")
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV sem cabecalho.")
        missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames))
        if missing:
            raise ValueError(f"CSV sem colunas obrigatorias: {', '.join(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError("CSV sem repositorios para analisar.")
    return rows


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Nao e possivel calcular percentil sem valores.")
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    remainder = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * remainder


def descriptive_stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("Nao e possivel analisar uma serie vazia.")
    return {
        "n": len(values),
        "minimum": round(min(values), 4),
        "p25": round(percentile(values, 0.25), 4),
        "median": round(statistics.median(values), 4),
        "mean": round(statistics.fmean(values), 4),
        "p75": round(percentile(values, 0.75), 4),
        "p90": round(percentile(values, 0.90), 4),
        "maximum": round(max(values), 4),
    }


def numeric_validation(rows: list[dict[str, str]], column: str) -> dict[str, int]:
    missing = invalid = negative = 0
    for row in rows:
        raw = row.get(column)
        if raw is None or not raw.strip():
            missing += 1
            continue
        value = as_float(raw)
        if value is None:
            invalid += 1
        elif value < 0:
            negative += 1
    return {
        "total_rows": len(rows),
        "valid_count": len(rows) - missing - invalid - negative,
        "missing_count": missing,
        "invalid_count": invalid,
        "negative_count": negative,
    }


def valid_pairs(rows: list[dict[str, str]], column: str) -> list[tuple[str, float]]:
    pairs: list[tuple[str, float]] = []
    for row in rows:
        value = as_float(row.get(column))
        if value is not None and value >= 0:
            pairs.append((row["name_with_owner"], value))
    return pairs


def bucket_counts(
    values: list[float], buckets: tuple[tuple[str, float, float | None], ...]
) -> list[dict[str, int | str]]:
    result: list[dict[str, int | str]] = []
    for label, lower, upper in buckets:
        count = sum(
            value >= lower if upper is None else lower <= value <= upper
            for value in values
        )
        result.append({"label": label, "count": count})
    return result


def update_bucket_counts(values: list[float]) -> list[dict[str, int | str]]:
    """Gera faixas exclusivas para uma metrica continua em dias."""
    predicates = (
        ("Ate 7 dias", lambda value: value <= 7),
        ("Mais de 7 a 30 dias", lambda value: 7 < value <= 30),
        ("Mais de 30 a 90 dias", lambda value: 30 < value <= 90),
        ("Mais de 90 dias a 1 ano", lambda value: 90 < value <= 365),
        ("Mais de 1 ano", lambda value: value > 365),
    )
    return [
        {"label": label, "count": sum(predicate(value) for value in values)}
        for label, predicate in predicates
    ]


def outlier_summary(pairs: list[tuple[str, float]]) -> dict[str, Any]:
    values = [value for _name, value in pairs]
    q1 = percentile(values, 0.25)
    q3 = percentile(values, 0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    outliers = [
        (name, value)
        for name, value in pairs
        if value < lower_bound or value > upper_bound
    ]
    outliers.sort(key=lambda item: item[1], reverse=True)
    return {
        "method": "IQR (1,5 x intervalo interquartil)",
        "lower_bound": round(lower_bound, 4),
        "upper_bound": round(upper_bound, 4),
        "count": len(outliers),
        "highest": [
            {"repository": name, "value": round(value, 4)}
            for name, value in outliers[:10]
        ],
    }


def top_repositories(pairs: list[tuple[str, float]], limit: int = 10) -> list[dict[str, Any]]:
    ordered = sorted(pairs, key=lambda item: (-item[1], item[0].lower()))
    return [
        {"repository": name, "value": round(value, 4)}
        for name, value in ordered[:limit]
    ]


def language_name(row: dict[str, str]) -> str:
    value = (row.get("primary_language") or "").strip()
    return value or NO_LANGUAGE


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(BASE_DIR).as_posix()
    except ValueError:
        return str(resolved)


def metric_values(rows: list[dict[str, str]], column: str) -> list[float]:
    return [
        value
        for row in rows
        if (value := as_float(row.get(column))) is not None and value >= 0
    ]


def compare_language_groups(
    eligible: list[tuple[str, list[dict[str, str]]]]
) -> dict[str, Any]:
    top_names = [name for name, _rows in eligible[:5]]
    remaining_names = [name for name, _rows in eligible[5:]]
    top_rows = [row for _name, group in eligible[:5] for row in group]
    remaining_rows = [row for _name, group in eligible[5:] for row in group]

    def summarize(group_rows: list[dict[str, str]]) -> dict[str, Any]:
        if not group_rows:
            return {
                "repository_count": 0,
                "median_merged_pull_requests": None,
                "median_releases_count": None,
                "median_days_since_update": None,
            }
        return {
            "repository_count": len(group_rows),
            "median_merged_pull_requests": round(
                statistics.median(metric_values(group_rows, "merged_pull_requests")), 4
            ),
            "median_releases_count": round(
                statistics.median(metric_values(group_rows, "releases_count")), 4
            ),
            "median_days_since_update": round(
                statistics.median(metric_values(group_rows, "days_since_update")), 4
            ),
        }

    top_summary = summarize(top_rows)
    remaining_summary = summarize(remaining_rows)
    if not remaining_rows:
        supported_metrics: list[str] = []
    else:
        supported_metrics = [
            label
            for label, key, direction in (
                ("PRs aceitas", "median_merged_pull_requests", "higher"),
                ("releases", "median_releases_count", "higher"),
                ("atualizacao", "median_days_since_update", "lower"),
            )
            if (
                top_summary[key] > remaining_summary[key]
                if direction == "higher"
                else top_summary[key] < remaining_summary[key]
            )
        ]

    return {
        "definition": (
            "Compara todos os repositorios das cinco linguagens mais frequentes com os "
            "repositorios das demais linguagens elegiveis (minimo de 10 repositorios)."
        ),
        "top_five_languages": top_names,
        "remaining_languages": remaining_names,
        "top_five": top_summary,
        "remaining": remaining_summary,
        "metrics_supporting_hypothesis": supported_metrics,
        "supported_metric_count": len(supported_metrics),
    }


def analyze_rows(rows: list[dict[str, str]], source_csv: Path) -> dict[str, Any]:
    release_pairs = valid_pairs(rows, "releases_count")
    update_pairs = valid_pairs(rows, "days_since_update")
    releases = [value for _name, value in release_pairs]
    update_days = [value for _name, value in update_pairs]
    if not releases or not update_days:
        raise ValueError("RQ03 e RQ04 exigem valores numericos validos.")

    release_stats = descriptive_stats(releases)
    update_stats = descriptive_stats(update_days)
    release_zero = sum(value == 0 for value in releases)
    release_maximum_count = sum(value == max(releases) for value in releases)
    updated_90_days = sum(value <= 90 for value in update_days)

    language_counts = Counter(language_name(row) for row in rows)
    language_distribution = [
        {"language": name, "count": count, "percentage": round(count / len(rows) * 100, 2)}
        for name, count in sorted(
            language_counts.items(), key=lambda item: (-item[1], item[0].lower())
        )
    ]
    no_language_count = language_counts.get(NO_LANGUAGE, 0)
    detected_count = len(rows) - no_language_count
    octoverse_count = sum(language_counts.get(name, 0) for name in OCTOVERSE_TOP_LANGUAGES)
    octoverse_share = octoverse_count / detected_count * 100 if detected_count else 0.0

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        name = language_name(row)
        if name != NO_LANGUAGE:
            groups[name].append(row)
    eligible = sorted(
        (
            (name, group_rows)
            for name, group_rows in groups.items()
            if len(group_rows) >= MIN_REPOSITORIES_PER_LANGUAGE
        ),
        key=lambda item: (-len(item[1]), item[0].lower()),
    )

    by_language: list[dict[str, Any]] = []
    for name, group_rows in eligible:
        prs = metric_values(group_rows, "merged_pull_requests")
        group_releases = metric_values(group_rows, "releases_count")
        group_updates = metric_values(group_rows, "days_since_update")
        metric_stats = {
            "merged_pull_requests": descriptive_stats(prs),
            "releases_count": descriptive_stats(group_releases),
            "days_since_update": descriptive_stats(group_updates),
        }
        by_language.append(
            {
                "language": name,
                "repository_count": len(group_rows),
                "median_merged_pull_requests": metric_stats["merged_pull_requests"]["median"],
                "median_releases_count": metric_stats["releases_count"]["median"],
                "median_days_since_update": metric_stats["days_since_update"]["median"],
                "statistics": metric_stats,
                "outliers": {
                    column: outlier_summary(valid_pairs(group_rows, column))
                    for column in (
                        "merged_pull_requests",
                        "releases_count",
                        "days_since_update",
                    )
                },
            }
        )

    group_comparison = compare_language_groups(eligible)
    supporting = group_comparison["metrics_supporting_hypothesis"]
    if group_comparison["remaining"]["repository_count"] == 0:
        rq07_evaluation = "inconclusiva"
        rq07_conclusion = "Nao ha dois grupos elegiveis suficientes para testar a hipotese da RQ07."
    elif len(supporting) >= 2:
        rq07_evaluation = "sustentada parcialmente"
        rq07_conclusion = (
            "As cinco linguagens mais frequentes apresentam vantagem descritiva em "
            f"{len(supporting)} de 3 metricas ({', '.join(supporting)}). A hipotese e "
            "sustentada parcialmente, sem inferencia de causalidade."
        )
    else:
        rq07_evaluation = "nao sustentada"
        rq07_conclusion = (
            "As cinco linguagens mais frequentes apresentam vantagem descritiva em apenas "
            f"{len(supporting)} de 3 metricas. Os dados nao sustentam a hipotese conjunta."
        )

    rq03_supported = release_zero < len(releases) / 2
    rq04_supported = updated_90_days >= len(update_days) / 2
    rq05_supported = octoverse_share >= 50

    return {
        "sprint": "Lab01S03",
        "responsible": "Luidi",
        "scope": ["RQ03", "RQ04", "RQ05", "RQ07"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": portable_path(source_csv),
        "source_collected_at": rows[0].get("collected_at", "") if rows else "",
        "repositories": len(rows),
        "results": {
            "RQ03": {
                "title": "Sistemas populares lancam releases com frequencia?",
                "metric": "Total de releases publicadas",
                "hypothesis": (
                    "A maioria dos repositorios populares possui pelo menos uma release, "
                    "mas projetos sem empacotamento formal devem formar um grupo relevante."
                ),
                "validation": numeric_validation(rows, "releases_count"),
                "statistics": release_stats,
                "zero_releases_count": release_zero,
                "zero_releases_percentage": round(release_zero / len(releases) * 100, 2),
                "maximum_value_count": release_maximum_count,
                "maximum_value_note": (
                    f"O valor maximo ({release_stats['maximum']:.0f}) aparece em "
                    f"{release_maximum_count} repositorios; a repeticao no teto deve ser "
                    "considerada ao interpretar os maiores outliers."
                ),
                "distribution": bucket_counts(releases, RELEASE_BUCKETS),
                "outliers": outlier_summary(release_pairs),
                "top_repositories": top_repositories(release_pairs),
                "hypothesis_evaluation": "sustentada" if rq03_supported else "nao sustentada",
                "conclusion": (
                    f"A mediana e {release_stats['median']:.0f} releases e {release_zero} de "
                    f"{len(releases)} repositorios ({release_zero / len(releases) * 100:.2f}%) "
                    "nao possuem releases. "
                    + (
                        "A maioria possui ao menos uma release, sustentando a hipotese."
                        if rq03_supported
                        else "A maioria nao possui releases, portanto a hipotese nao e sustentada."
                    )
                ),
            },
            "RQ04": {
                "title": "Sistemas populares sao atualizados com frequencia?",
                "metric": "Dias desde a ultima atualizacao",
                "hypothesis": (
                    "A maioria dos repositorios populares foi atualizada nos ultimos 90 dias."
                ),
                "validation": numeric_validation(rows, "days_since_update"),
                "statistics": update_stats,
                "updated_within": {
                    "7_days": sum(value <= 7 for value in update_days),
                    "30_days": sum(value <= 30 for value in update_days),
                    "90_days": updated_90_days,
                    "more_than_1_year": sum(value > 365 for value in update_days),
                },
                "distribution": update_bucket_counts(update_days),
                "outliers": outlier_summary(update_pairs),
                "least_recently_updated": top_repositories(update_pairs),
                "hypothesis_evaluation": "sustentada" if rq04_supported else "nao sustentada",
                "conclusion": (
                    f"A mediana e {update_stats['median']:.2f} dias desde a atualizacao e "
                    f"{updated_90_days} de {len(update_days)} repositorios "
                    f"({updated_90_days / len(update_days) * 100:.2f}%) foram atualizados em ate "
                    "90 dias. "
                    + (
                        "Os dados sustentam a hipotese de atualizacao frequente."
                        if rq04_supported
                        else "Os dados nao sustentam a hipotese de atualizacao frequente."
                    )
                ),
            },
            "RQ05": {
                "title": "Sistemas populares sao escritos nas linguagens mais populares?",
                "metric": "Linguagem primaria",
                "hypothesis": (
                    "Mais da metade dos repositorios com linguagem detectada usa uma das dez "
                    "linguagens de maior crescimento por contribuidores no Octoverse 2025."
                ),
                "reference": {
                    "name": "GitHub Octoverse 2025",
                    "url": OCTOVERSE_URL,
                    "criterion": "Top 10 linguagens do ranking por contagem de contribuidores em 2025",
                    "languages": list(OCTOVERSE_TOP_LANGUAGES),
                },
                "validation": {
                    "total_rows": len(rows),
                    "detected_count": detected_count,
                    "missing_count": no_language_count,
                    "missing_label": NO_LANGUAGE,
                    "unique_detected_languages": len(language_counts) - (1 if no_language_count else 0),
                },
                "distribution": language_distribution,
                "octoverse_top_10_count": octoverse_count,
                "octoverse_top_10_share_of_detected_percent": round(octoverse_share, 2),
                "outliers": {
                    "method": "Nao aplicavel a variavel categorica",
                    "count": 0,
                    "note": "Outliers por IQR so sao calculados para metricas numericas.",
                },
                "hypothesis_evaluation": "sustentada" if rq05_supported else "nao sustentada",
                "conclusion": (
                    f"Foram encontradas {len(language_counts) - (1 if no_language_count else 0)} "
                    f"linguagens e {no_language_count} repositorios sem linguagem detectada. "
                    f"As linguagens do top 10 do Octoverse 2025 representam {octoverse_share:.2f}% "
                    "dos repositorios com linguagem detectada; "
                    + (
                        "isso sustenta a hipotese definida."
                        if rq05_supported
                        else "isso nao sustenta a hipotese definida."
                    )
                ),
            },
            "RQ07": {
                "title": "As metricas de processo diferem entre linguagens populares?",
                "metric": "Medianas de PRs, releases e dias desde atualizacao por linguagem",
                "hypothesis": (
                    "As cinco linguagens mais frequentes apresentam, em conjunto, mais PRs "
                    "aceitas, mais releases e menos dias desde a atualizacao que as demais "
                    "linguagens com amostra suficiente."
                ),
                "minimum_repositories_per_language": MIN_REPOSITORIES_PER_LANGUAGE,
                "missing_language_count": no_language_count,
                "excluded_below_minimum_count": sum(
                    len(group_rows)
                    for group_rows in groups.values()
                    if len(group_rows) < MIN_REPOSITORIES_PER_LANGUAGE
                ),
                "eligible_language_count": len(by_language),
                "by_language": by_language,
                "group_comparison": group_comparison,
                "outliers": {
                    "method": "IQR calculado dentro de cada metrica e linguagem",
                    "note": (
                        "Os limites, contagens e maiores valores de cada grupo estao em "
                        "by_language.outliers; "
                        "a comparacao principal usa medianas, menos sensiveis a extremos."
                    ),
                },
                "hypothesis_evaluation": rq07_evaluation,
                "conclusion": rq07_conclusion,
            },
        },
    }


def add_bar_labels(axis: Any, bars: Any) -> None:
    for bar in bars:
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{bar.get_height():.0f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )


def save_charts(analysis: dict[str, Any], output_dir: Path) -> dict[str, str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    style = {
        "figure.facecolor": "#ffffff",
        "axes.facecolor": "#ffffff",
        "font.size": 10,
    }
    paths: dict[str, str] = {}

    for rq, filename, title, color in (
        ("RQ03", "rq03_releases.png", "Distribuicao de releases", "#7c3aed"),
        ("RQ04", "rq04_atualizacao.png", "Dias desde a ultima atualizacao", "#0891b2"),
    ):
        distribution = analysis["results"][rq]["distribution"]
        labels = [item["label"] for item in distribution]
        counts = [item["count"] for item in distribution]
        with plt.rc_context(style):
            figure, axis = plt.subplots(figsize=(10.5, 4.8), layout="constrained")
            bars = axis.bar(labels, counts, color=color, width=0.68)
            axis.set_title(title, fontweight="bold", loc="left")
            axis.set_xlabel("Faixa")
            axis.set_ylabel("Repositorios")
            axis.spines[["top", "right"]].set_visible(False)
            axis.grid(axis="y", alpha=0.2)
            axis.set_axisbelow(True)
            axis.tick_params(axis="x", rotation=16)
            add_bar_labels(axis, bars)
            path = output_dir / filename
            figure.savefig(path, dpi=150)
            plt.close(figure)
            paths[rq] = portable_path(path)

    languages = analysis["results"]["RQ05"]["distribution"][:15]
    labels = [item["language"] for item in reversed(languages)]
    counts = [item["count"] for item in reversed(languages)]
    with plt.rc_context(style):
        figure, axis = plt.subplots(figsize=(10.5, 6.4), layout="constrained")
        colors = ["#d97706" if label == NO_LANGUAGE else "#2563eb" for label in labels]
        bars = axis.barh(labels, counts, color=colors, height=0.66)
        axis.set_title("Linguagens primarias mais frequentes", fontweight="bold", loc="left")
        axis.set_xlabel("Repositorios")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="x", alpha=0.2)
        axis.set_axisbelow(True)
        for bar, count in zip(bars, counts):
            axis.text(count, bar.get_y() + bar.get_height() / 2, f" {count}", va="center", fontsize=9)
        path = output_dir / "rq05_linguagens.png"
        figure.savefig(path, dpi=150)
        plt.close(figure)
        paths["RQ05"] = portable_path(path)

    language_rows = analysis["results"]["RQ07"]["by_language"]
    labels = [row["language"] for row in reversed(language_rows)]
    metrics = (
        ("median_merged_pull_requests", "Mediana de PRs aceitas", "#0f766e"),
        ("median_releases_count", "Mediana de releases", "#7c3aed"),
        ("median_days_since_update", "Mediana de dias desde atualizacao", "#0891b2"),
    )
    with plt.rc_context(style):
        height = max(6.5, len(labels) * 0.46)
        figure, axes = plt.subplots(1, 3, figsize=(15.5, height), layout="constrained")
        figure.suptitle(
            f"RQ07 por linguagem (minimo de {MIN_REPOSITORIES_PER_LANGUAGE} repositorios)",
            fontweight="bold",
        )
        for index, (key, title, color) in enumerate(metrics):
            values = [row[key] for row in reversed(language_rows)]
            axes[index].barh(labels, values, color=color, height=0.66)
            axes[index].set_title(title, fontsize=10, fontweight="bold")
            axes[index].grid(axis="x", alpha=0.2)
            axes[index].set_axisbelow(True)
            axes[index].spines[["top", "right"]].set_visible(False)
            if index:
                axes[index].tick_params(axis="y", labelleft=False)
        path = output_dir / "rq07_comparacao_linguagens.png"
        figure.savefig(path, dpi=150)
        plt.close(figure)
        paths["RQ07"] = portable_path(path)

    return paths


def combine_with_base(
    base_analysis: dict[str, Any],
    luidi_analysis: dict[str, Any],
    chart_files: dict[str, str],
    output_dir: Path,
) -> dict[str, Any]:
    combined = dict(base_analysis)
    combined["sprint"] = "Lab01S03"
    combined["scope"] = ["RQ01", "RQ02", "RQ03", "RQ04", "RQ05", "RQ06", "RQ07"]
    combined["generated_at"] = luidi_analysis["generated_at"]
    combined["source_csv"] = luidi_analysis["source_csv"]
    combined["source_collected_at"] = luidi_analysis["source_collected_at"]
    combined["repositories"] = luidi_analysis["repositories"]
    combined["results"] = dict(base_analysis.get("results", {}))
    combined["results"].update(luidi_analysis["results"])
    combined["chart_files"] = {
        rq: portable_path(output_dir / Path(str(path)).name)
        for rq, path in base_analysis.get("chart_files", {}).items()
    }
    combined["chart_files"].update(chart_files)
    return combined


def run_analysis(
    csv_path: Path,
    output_dir: Path,
    *,
    save_plots: bool = True,
    refresh_base: bool = True,
) -> tuple[dict[str, Any], Path, Path]:
    rows = load_rows(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis = analyze_rows(rows, csv_path)
    chart_files = save_charts(analysis, output_dir) if save_plots else {}
    analysis["chart_files"] = chart_files

    luidi_path = output_dir / LUIDI_RESULTS_FILENAME
    luidi_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    combined_path = output_dir / COMBINED_RESULTS_FILENAME
    if refresh_base:
        from analyze_lab01_s03 import run_analysis as run_base_analysis

        base_analysis, _base_path = run_base_analysis(
            csv_path, output_dir, save_plots=save_plots
        )
    elif combined_path.is_file():
        base_analysis = json.loads(combined_path.read_text(encoding="utf-8"))
    else:
        base_analysis = {"results": {}, "chart_files": {}}

    combined = combine_with_base(base_analysis, analysis, chart_files, output_dir)
    combined_path.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return analysis, luidi_path, combined_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analise e graficos da Lab01S03 para RQ03, RQ04, RQ05 e RQ07"
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV de 1.000 repositorios")
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Diretorio dos resultados"
    )
    parser.add_argument("--no-plots", action="store_true", help="Gera apenas os arquivos JSON")
    parser.add_argument(
        "--skip-base-analysis",
        action="store_true",
        help="Nao regenera RQ01, RQ02 e RQ06; reaproveita o JSON geral existente",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        analysis, luidi_path, combined_path = run_analysis(
            args.csv,
            args.output_dir,
            save_plots=not args.no_plots,
            refresh_base=not args.skip_base_analysis,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Erro na analise S03 do Luidi: {exc}") from exc

    print(f"Analise do Luidi salva em: {luidi_path}")
    print(f"Analise completa da S03 salva em: {combined_path}")
    for rq in analysis["scope"]:
        print(f"{rq}: {analysis['results'][rq]['conclusion']}")
    for rq, path in analysis["chart_files"].items():
        print(f"Grafico {rq}: {path}")


if __name__ == "__main__":
    main()
