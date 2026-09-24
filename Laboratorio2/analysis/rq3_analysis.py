#!/usr/bin/env python3
"""Analisa RQ3 e gera resultados e figuras reproduziveis."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import rankdata


LAB_DIR = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = LAB_DIR / "data" / "static_metrics.csv"
DEFAULT_TRIALS = LAB_DIR / "data" / "trials.csv"
DEFAULT_OUTPUT = LAB_DIR / "analysis"

PAIR_KEYS = ["participant", "kata"]
TREATMENTS = {"com_ia", "sem_ia"}
METRICS = {
    "loc": {
        "label": "LOC",
        "unit": "linhas",
        "better": "lower",
        "bounds": (1, 1_000_000),
    },
    "avg_cyclomatic_complexity": {
        "label": "Complexidade ciclomática média",
        "unit": "McCabe",
        "better": "lower",
        "bounds": (0, 100_000),
    },
    "maintainability_index": {
        "label": "Maintainability Index",
        "unit": "índice 0–100",
        "better": "higher",
        "bounds": (0, 100),
    },
    "duplication_percentage": {
        "label": "Duplicação",
        "unit": "%",
        "better": "lower",
        "bounds": (0, 100),
    },
}
REQUIRED_METRICS_COLUMNS = {"participant", "kata", "treatment", *METRICS}
REQUIRED_TRIAL_COLUMNS = {"participant", "kata", "treatment", "trial_id"}

AI_COLOR = "#087F8C"
MANUAL_COLOR = "#E76F51"
AMBER = "#E9A23B"
GREEN = "#3E8E5B"
INK = "#17232B"
MUTED = "#68777D"
GRID = "#D9E0DE"


def configure_theme() -> None:
    sns.set_theme(
        context="notebook",
        style="whitegrid",
        rc={
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "figure.facecolor": "white",
            "font.family": "DejaVu Sans",
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
        },
    )


def _validate_design(frame: pd.DataFrame, *, source: str) -> None:
    if not set(frame["treatment"]).issubset(TREATMENTS):
        invalid = sorted(set(frame["treatment"]) - TREATMENTS)
        raise ValueError(f"{source}: tratamentos invalidos: {', '.join(invalid)}.")
    if frame.duplicated(PAIR_KEYS + ["treatment"]).any():
        raise ValueError(
            f"{source}: registro duplicado para participante, kata e tratamento."
        )
    groups = frame.groupby(PAIR_KEYS, sort=True)["treatment"].agg(set)
    incomplete = groups[groups != TREATMENTS]
    if not incomplete.empty:
        labels = [" / ".join(index) for index in incomplete.index]
        raise ValueError(f"{source}: pares incompletos: {', '.join(labels)}.")
    if len(groups) != 4:
        raise ValueError(f"{source}: o desenho exige quatro pares; encontrados {len(groups)}.")
    if len(frame) != 8:
        raise ValueError(f"{source}: o desenho exige oito registros; encontrados {len(frame)}.")


def load_and_validate(metrics_path: Path, trials_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carrega os dois CSVs, valida o desenho e exige correspondencia 1:1."""
    if not metrics_path.is_file():
        raise ValueError(f"Arquivo de metricas nao encontrado: {metrics_path}")
    if not trials_path.is_file():
        raise ValueError(f"Arquivo de trials nao encontrado: {trials_path}")

    metrics = pd.read_csv(metrics_path)
    trials = pd.read_csv(trials_path)
    missing_metrics = REQUIRED_METRICS_COLUMNS - set(metrics.columns)
    missing_trials = REQUIRED_TRIAL_COLUMNS - set(trials.columns)
    if missing_metrics:
        raise ValueError(
            "Metricas: colunas obrigatorias ausentes: "
            + ", ".join(sorted(missing_metrics))
        )
    if missing_trials:
        raise ValueError(
            "Trials: colunas obrigatorias ausentes: " + ", ".join(sorted(missing_trials))
        )

    metrics = metrics.copy()
    trials = trials.copy()
    for column in METRICS:
        metrics[column] = pd.to_numeric(metrics[column], errors="raise")
        if not np.isfinite(metrics[column]).all():
            raise ValueError(f"Metricas: {column} contem valor nao finito.")
        lower, upper = METRICS[column]["bounds"]
        if not metrics[column].between(lower, upper).all():
            raise ValueError(
                f"Metricas: {column} deve estar entre {lower} e {upper}."
            )
    if not np.allclose(metrics["loc"], np.round(metrics["loc"])):
        raise ValueError("Metricas: loc deve conter numeros inteiros.")
    if metrics[["participant", "kata"]].isna().any().any():
        raise ValueError("Metricas: participante e kata nao podem ser vazios.")
    if trials["trial_id"].duplicated().any():
        raise ValueError("Trials: existem trial_ids duplicados.")

    _validate_design(metrics, source="Metricas")
    _validate_design(trials, source="Trials")

    key_columns = PAIR_KEYS + ["treatment"]
    metric_keys = set(map(tuple, metrics[key_columns].itertuples(index=False, name=None)))
    trial_keys = set(map(tuple, trials[key_columns].itertuples(index=False, name=None)))
    if metric_keys != trial_keys:
        missing = sorted(trial_keys - metric_keys)
        extra = sorted(metric_keys - trial_keys)
        details = []
        if missing:
            details.append(f"ausentes nas metricas: {missing}")
        if extra:
            details.append(f"sem trial correspondente: {extra}")
        raise ValueError("Correspondencia entre trials e metricas invalida; " + "; ".join(details))

    return (
        metrics.sort_values(key_columns).reset_index(drop=True),
        trials.sort_values(key_columns).reset_index(drop=True),
    )


def build_pairs(metrics: pd.DataFrame) -> pd.DataFrame:
    pivot = metrics.pivot(index=PAIR_KEYS, columns="treatment", values=list(METRICS))
    pivot.columns = [f"{metric}_{treatment}" for metric, treatment in pivot.columns]
    pairs = pivot.reset_index()
    pairs["pair_id"] = pairs["participant"] + " / " + pairs["kata"]
    for metric, definition in METRICS.items():
        ai = pairs[f"{metric}_com_ia"].astype(float)
        manual = pairs[f"{metric}_sem_ia"].astype(float)
        raw_delta = ai - manual
        orientation = 1.0 if definition["better"] == "higher" else -1.0
        scale = np.maximum(np.maximum(np.abs(ai), np.abs(manual)), 1e-12)
        pairs[f"{metric}_delta"] = raw_delta
        pairs[f"{metric}_oriented_delta"] = raw_delta * orientation
        pairs[f"{metric}_normalized_effect_percent"] = raw_delta * orientation / scale * 100
    return pairs.sort_values(PAIR_KEYS).reset_index(drop=True)


def descriptive_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for treatment, group in metrics.groupby("treatment", sort=True):
        for metric, definition in METRICS.items():
            values = group[metric].astype(float)
            q1 = float(values.quantile(0.25))
            q3 = float(values.quantile(0.75))
            rows.append(
                {
                    "treatment": treatment,
                    "metric": metric,
                    "label": definition["label"],
                    "unit": definition["unit"],
                    "better_when": definition["better"],
                    "n": int(values.size),
                    "median": float(values.median()),
                    "q1": q1,
                    "q3": q3,
                    "iqr": q3 - q1,
                    "minimum": float(values.min()),
                    "maximum": float(values.max()),
                }
            )
    return pd.DataFrame(rows)


def bootstrap_statistic_ci(
    values: Iterable[float],
    statistic: Any = np.median,
    *,
    resamples: int = 20_000,
    seed: int = 2026,
) -> tuple[float, float]:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        return float("nan"), float("nan")
    if np.allclose(array, array[0]):
        result = float(statistic(array))
        return result, result
    generator = np.random.default_rng(seed)
    samples = generator.choice(array, size=(resamples, array.size), replace=True)
    estimates = np.asarray([statistic(sample) for sample in samples], dtype=float)
    low, high = np.quantile(estimates, [0.025, 0.975])
    return float(low), float(high)


def rank_biserial(differences: Iterable[float]) -> float:
    """Retorna efeito orientado: positivo sempre favorece IA."""
    values = np.asarray(list(differences), dtype=float)
    nonzero = values[~np.isclose(values, 0)]
    if nonzero.size == 0:
        return 0.0
    ranks = rankdata(np.abs(nonzero), method="average")
    positive = float(ranks[nonzero > 0].sum())
    negative = float(ranks[nonzero < 0].sum())
    return (positive - negative) / (positive + negative)


def wilcoxon_exact_or_permutation(differences: Iterable[float]) -> dict[str, Any]:
    """Wilcoxon bilateral por enumeracao exata dos sinais dos pares nao nulos."""
    values = np.round(np.asarray(list(differences), dtype=float), decimals=12)
    nonzero = values[~np.isclose(values, 0)]
    zeros = int(values.size - nonzero.size)
    if nonzero.size == 0:
        return {
            "statistic": None,
            "p_value": None,
            "method": "nao aplicavel: todas as diferencas sao zero",
            "effective_pairs": 0,
            "zero_differences": zeros,
        }

    ranks = rankdata(np.abs(nonzero), method="average")
    positive = float(ranks[nonzero > 0].sum())
    negative = float(ranks[nonzero < 0].sum())
    observed = min(positive, negative)
    possible = []
    for signs in itertools.product((-1, 1), repeat=nonzero.size):
        signed = np.asarray(signs)
        w_positive = float(ranks[signed > 0].sum())
        w_negative = float(ranks[signed < 0].sum())
        possible.append(min(w_positive, w_negative))
    p_value = float(np.mean(np.asarray(possible) <= observed + 1e-12))
    has_ties = np.unique(np.abs(nonzero)).size != nonzero.size
    method = (
        "permutacao exata de sinais (empates/zeros)"
        if has_ties or zeros
        else "Wilcoxon exato"
    )
    return {
        "statistic": observed,
        "p_value": p_value,
        "method": method,
        "effective_pairs": int(nonzero.size),
        "zero_differences": zeros,
    }


def holm_adjust(p_values: dict[str, float | None]) -> dict[str, float | None]:
    valid = sorted(
        ((metric, value) for metric, value in p_values.items() if value is not None),
        key=lambda item: item[1],
    )
    adjusted: dict[str, float | None] = {metric: None for metric in p_values}
    running = 0.0
    total = len(valid)
    for index, (metric, value) in enumerate(valid):
        candidate = min(1.0, (total - index) * float(value))
        running = max(running, candidate)
        adjusted[metric] = running
    return adjusted


def inferential_summary(pairs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    p_values: dict[str, float | None] = {}
    for index, (metric, definition) in enumerate(METRICS.items()):
        raw = pairs[f"{metric}_delta"].to_numpy(dtype=float)
        oriented = pairs[f"{metric}_oriented_delta"].to_numpy(dtype=float)
        test = wilcoxon_exact_or_permutation(oriented)
        raw_low, raw_high = bootstrap_statistic_ci(raw, seed=2026 + index)
        effect_low, effect_high = bootstrap_statistic_ci(
            oriented,
            rank_biserial,
            seed=3026 + index,
        )
        p_values[metric] = test["p_value"]
        rows.append(
            {
                "metric": metric,
                "label": definition["label"],
                "unit": definition["unit"],
                "better_when": definition["better"],
                "n_pairs": int(raw.size),
                "median_delta_ai_minus_manual": float(np.median(raw)),
                "median_oriented_effect": float(np.median(oriented)),
                "bootstrap_delta_ci_low": raw_low,
                "bootstrap_delta_ci_high": raw_high,
                "wilcoxon_statistic": test["statistic"],
                "p_value_two_sided": test["p_value"],
                "holm_adjusted_p": None,
                "method": test["method"],
                "effective_pairs": test["effective_pairs"],
                "zero_differences": test["zero_differences"],
                "rank_biserial_favors_ai": rank_biserial(oriented),
                "rank_biserial_bootstrap_ci_low": effect_low,
                "rank_biserial_bootstrap_ci_high": effect_high,
                "pairs_favoring_ai": int(np.sum(oriented > 0)),
                "pairs_tied": int(np.sum(np.isclose(oriented, 0))),
                "proportion_pairs_favoring_ai": float(np.mean(oriented > 0)),
            }
        )
    adjusted = holm_adjust(p_values)
    result = pd.DataFrame(rows)
    result["holm_adjusted_p"] = result["metric"].map(adjusted)
    return result


def leave_one_pair_out(pairs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for metric, definition in METRICS.items():
        for omitted_index, omitted in pairs.iterrows():
            subset = pairs.drop(index=omitted_index)
            raw = subset[f"{metric}_delta"].to_numpy(dtype=float)
            oriented = subset[f"{metric}_oriented_delta"].to_numpy(dtype=float)
            manual_median = float(subset[f"{metric}_sem_ia"].median())
            relative = (
                float(np.median(oriented)) / max(abs(manual_median), 1e-12) * 100
            )
            rows.append(
                {
                    "metric": metric,
                    "label": definition["label"],
                    "omitted_pair": omitted["pair_id"],
                    "remaining_pairs": int(len(subset)),
                    "median_delta_ai_minus_manual": float(np.median(raw)),
                    "median_oriented_effect": float(np.median(oriented)),
                    "relative_oriented_effect_percent": relative,
                    "rank_biserial_favors_ai": rank_biserial(oriented),
                    "proportion_pairs_favoring_ai": float(np.mean(oriented > 0)),
                }
            )
    return pd.DataFrame(rows)


def save_figure(figure: plt.Figure, figures_dir: Path, stem: str) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    png_path = figures_dir / f"{stem}.png"
    svg_path = figures_dir / f"{stem}.svg"
    figure.savefig(
        png_path,
        dpi=220,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "Lab02 RQ3 analysis"},
    )
    figure.savefig(
        svg_path,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Date": None, "Creator": "Lab02 RQ3 analysis"},
    )
    svg_lines = svg_path.read_text(encoding="utf-8").splitlines()
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_lines) + "\n", encoding="utf-8"
    )
    plt.close(figure)


def short_pair_label(row: pd.Series) -> str:
    return f"{str(row['participant']).capitalize()} · {str(row['kata']).replace('kata_', 'K')}"


def plot_paired_small_multiples(pairs: pd.DataFrame, figures_dir: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.8, 9.1), layout="constrained")
    for axis, (metric, definition) in zip(axes.flat, METRICS.items()):
        for _, row in pairs.iterrows():
            manual = row[f"{metric}_sem_ia"]
            ai = row[f"{metric}_com_ia"]
            axis.plot([0, 1], [manual, ai], color="#AAB5B2", linewidth=1.6, zorder=1)
            axis.scatter(0, manual, s=65, color=MANUAL_COLOR, edgecolor="white", zorder=3)
            axis.scatter(1, ai, s=65, color=AI_COLOR, edgecolor="white", zorder=3)
        axis.scatter(
            [0, 1],
            [pairs[f"{metric}_sem_ia"].median(), pairs[f"{metric}_com_ia"].median()],
            marker="D",
            s=85,
            color=INK,
            edgecolor="white",
            zorder=4,
        )
        axis.set_xticks([0, 1], ["Sem IA", "Com IA"])
        axis.set_ylabel(definition["unit"])
        arrow = "↓ menor é melhor" if definition["better"] == "lower" else "↑ maior é melhor"
        axis.set_title(f"{definition['label']}  ·  {arrow}", loc="left")
        axis.grid(axis="x", visible=False)
    figure.suptitle("RQ3 · Comparações pareadas da estrutura do código", fontsize=20, weight="bold")
    figure.text(
        0.01,
        -0.015,
        "Cada linha liga a mesma combinação participante–kata; losangos mostram as medianas.",
        color=MUTED,
        fontsize=9.5,
    )
    save_figure(figure, figures_dir, "rq3_paired_metrics")


def plot_loc_complexity(pairs: pd.DataFrame, figures_dir: Path) -> None:
    figure, axis = plt.subplots(figsize=(10.8, 7.0), layout="constrained")
    for _, row in pairs.iterrows():
        x0, y0 = row["loc_sem_ia"], row["avg_cyclomatic_complexity_sem_ia"]
        x1, y1 = row["loc_com_ia"], row["avg_cyclomatic_complexity_com_ia"]
        axis.annotate(
            "",
            xy=(x1, y1),
            xytext=(x0, y0),
            arrowprops={"arrowstyle": "-|>", "color": "#91A09C", "lw": 1.8},
        )
        axis.scatter(x0, y0, s=90, color=MANUAL_COLOR, edgecolor="white", zorder=3)
        axis.scatter(x1, y1, s=90, color=AI_COLOR, edgecolor="white", zorder=3)
        axis.annotate(
            short_pair_label(row),
            (x1, y1),
            xytext=(7, 6),
            textcoords="offset points",
            fontsize=8.5,
            color=INK,
        )
    axis.scatter([], [], color=MANUAL_COLOR, label="Sem IA")
    axis.scatter([], [], color=AI_COLOR, label="Com IA")
    axis.set_xlabel("LOC · menor é melhor")
    axis.set_ylabel("Complexidade ciclomática média · menor é melhor")
    axis.set_title("RQ3 · LOC versus complexidade", loc="left", fontsize=18, y=1.07)
    axis.text(
        0.01,
        1.015,
        "As setas partem da solução manual e apontam para a solução com IA.",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9.5,
    )
    axis.legend(frameon=False)
    save_figure(figure, figures_dir, "rq3_loc_vs_complexity")


def plot_difference_heatmap(pairs: pd.DataFrame, figures_dir: Path) -> None:
    columns = [f"{metric}_normalized_effect_percent" for metric in METRICS]
    heatmap = pairs[columns].copy()
    heatmap.columns = [definition["label"] for definition in METRICS.values()]
    heatmap.index = [short_pair_label(row) for _, row in pairs.iterrows()]
    limit = max(100.0, float(np.nanmax(np.abs(heatmap.to_numpy()))))
    figure, axis = plt.subplots(figsize=(12.2, 5.6), layout="constrained")
    sns.heatmap(
        heatmap,
        ax=axis,
        cmap=sns.diverging_palette(18, 155, s=80, l=48, as_cmap=True),
        center=0,
        vmin=-limit,
        vmax=limit,
        annot=True,
        fmt=".1f",
        linewidths=1,
        linecolor="white",
        cbar_kws={"label": "Efeito normalizado (%); positivo favorece IA"},
    )
    axis.set_xlabel("")
    axis.set_ylabel("")
    axis.set_title("RQ3 · Direção e magnitude por par", loc="left", fontsize=18, y=1.1)
    axis.text(
        0,
        1.025,
        "A escala usa a maior magnitude do par como denominador; verde favorece IA e laranja favorece manual.",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9.2,
    )
    save_figure(figure, figures_dir, "rq3_difference_heatmap")


def plot_forest(inference: pd.DataFrame, figures_dir: Path) -> None:
    ordered = inference.reset_index(drop=True)
    positions = np.arange(len(ordered))
    figure, axis = plt.subplots(figsize=(10.7, 6.2), layout="constrained")
    for position, row in ordered.iterrows():
        low = row["rank_biserial_bootstrap_ci_low"]
        high = row["rank_biserial_bootstrap_ci_high"]
        effect = row["rank_biserial_favors_ai"]
        axis.hlines(position, low, high, color="#8A9995", linewidth=3)
        axis.scatter(effect, position, marker="D", s=95, color=AI_COLOR, edgecolor="white", zorder=3)
        axis.text(min(high + 0.05, 1.02), position, f"r={effect:.2f}", va="center", fontsize=8.5)
    axis.axvline(0, color=INK, linewidth=1.1)
    axis.set_xlim(-1.12, 1.12)
    axis.set_yticks(positions, ordered["label"])
    axis.invert_yaxis()
    axis.set_xlabel("Correlação bisserial de postos (positivo favorece IA)")
    axis.set_title("RQ3 · Efeitos observados", loc="left", fontsize=18, y=1.09)
    axis.text(
        0.01,
        1.025,
        "Barras: IC bootstrap exploratório de 95%; n=4 não sustenta precisão inferencial.",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9.5,
    )
    axis.grid(axis="y", visible=False)
    save_figure(figure, figures_dir, "rq3_forest_effects")


def plot_leave_one_out(loo: pd.DataFrame, figures_dir: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13.0, 8.7), layout="constrained")
    for axis, (metric, definition) in zip(axes.flat, METRICS.items()):
        subset = loo[loo["metric"] == metric].reset_index(drop=True)
        positions = np.arange(len(subset))
        values = subset["relative_oriented_effect_percent"]
        colors = [AI_COLOR if value > 0 else MANUAL_COLOR if value < 0 else MUTED for value in values]
        axis.barh(positions, values, color=colors, height=0.62)
        axis.axvline(0, color=INK, linewidth=1)
        axis.set_yticks(positions, subset["omitted_pair"].str.replace("kata_", "K", regex=False))
        axis.invert_yaxis()
        axis.set_xlabel("Efeito mediano orientado / mediana manual (%)")
        axis.set_title(definition["label"], loc="left")
        axis.grid(axis="y", visible=False)
    figure.suptitle("RQ3 · Sensibilidade leave-one-pair-out", fontsize=20, weight="bold")
    figure.text(
        0.01,
        -0.015,
        "Cada barra recalcula o efeito após remover o par indicado; valores positivos favorecem IA.",
        color=MUTED,
        fontsize=9.5,
    )
    save_figure(figure, figures_dir, "rq3_leave_one_out")


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"Tipo nao serializavel: {type(value)!r}")


def rounded(value: Any) -> float:
    return round(float(value), 6)


def write_results(
    metrics_path: Path,
    trials_path: Path,
    metrics: pd.DataFrame,
    trials: pd.DataFrame,
    pairs: pd.DataFrame,
    descriptive: pd.DataFrame,
    inference: pd.DataFrame,
    loo: pd.DataFrame,
    output_dir: Path,
) -> None:
    results_dir = output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(results_dir / "rq3_pairs.csv", index=False, float_format="%.6f")
    descriptive.to_csv(results_dir / "rq3_descriptive.csv", index=False, float_format="%.6f")
    inference.to_csv(results_dir / "rq3_inference.csv", index=False, float_format="%.6f")
    loo.to_csv(results_dir / "rq3_leave_one_out.csv", index=False, float_format="%.6f")

    summary_metrics: dict[str, Any] = {}
    for metric, definition in METRICS.items():
        row = inference[inference["metric"] == metric].iloc[0]
        by_treatment = descriptive[descriptive["metric"] == metric].set_index("treatment")
        summary_metrics[metric] = {
            "label": definition["label"],
            "unit": definition["unit"],
            "better_when": definition["better"],
            "median_com_ia": rounded(by_treatment.loc["com_ia", "median"]),
            "median_sem_ia": rounded(by_treatment.loc["sem_ia", "median"]),
            "median_delta_ai_minus_manual": rounded(row["median_delta_ai_minus_manual"]),
            "bootstrap_delta_ci": [
                rounded(row["bootstrap_delta_ci_low"]),
                rounded(row["bootstrap_delta_ci_high"]),
            ],
            "wilcoxon_statistic": (
                None if pd.isna(row["wilcoxon_statistic"]) else rounded(row["wilcoxon_statistic"])
            ),
            "p_value_two_sided": (
                None if pd.isna(row["p_value_two_sided"]) else rounded(row["p_value_two_sided"])
            ),
            "holm_adjusted_p": (
                None if pd.isna(row["holm_adjusted_p"]) else rounded(row["holm_adjusted_p"])
            ),
            "method": row["method"],
            "rank_biserial_favors_ai": rounded(row["rank_biserial_favors_ai"]),
            "pairs_favoring_ai": int(row["pairs_favoring_ai"]),
            "pairs_tied": int(row["pairs_tied"]),
            "proportion_pairs_favoring_ai": rounded(row["proportion_pairs_favoring_ai"]),
        }
    summary = {
        "sources": {
            "static_metrics": {
                "path": metrics_path.relative_to(LAB_DIR).as_posix(),
                "sha256": hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
                "records": int(len(metrics)),
            },
            "trials": {
                "path": trials_path.relative_to(LAB_DIR).as_posix(),
                "sha256": hashlib.sha256(trials_path.read_bytes()).hexdigest(),
                "records": int(len(trials)),
            },
            "pairs": int(len(pairs)),
        },
        "analysis": {
            "difference_definition": "com_ia menos sem_ia",
            "effect_orientation": "positivo favorece IA",
            "bootstrap_resamples": 20_000,
            "holm_correction": "exploratoria para quatro metricas",
        },
        "metrics": summary_metrics,
        "figures": [
            "rq3_paired_metrics",
            "rq3_loc_vs_complexity",
            "rq3_difference_heatmap",
            "rq3_forest_effects",
            "rq3_leave_one_out",
        ],
    }
    (results_dir / "rq3_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def run_analysis(metrics_path: Path, trials_path: Path, output_dir: Path) -> dict[str, Path]:
    configure_theme()
    metrics, trials = load_and_validate(metrics_path, trials_path)
    pairs = build_pairs(metrics)
    descriptive = descriptive_summary(metrics)
    inference = inferential_summary(pairs)
    loo = leave_one_pair_out(pairs)
    figures_dir = output_dir / "figures"
    plot_paired_small_multiples(pairs, figures_dir)
    plot_loc_complexity(pairs, figures_dir)
    plot_difference_heatmap(pairs, figures_dir)
    plot_forest(inference, figures_dir)
    plot_leave_one_out(loo, figures_dir)
    write_results(
        metrics_path,
        trials_path,
        metrics,
        trials,
        pairs,
        descriptive,
        inference,
        loo,
        output_dir,
    )
    return {"figures": figures_dir, "results": output_dir / "results"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Analisa RQ3 do Lab02.")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--trials", type=Path, default=DEFAULT_TRIALS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    outputs = run_analysis(
        args.metrics.resolve(), args.trials.resolve(), args.output_dir.resolve()
    )
    print("Analise RQ3 concluida.")
    print(f"Resultados: {outputs['results']}")
    print(f"Figuras: {outputs['figures']}")


if __name__ == "__main__":
    main()
