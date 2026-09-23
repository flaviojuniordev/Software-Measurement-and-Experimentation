#!/usr/bin/env python3
"""Analisa RQ1 e RQ2 e gera tabelas e figuras reproduziveis."""

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
from matplotlib import patches
from scipy.stats import PermutationMethod, rankdata, wilcoxon


LAB_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TRIALS = LAB_DIR / "data" / "trials.csv"
DEFAULT_OUTPUT = LAB_DIR / "analysis"

AI_COLOR = "#087F8C"
MANUAL_COLOR = "#E76F51"
AMBER = "#E9A23B"
GREEN = "#3E8E5B"
INK = "#17232B"
MUTED = "#68777D"
GRID = "#D9E0DE"
PALE = "#EFF3F2"

REQUIRED_COLUMNS = {
    "trial_id",
    "participant",
    "kata",
    "treatment",
    "timebox_minutes",
    "time_to_green_seconds",
    "censored",
    "tests_passed",
    "tests_failed",
    "success_rate",
}
NUMERIC_COLUMNS = {
    "timebox_minutes",
    "time_to_green_seconds",
    "tests_passed",
    "tests_failed",
    "success_rate",
}
PAIR_KEYS = ["participant", "kata"]


def configure_theme() -> None:
    sns.set_theme(
        context="notebook",
        style="whitegrid",
        rc={
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "axes.titlesize": 15,
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


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "sim"}:
        return True
    if normalized in {"false", "0", "no", "nao", "não", ""}:
        return False
    raise ValueError(f"Valor booleano invalido: {value!r}")


def load_trials(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise ValueError(f"Arquivo de trials nao encontrado: {path}")

    trials = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(trials.columns)
    if missing:
        raise ValueError(f"Colunas obrigatorias ausentes: {', '.join(sorted(missing))}")

    trials = trials.copy()
    for column in NUMERIC_COLUMNS:
        trials[column] = pd.to_numeric(trials[column], errors="raise")
    trials["censored"] = trials["censored"].map(parse_bool)

    if not set(trials["treatment"]).issubset({"com_ia", "sem_ia"}):
        raise ValueError("Tratamento invalido: use somente com_ia ou sem_ia.")
    if trials["trial_id"].duplicated().any():
        raise ValueError("Existem trial_ids duplicados.")
    if trials.duplicated(PAIR_KEYS + ["treatment"]).any():
        raise ValueError("Existe mais de um trial para o mesmo participante, kata e tratamento.")
    if (trials[list(NUMERIC_COLUMNS)] < 0).any().any():
        raise ValueError("Metricas numericas nao podem ser negativas.")
    if not trials["success_rate"].between(0, 1).all():
        raise ValueError("success_rate deve estar entre 0 e 1.")

    treatment_counts = trials.groupby(PAIR_KEYS)["treatment"].agg(set)
    incomplete = treatment_counts[treatment_counts != {"com_ia", "sem_ia"}]
    if not incomplete.empty:
        labels = [" / ".join(index) for index in incomplete.index]
        raise ValueError(f"Pares incompletos: {', '.join(labels)}")
    if len(treatment_counts) != 4:
        raise ValueError(f"O desenho exige quatro pares; foram encontrados {len(treatment_counts)}.")

    cap_seconds = trials["timebox_minutes"] * 60
    trials["analysis_time_seconds"] = np.where(
        trials["censored"], cap_seconds, trials["time_to_green_seconds"]
    )
    trials["success_rate_percent"] = trials["success_rate"] * 100
    return trials.sort_values(PAIR_KEYS + ["treatment"]).reset_index(drop=True)


def build_pairs(trials: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "analysis_time_seconds",
        "success_rate",
        "success_rate_percent",
        "tests_passed",
        "tests_failed",
        "censored",
    ]
    pivot = trials.pivot(index=PAIR_KEYS, columns="treatment", values=metrics)
    pivot.columns = [f"{metric}_{treatment}" for metric, treatment in pivot.columns]
    pairs = pivot.reset_index()
    pairs["pair_id"] = pairs["participant"] + " / " + pairs["kata"]
    pairs["time_delta_seconds"] = (
        pairs["analysis_time_seconds_com_ia"] - pairs["analysis_time_seconds_sem_ia"]
    )
    pairs["time_reduction_percent"] = (
        (pairs["analysis_time_seconds_sem_ia"] - pairs["analysis_time_seconds_com_ia"])
        / pairs["analysis_time_seconds_sem_ia"]
        * 100
    )
    pairs["speedup"] = (
        pairs["analysis_time_seconds_sem_ia"] / pairs["analysis_time_seconds_com_ia"]
    )
    pairs["success_rate_delta"] = (
        pairs["success_rate_com_ia"] - pairs["success_rate_sem_ia"]
    )
    pairs["tests_failed_delta"] = (
        pairs["tests_failed_com_ia"] - pairs["tests_failed_sem_ia"]
    )
    return pairs.sort_values(PAIR_KEYS).reset_index(drop=True)


def descriptive_summary(trials: pd.DataFrame) -> pd.DataFrame:
    definitions = {
        "analysis_time_seconds": "segundos",
        "success_rate_percent": "percentual",
        "tests_failed": "testes",
        "tests_passed": "testes",
    }
    rows: list[dict[str, Any]] = []
    for treatment, group in trials.groupby("treatment", sort=True):
        for metric, unit in definitions.items():
            values = group[metric].astype(float)
            q1 = values.quantile(0.25)
            q3 = values.quantile(0.75)
            rows.append(
                {
                    "treatment": treatment,
                    "metric": metric,
                    "unit": unit,
                    "n": int(values.count()),
                    "median": float(values.median()),
                    "q1": float(q1),
                    "q3": float(q3),
                    "iqr": float(q3 - q1),
                    "minimum": float(values.min()),
                    "maximum": float(values.max()),
                    "censored_trials": int(group["censored"].sum()),
                }
            )
    return pd.DataFrame(rows)


def bootstrap_median_ci(
    values: Iterable[float], *, resamples: int = 20_000, seed: int = 2026
) -> tuple[float, float]:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        return float("nan"), float("nan")
    if np.allclose(array, array[0]):
        return float(array[0]), float(array[0])
    generator = np.random.default_rng(seed)
    samples = generator.choice(array, size=(resamples, array.size), replace=True)
    medians = np.median(samples, axis=1)
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def rank_biserial(differences: Iterable[float]) -> float:
    values = np.asarray(list(differences), dtype=float)
    nonzero = values[~np.isclose(values, 0)]
    if nonzero.size == 0:
        return 0.0
    ranks = rankdata(np.abs(nonzero), method="average")
    positive = float(ranks[nonzero > 0].sum())
    negative = float(ranks[nonzero < 0].sum())
    return (positive - negative) / (positive + negative)


def wilcoxon_result(
    differences: Iterable[float], *, alternative: str, seed: int = 2026
) -> dict[str, Any]:
    values = np.round(np.asarray(list(differences), dtype=float), decimals=9)
    nonzero = values[~np.isclose(values, 0)]
    if nonzero.size == 0:
        return {
            "statistic": 0.0,
            "p_value": 1.0,
            "method": "nao aplicavel: todas as diferencas sao zero",
            "effective_pairs": 0,
        }

    has_ties = np.unique(np.abs(nonzero)).size != nonzero.size
    if has_ties:
        method: str | PermutationMethod = PermutationMethod(
            n_resamples=100_000, random_state=seed
        )
        method_label = "permutacao exaustiva/deterministica"
    else:
        method = "exact"
        method_label = "Wilcoxon exato"

    result = wilcoxon(
        nonzero,
        zero_method="wilcox",
        alternative=alternative,
        method=method,
    )
    return {
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "method": method_label,
        "effective_pairs": int(nonzero.size),
    }


def inferential_summary(pairs: pd.DataFrame) -> pd.DataFrame:
    analyses = [
        {
            "question": "RQ1",
            "metric": "time_to_green_seconds",
            "differences": pairs["time_delta_seconds"],
            "directional_alternative": "less",
            "better_when": "negative",
        },
        {
            "question": "RQ2",
            "metric": "success_rate",
            "differences": pairs["success_rate_delta"],
            "directional_alternative": "greater",
            "better_when": "positive",
        },
        {
            "question": "RQ2",
            "metric": "tests_failed",
            "differences": pairs["tests_failed_delta"],
            "directional_alternative": "less",
            "better_when": "negative",
        },
    ]
    rows: list[dict[str, Any]] = []
    for analysis in analyses:
        differences = np.asarray(analysis["differences"], dtype=float)
        two_sided = wilcoxon_result(differences, alternative="two-sided")
        directional = wilcoxon_result(
            differences, alternative=str(analysis["directional_alternative"])
        )
        ci_low, ci_high = bootstrap_median_ci(differences)
        if analysis["better_when"] == "negative":
            favorable = float(
                (np.sum(differences < 0) + 0.5 * np.sum(np.isclose(differences, 0)))
                / differences.size
            )
        else:
            favorable = float(
                (np.sum(differences > 0) + 0.5 * np.sum(np.isclose(differences, 0)))
                / differences.size
            )
        rows.append(
            {
                "question": analysis["question"],
                "metric": analysis["metric"],
                "n_pairs": int(differences.size),
                "median_delta_ai_minus_manual": float(np.median(differences)),
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "wilcoxon_statistic": two_sided["statistic"],
                "p_value_two_sided": two_sided["p_value"],
                "p_value_directional": directional["p_value"],
                "directional_alternative": analysis["directional_alternative"],
                "method": two_sided["method"],
                "effective_pairs": two_sided["effective_pairs"],
                "rank_biserial_ai_minus_manual": rank_biserial(differences),
                "probability_pair_favors_ai": favorable,
            }
        )
    return pd.DataFrame(rows)


def sign_flip_distribution(differences: Iterable[float]) -> tuple[np.ndarray, float, float]:
    observed_values = np.asarray(list(differences), dtype=float)
    ranks = rankdata(np.abs(observed_values), method="average")
    distribution = np.asarray(
        [
            np.sum(ranks * np.asarray(signs))
            for signs in itertools.product((-1, 1), repeat=ranks.size)
        ],
        dtype=float,
    )
    observed = float(np.sum(ranks * np.sign(observed_values)))
    p_value = float(np.mean(np.abs(distribution) >= abs(observed) - 1e-12))
    return distribution, observed, p_value


def save_figure(figure: plt.Figure, figures_dir: Path, stem: str) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    svg_path = figures_dir / f"{stem}.svg"
    figure.savefig(
        figures_dir / f"{stem}.png",
        dpi=220,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "Lab02 RQ1/RQ2 analysis"},
    )
    figure.savefig(
        svg_path,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Date": None, "Creator": "Lab02 RQ1/RQ2 analysis"},
    )
    svg_lines = svg_path.read_text(encoding="utf-8").splitlines()
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_lines) + "\n",
        encoding="utf-8",
    )
    plt.close(figure)


def short_pair_label(row: pd.Series) -> str:
    participant = str(row["participant"]).capitalize()
    kata = str(row["kata"]).replace("kata_", "K")
    return f"{participant} · {kata}"


def plot_paired_estimation(pairs: pd.DataFrame, figures_dir: Path) -> None:
    figure = plt.figure(figsize=(12.8, 6.8), layout="constrained")
    grid = figure.add_gridspec(1, 2, width_ratios=[1.05, 1.3])
    raw_axis = figure.add_subplot(grid[0, 0])
    delta_axis = figure.add_subplot(grid[0, 1])

    for _, row in pairs.iterrows():
        manual = row["analysis_time_seconds_sem_ia"] / 60
        ai = row["analysis_time_seconds_com_ia"] / 60
        raw_axis.plot([0, 1], [manual, ai], color="#AAB5B2", linewidth=1.5, zorder=1)
        raw_axis.scatter(0, manual, s=75, color=MANUAL_COLOR, edgecolor="white", zorder=3)
        raw_axis.scatter(1, ai, s=75, color=AI_COLOR, edgecolor="white", zorder=3)

    manual_median = pairs["analysis_time_seconds_sem_ia"].median() / 60
    ai_median = pairs["analysis_time_seconds_com_ia"].median() / 60
    raw_axis.scatter(
        [0, 1],
        [manual_median, ai_median],
        marker="D",
        s=95,
        color=INK,
        edgecolor="white",
        zorder=4,
        label="Mediana",
    )
    raw_axis.axhline(35, color=AMBER, linestyle=(0, (4, 4)), linewidth=1.2)
    raw_axis.text(0.02, 35.8, "time-box 35 min", color=AMBER, fontsize=8.5)
    raw_axis.set_yscale("log")
    raw_axis.set_xticks([0, 1], ["Sem IA", "Com IA"])
    raw_axis.set_ylabel("Tempo ate todos os testes passarem (min, escala log)")
    raw_axis.set_title("Cada linha e o mesmo participante e kata", loc="left")
    raw_axis.legend(frameon=False, loc="lower left")
    raw_axis.grid(axis="x", visible=False)

    deltas_minutes = pairs["time_delta_seconds"] / 60
    positions = np.arange(len(pairs))
    delta_axis.hlines(positions, 0, deltas_minutes, color="#BCC5C3", linewidth=2)
    delta_axis.scatter(deltas_minutes, positions, s=85, color=AI_COLOR, zorder=3)
    for position, (_, row) in zip(positions, pairs.iterrows()):
        delta = row["time_delta_seconds"] / 60
        delta_axis.annotate(
            f"{delta:.1f} min",
            (delta, position),
            xytext=(8, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=8.5,
            color=INK,
        )
    ci_low, ci_high = bootstrap_median_ci(deltas_minutes)
    median_delta = float(np.median(deltas_minutes))
    summary_position = len(pairs) + 0.45
    delta_axis.hlines(summary_position, ci_low, ci_high, color=INK, linewidth=3)
    delta_axis.scatter(median_delta, summary_position, marker="D", s=105, color=INK, zorder=4)
    delta_axis.text(
        ci_high + 0.35,
        summary_position,
        "mediana + IC bootstrap exploratorio",
        va="center",
        fontsize=8.5,
        color=MUTED,
    )
    delta_axis.axvline(0, color=INK, linewidth=1.1)
    delta_axis.set_yticks(positions, [short_pair_label(row) for _, row in pairs.iterrows()])
    delta_axis.set_ylim(-0.7, summary_position + 0.7)
    delta_axis.invert_yaxis()
    delta_axis.set_xlabel("Diferenca com IA - sem IA (min); valores negativos favorecem IA")
    delta_axis.set_title("Reducao pareada observada", loc="left")
    delta_axis.grid(axis="y", visible=False)

    figure.suptitle("RQ1 · Estimativa pareada do tempo de resolucao", fontsize=20, weight="bold")
    figure.text(
        0.01,
        -0.025,
        "Todos os quatro pares favoreceram o tratamento com IA. O intervalo bootstrap e descritivo devido a n=4.",
        color=MUTED,
        fontsize=9,
    )
    save_figure(figure, figures_dir, "rq1_paired_estimation")


def plot_speedup(pairs: pd.DataFrame, figures_dir: Path) -> None:
    ordered = pairs.sort_values("speedup").reset_index(drop=True)
    positions = np.arange(len(ordered))
    figure, axis = plt.subplots(figsize=(10.8, 5.8), layout="constrained")
    axis.hlines(positions, 1, ordered["speedup"], color="#B8C3C0", linewidth=3)
    axis.scatter(ordered["speedup"], positions, s=130, color=AI_COLOR, edgecolor="white", zorder=3)
    for position, (_, row) in zip(positions, ordered.iterrows()):
        axis.text(
            row["speedup"] * 1.045,
            position,
            f"{row['speedup']:.1f}x",
            va="center",
            weight="bold",
            color=INK,
        )
    median_speedup = float(ordered["speedup"].median())
    axis.axvline(1, color=MANUAL_COLOR, linewidth=1.2, linestyle=(0, (4, 4)))
    axis.axvline(median_speedup, color=INK, linewidth=1.2, linestyle=(0, (2, 3)))
    axis.text(median_speedup, len(ordered) - 0.15, f" mediana {median_speedup:.1f}x", color=INK)
    axis.set_xscale("log")
    axis.set_xlim(0.8, max(ordered["speedup"]) * 1.35)
    axis.set_yticks(positions, [short_pair_label(row) for _, row in ordered.iterrows()])
    axis.set_xlabel("Speedup = tempo sem IA / tempo com IA (escala log)")
    axis.set_title(
        "RQ1 · Ganho de velocidade em cada par", loc="left", fontsize=18, y=1.09
    )
    axis.text(
        0.01,
        1.025,
        "1x indica empate; valores a direita indicam resolucao mais rapida com IA.",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9.5,
    )
    axis.grid(axis="y", visible=False)
    save_figure(figure, figures_dir, "rq1_speedup")


def plot_timebox(trials: pd.DataFrame, figures_dir: Path) -> None:
    ordered = trials.sort_values(PAIR_KEYS + ["treatment"], ascending=[True, True, False]).copy()
    ordered["minutes"] = ordered["analysis_time_seconds"] / 60
    ordered["cap_minutes"] = ordered["timebox_minutes"]
    positions = np.arange(len(ordered))
    colors = ordered["treatment"].map({"com_ia": AI_COLOR, "sem_ia": MANUAL_COLOR})

    figure, axis = plt.subplots(figsize=(11.5, 7.1), layout="constrained")
    axis.barh(positions, ordered["cap_minutes"], color=PALE, height=0.62)
    axis.barh(positions, ordered["minutes"], color=colors, height=0.62)
    for position, (_, row) in zip(positions, ordered.iterrows()):
        axis.text(
            min(row["minutes"] + 0.45, 33.2),
            position,
            f"{row['minutes']:.2f} min",
            va="center",
            fontsize=8.5,
            color=INK,
        )
        if row["censored"]:
            axis.scatter(row["cap_minutes"], position, marker=">", s=75, color=AMBER, zorder=4)
    labels = [
        f"{row.participant.capitalize()} · {row.kata.replace('kata_', 'K')} · "
        f"{'Com IA' if row.treatment == 'com_ia' else 'Sem IA'}"
        for row in ordered.itertuples()
    ]
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlim(0, 36)
    axis.set_xlabel("Minutos observados dentro do time-box")
    axis.set_title(
        "RQ1 · Distancia ate o limite de 35 minutos", loc="left", fontsize=18, y=1.09
    )
    axis.text(
        0.01,
        1.025,
        "Fundo cinza = janela disponivel; triangulo ambar = observacao censurada.",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9.5,
    )
    axis.grid(axis="y", visible=False)
    save_figure(figure, figures_dir, "rq1_timebox")


def plot_rq2_outcomes(trials: pd.DataFrame, figures_dir: Path) -> None:
    ordered_pairs = trials[PAIR_KEYS].drop_duplicates().sort_values(PAIR_KEYS).reset_index(drop=True)
    figure, axis = plt.subplots(figsize=(9.8, 6.2), layout="constrained")
    axis.set_xlim(-0.65, 2.25)
    axis.set_ylim(-0.65, len(ordered_pairs) - 0.35)

    for row_index, pair in ordered_pairs.iterrows():
        subset = trials[
            (trials["participant"] == pair["participant"])
            & (trials["kata"] == pair["kata"])
        ].set_index("treatment")
        for column_index, treatment in enumerate(("sem_ia", "com_ia")):
            trial = subset.loc[treatment]
            rate = float(trial["success_rate"])
            color = GREEN if rate == 1 and trial["tests_failed"] == 0 else AMBER
            tile = patches.FancyBboxPatch(
                (column_index - 0.4, row_index - 0.32),
                0.8,
                0.64,
                boxstyle="round,pad=0.02,rounding_size=0.04",
                linewidth=1.2,
                edgecolor="white",
                facecolor=color,
            )
            axis.add_patch(tile)
            total = int(trial["tests_passed"] + trial["tests_failed"])
            axis.text(
                column_index,
                row_index - 0.04,
                f"{int(trial['tests_passed'])}/{total}",
                ha="center",
                va="center",
                color="white",
                fontsize=14,
                weight="bold",
            )
            axis.text(
                column_index,
                row_index + 0.18,
                f"{rate * 100:.0f}% · {int(trial['tests_failed'])} falhas",
                ha="center",
                va="center",
                color="white",
                fontsize=8,
            )
    axis.set_xticks([0, 1], ["Sem IA", "Com IA"])
    axis.xaxis.tick_top()
    axis.set_yticks(
        np.arange(len(ordered_pairs)),
        [short_pair_label(row) for _, row in ordered_pairs.iterrows()],
    )
    axis.invert_yaxis()
    axis.grid(False)
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.set_title(
        "RQ2 · Resultado funcional ao final do time-box",
        loc="left",
        fontsize=18,
        y=1.16,
    )
    axis.text(
        0,
        1.075,
        "8/8 trials verdes; nao houve variacao observada em defeitos entre os tratamentos.",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9.5,
    )
    save_figure(figure, figures_dir, "rq2_outcomes")


def plot_exact_permutations(pairs: pd.DataFrame, figures_dir: Path) -> None:
    distribution, observed, p_value = sign_flip_distribution(pairs["time_delta_seconds"])
    ordered = np.sort(distribution)
    offsets = (np.arange(ordered.size) % 4 - 1.5) * 0.055

    figure, axis = plt.subplots(figsize=(11.2, 5.5), layout="constrained")
    extreme = np.abs(ordered) >= abs(observed) - 1e-12
    axis.scatter(
        ordered[~extreme],
        offsets[~extreme],
        s=85,
        color="#AEB9B6",
        edgecolor="white",
        label="Resultado possivel sob H0",
    )
    axis.scatter(
        ordered[extreme],
        offsets[extreme],
        s=115,
        color=AMBER,
        edgecolor="white",
        label="Tao extremo quanto o observado",
        zorder=3,
    )
    axis.scatter(observed, 0.27, marker="*", s=260, color=MANUAL_COLOR, edgecolor="white", zorder=4)
    axis.axvline(0, color=INK, linewidth=1.1)
    axis.annotate(
        f"escore observado: {observed:.0f}",
        (observed, 0.27),
        xytext=(12, 12),
        textcoords="offset points",
        fontsize=9,
        weight="bold",
        color=INK,
    )
    axis.set_ylim(-0.4, 0.55)
    axis.set_yticks([])
    axis.set_xlabel("Soma assinada dos postos de Wilcoxon")
    axis.set_title(
        "RQ1 · Os 16 mundos possiveis sob a hipotese nula",
        loc="left",
        fontsize=18,
        y=1.09,
    )
    axis.text(
        0.01,
        1.025,
        f"Com quatro pares, o resultado bilateral exato e p={p_value:.3f}; a resolucao inferencial e limitada.",
        transform=axis.transAxes,
        color=MUTED,
        fontsize=9.5,
    )
    axis.legend(frameon=False, loc="lower right", ncol=2)
    axis.grid(axis="y", visible=False)
    save_figure(figure, figures_dir, "rq1_exact_permutations")


def json_value(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    raise TypeError(f"Tipo nao serializavel: {type(value)!r}")


def write_results(
    trials_path: Path,
    trials: pd.DataFrame,
    pairs: pd.DataFrame,
    descriptive: pd.DataFrame,
    inferential: pd.DataFrame,
    output_dir: Path,
) -> None:
    results_dir = output_dir / "results"
    figures_dir = output_dir / "figures"
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    pairs.to_csv(results_dir / "rq1_rq2_pairs.csv", index=False, float_format="%.6f")
    descriptive.to_csv(
        results_dir / "rq1_rq2_descriptive.csv", index=False, float_format="%.6f"
    )
    inferential.to_csv(
        results_dir / "rq1_rq2_inference.csv", index=False, float_format="%.6f"
    )

    time_row = inferential[inferential["metric"] == "time_to_green_seconds"].iloc[0]
    success_row = inferential[inferential["metric"] == "success_rate"].iloc[0]
    summary = {
        "source": {
            "path": str(trials_path.relative_to(LAB_DIR)),
            "sha256": hashlib.sha256(trials_path.read_bytes()).hexdigest(),
            "trials": int(len(trials)),
            "pairs": int(len(pairs)),
        },
        "rq1": {
            "median_time_com_ia_seconds": float(
                trials.loc[trials["treatment"] == "com_ia", "analysis_time_seconds"].median()
            ),
            "median_time_sem_ia_seconds": float(
                trials.loc[trials["treatment"] == "sem_ia", "analysis_time_seconds"].median()
            ),
            "median_delta_seconds": float(pairs["time_delta_seconds"].median()),
            "median_reduction_percent": float(pairs["time_reduction_percent"].median()),
            "median_speedup": float(pairs["speedup"].median()),
            "pairs_favoring_ai": int((pairs["time_delta_seconds"] < 0).sum()),
            "p_value_two_sided": float(time_row["p_value_two_sided"]),
            "p_value_directional": float(time_row["p_value_directional"]),
            "rank_biserial_ai_minus_manual": float(
                time_row["rank_biserial_ai_minus_manual"]
            ),
            "interpretation": (
                "Os quatro pares foram mais rapidos com IA, com efeito observado grande, "
                "mas n=4 limita a significancia do Wilcoxon bilateral."
            ),
        },
        "rq2": {
            "green_trials": int(
                ((trials["tests_failed"] == 0) & (trials["tests_passed"] > 0)).sum()
            ),
            "median_success_com_ia_percent": float(
                trials.loc[trials["treatment"] == "com_ia", "success_rate_percent"].median()
            ),
            "median_success_sem_ia_percent": float(
                trials.loc[trials["treatment"] == "sem_ia", "success_rate_percent"].median()
            ),
            "p_value_two_sided": float(success_row["p_value_two_sided"]),
            "interpretation": (
                "Todos os trials terminaram com 100% dos testes passando e zero falhas; "
                "nao houve variacao para atribuir diferenca funcional ao tratamento."
            ),
        },
        "figures": [
            "rq1_paired_estimation",
            "rq1_speedup",
            "rq1_timebox",
            "rq1_exact_permutations",
            "rq2_outcomes",
        ],
    }
    (results_dir / "rq1_rq2_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=json_value) + "\n",
        encoding="utf-8",
    )


def run_analysis(trials_path: Path, output_dir: Path) -> dict[str, Path]:
    configure_theme()
    trials = load_trials(trials_path)
    pairs = build_pairs(trials)
    descriptive = descriptive_summary(trials)
    inferential = inferential_summary(pairs)

    figures_dir = output_dir / "figures"
    plot_paired_estimation(pairs, figures_dir)
    plot_speedup(pairs, figures_dir)
    plot_timebox(trials, figures_dir)
    plot_rq2_outcomes(trials, figures_dir)
    plot_exact_permutations(pairs, figures_dir)
    write_results(trials_path, trials, pairs, descriptive, inferential, output_dir)
    return {"figures": figures_dir, "results": output_dir / "results"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Analisa RQ1 e RQ2 do Lab02.")
    parser.add_argument("--trials", type=Path, default=DEFAULT_TRIALS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    outputs = run_analysis(args.trials.resolve(), args.output_dir.resolve())
    print("Analise RQ1/RQ2 concluida.")
    print(f"Resultados: {outputs['results']}")
    print(f"Figuras: {outputs['figures']}")


if __name__ == "__main__":
    main()
