#!/usr/bin/env python3
"""Analise reproduzivel da Sprint 3 do Laboratorio 1.

Le o CSV de 1.000 repositorios e gera os resultados e graficos das RQs
assumidas nesta entrega: RQ01, RQ02 e RQ06.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Evita que o Matplotlib tente gravar configuracoes no diretorio pessoal do usuario.
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR / "output" / "coleta_1000.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output" / "sprint3"
os.environ.setdefault("MPLCONFIGDIR", str(BASE_DIR / ".matplotlib"))

REQUIRED_COLUMNS = {
    "name_with_owner",
    "age_days",
    "merged_pull_requests",
    "issues_total",
    "issues_closed",
    "closed_issues_ratio",
}

AGE_BUCKETS = (
    ("Ate 1 ano", 0, 365.25),
    ("1 a 3 anos", 365.25, 365.25 * 3),
    ("3 a 5 anos", 365.25 * 3, 365.25 * 5),
    ("5 a 10 anos", 365.25 * 5, 365.25 * 10),
    ("Mais de 10 anos", 365.25 * 10, None),
)
PR_BUCKETS = (
    ("0", 0, 0),
    ("1 a 10", 1, 10),
    ("11 a 100", 11, 100),
    ("101 a 500", 101, 500),
    ("501 a 1.000", 501, 1000),
    ("1.001 a 5.000", 1001, 5000),
    ("Mais de 5.000", 5001, None),
)
RATIO_BUCKETS = (
    ("0% a 24%", 0.0, 0.249999),
    ("25% a 49%", 0.25, 0.499999),
    ("50% a 74%", 0.5, 0.749999),
    ("75% a 89%", 0.75, 0.899999),
    ("90% a 100%", 0.9, 1.0),
)


def as_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def as_int(value: str | None) -> int | None:
    number = as_float(value)
    return None if number is None else int(number)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV sem cabecalho.")
        missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames))
        if missing:
            raise ValueError(f"CSV sem colunas obrigatorias: {', '.join(missing)}")
        return list(reader)


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
    q1 = percentile(values, 0.25)
    q3 = percentile(values, 0.75)
    return {
        "n": len(values),
        "minimum": round(min(values), 4),
        "p25": round(q1, 4),
        "median": round(statistics.median(values), 4),
        "mean": round(statistics.fmean(values), 4),
        "p75": round(q3, 4),
        "p90": round(percentile(values, 0.9), 4),
        "maximum": round(max(values), 4),
    }


def bucket_counts(values: list[float], buckets: tuple[tuple[str, float, float | None], ...]) -> list[dict[str, int | str]]:
    result: list[dict[str, int | str]] = []
    for label, lower, upper in buckets:
        if upper is None:
            count = sum(value >= lower for value in values)
        else:
            count = sum(lower <= value <= upper for value in values)
        result.append({"label": label, "count": count})
    return result


def outlier_summary(rows: list[dict[str, str]], column: str) -> dict[str, Any]:
    pairs = [(row["name_with_owner"], as_float(row[column])) for row in rows]
    valid_pairs = [(name, value) for name, value in pairs if value is not None]
    values = [value for _name, value in valid_pairs]
    q1 = percentile(values, 0.25)
    q3 = percentile(values, 0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    outliers = [(name, value) for name, value in valid_pairs if value < lower_bound or value > upper_bound]
    outliers.sort(key=lambda item: item[1], reverse=True)
    return {
        "method": "IQR (1,5 x intervalo interquartil)",
        "lower_bound": round(lower_bound, 4),
        "upper_bound": round(upper_bound, 4),
        "count": len(outliers),
        "highest": [
            {"repository": name, "value": round(value, 4)} for name, value in outliers[:5]
        ],
    }


def analyze_rows(rows: list[dict[str, str]], source_csv: Path) -> dict[str, Any]:
    ages = [value for row in rows if (value := as_float(row["age_days"])) is not None]
    prs = [value for row in rows if (value := as_float(row["merged_pull_requests"])) is not None]
    ratio_rows = [row for row in rows if as_float(row["closed_issues_ratio"]) is not None]
    ratios = [as_float(row["closed_issues_ratio"]) for row in ratio_rows]
    ratios = [value for value in ratios if value is not None]

    age_stats = descriptive_stats(ages)
    pr_stats = descriptive_stats(prs)
    ratio_stats = descriptive_stats(ratios)
    median_years = age_stats["median"] / 365.25
    ratio_percent = ratio_stats["median"] * 100

    return {
        "sprint": "Lab01S03",
        "scope": ["RQ01", "RQ02", "RQ06"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(source_csv.resolve()),
        "source_collected_at": rows[0].get("collected_at", "") if rows else "",
        "repositories": len(rows),
        "results": {
            "RQ01": {
                "title": "Sistemas populares sao maduros/antigos?",
                "metric": "Idade do repositorio em dias",
                "statistics": age_stats,
                "median_years": round(median_years, 2),
                "distribution": bucket_counts(ages, AGE_BUCKETS),
                "outliers": outlier_summary(rows, "age_days"),
                "conclusion": (
                    "A mediana de idade e de "
                    f"{median_years:.2f} anos; isso sustenta a hipotese de que os repositorios "
                    "populares da amostra sao, em geral, maduros."
                ),
            },
            "RQ02": {
                "title": "Sistemas populares recebem muita contribuicao externa?",
                "metric": "Total de pull requests aceitas",
                "statistics": pr_stats,
                "distribution": bucket_counts(prs, PR_BUCKETS),
                "outliers": outlier_summary(rows, "merged_pull_requests"),
                "conclusion": (
                    "A mediana de pull requests aceitas e de "
                    f"{pr_stats['median']:.0f}. A distribuicao deve ser lida junto com os outliers, "
                    "pois poucos projetos muito grandes elevam fortemente a media."
                ),
            },
            "RQ06": {
                "title": "Sistemas populares possuem alto percentual de issues fechadas?",
                "metric": "Razao entre issues fechadas e total de issues",
                "statistics": ratio_stats,
                "median_percent": round(ratio_percent, 2),
                "excluded_no_issues": len(rows) - len(ratio_rows),
                "distribution": bucket_counts(ratios, RATIO_BUCKETS),
                "outliers": outlier_summary(ratio_rows, "closed_issues_ratio"),
                "conclusion": (
                    "A mediana da razao de issues fechadas e de "
                    f"{ratio_percent:.2f}%. Os repositorios sem issues foram excluidos desta razao "
                    "porque nao ha denominador valido para o calculo."
                ),
            },
        },
    }


def save_charts(analysis: dict[str, Any], output_dir: Path) -> dict[str, str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    style = {"figure.facecolor": "#ffffff", "axes.facecolor": "#ffffff", "font.size": 11}
    chart_specs = (
        ("RQ01", "rq01_idade.png", "Repositorios por faixa de idade", "Repositorios", "#2563eb"),
        ("RQ02", "rq02_prs_aceitas.png", "Repositorios por faixa de PRs aceitas", "Repositorios", "#0f766e"),
        ("RQ06", "rq06_issues_fechadas.png", "Repositorios por percentual de issues fechadas", "Repositorios", "#d97706"),
    )
    paths: dict[str, str] = {}
    for rq, filename, title, y_label, color in chart_specs:
        distribution = analysis["results"][rq]["distribution"]
        labels = [str(item["label"]) for item in distribution]
        counts = [int(item["count"]) for item in distribution]
        with plt.rc_context(style):
            figure, axis = plt.subplots(figsize=(10.5, 4.8), layout="constrained")
            bars = axis.bar(labels, counts, color=color, width=0.68)
            axis.set_title(title, fontweight="bold", loc="left")
            axis.set_xlabel("Faixa")
            axis.set_ylabel(y_label)
            axis.spines[["top", "right"]].set_visible(False)
            axis.grid(axis="y", alpha=0.2)
            axis.set_axisbelow(True)
            axis.tick_params(axis="x", rotation=18)
            for bar, count in zip(bars, counts):
                axis.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    str(count),
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )
            path = output_dir / filename
            figure.savefig(path, dpi=150)
            plt.close(figure)
            paths[rq] = str(path.resolve())
    return paths


def run_analysis(csv_path: Path, output_dir: Path, *, save_plots: bool = True) -> tuple[dict[str, Any], Path]:
    rows = load_rows(csv_path)
    analysis = analyze_rows(rows, csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis["chart_files"] = save_charts(analysis, output_dir) if save_plots else {}
    result_path = output_dir / "sprint3_results.json"
    result_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return analysis, result_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analise e graficos da Lab01S03 para RQ01, RQ02 e RQ06")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV de 1.000 repositorios")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Diretorio dos resultados")
    parser.add_argument("--no-plots", action="store_true", help="Gera apenas o JSON de resultados")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        analysis, result_path = run_analysis(args.csv, args.output_dir, save_plots=not args.no_plots)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Erro na analise S03: {exc}") from exc
    print(f"Analise S03 salva em: {result_path}")
    for rq in analysis["scope"]:
        print(f"{rq}: {analysis['results'][rq]['conclusion']}")
    for rq, path in analysis["chart_files"].items():
        print(f"Grafico {rq}: {path}")


if __name__ == "__main__":
    main()
