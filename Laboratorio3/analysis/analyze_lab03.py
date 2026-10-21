"""Executa as analises estatisticas das RQ01 a RQ07 do Laboratorio 03."""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import kruskal, mannwhitneyu, spearmanr
from sklearn.metrics import cohen_kappa_score
from statsmodels.stats.multitest import multipletests

from pipeline.metrics import (
    classify_change_failure_rate,
    classify_deployment_frequency,
    classify_lead_time,
    classify_overall_dora,
    classify_recovery_time,
)


METRICS = {
    "deployment_frequency_per_week": "Deployment frequency",
    "lead_time_release_median_hours": "Lead time por release",
    "lead_time_commit_median_hours": "Lead time por commit",
    "ci_change_failure_rate": "CFR de CI",
    "release_change_failure_rate": "CFR por entrega",
    "median_recovery_hours": "Tempo de recuperacao",
    "censored_episodes_proportion": "Proporcao censurada",
}

RQ06_METRICS = {
    "deployment_frequency_per_week": "Deployment frequency",
    "lead_time_release_median_hours": "Lead time",
    "ci_change_failure_rate": "CFR de CI",
    "median_recovery_hours": "Recuperacao",
}

DORA_ORDER = ["Low", "Medium", "High", "Elite"]
COLORS = {
    "teal": "#147D78",
    "coral": "#D95F59",
    "gold": "#D7A52A",
    "ink": "#293241",
    "green": "#4C956C",
    "gray": "#8D99AE",
}


def descriptive_statistics(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column, label in METRICS.items():
        values = pd.to_numeric(data[column], errors="coerce").dropna()
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        rows.append(
            {
                "metric": column,
                "label": label,
                "n": int(values.size),
                "missing": int(len(data) - values.size),
                "median": float(values.median()),
                "q1": float(q1),
                "q3": float(q3),
                "iqr": float(q3 - q1),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
            }
        )
    return pd.DataFrame(rows)


def cliffs_delta(first: Iterable[float], second: Iterable[float]) -> float:
    x = np.asarray(list(first), dtype=float)
    y = np.asarray(list(second), dtype=float)
    if not len(x) or not len(y):
        raise ValueError("Cliff's delta exige dois grupos nao vazios")
    statistic = mannwhitneyu(x, y, alternative="two-sided").statistic
    return float(2 * statistic / (len(x) * len(y)) - 1)


def effect_magnitude(value: float, *, signed: bool = False) -> str:
    magnitude = abs(value) if signed else value
    if signed:
        if magnitude < 0.147:
            return "desprezivel"
        if magnitude < 0.33:
            return "pequeno"
        if magnitude < 0.474:
            return "medio"
        return "grande"
    if magnitude < 0.01:
        return "desprezivel"
    if magnitude < 0.06:
        return "pequeno"
    if magnitude < 0.14:
        return "medio"
    return "grande"


def add_rq06_factors(
    data: pd.DataFrame, consensus_repositories: pd.DataFrame
) -> pd.DataFrame:
    result = data.copy()
    for source, destination in (
        ("stars", "stars_quartile"),
        ("contributors_count", "contributors_quartile"),
        ("age_days_at_window_end", "age_quartile"),
    ):
        result[destination] = pd.qcut(
            result[source],
            q=4,
            labels=["Q1", "Q2", "Q3", "Q4"],
            duplicates="drop",
        ).astype("string")

    top_languages = result["language"].value_counts().head(5).index
    result["language_group"] = result["language"].where(
        result["language"].isin(top_languages), "Outras"
    )
    labels = consensus_repositories.rename(
        columns={
            "repository": "full_name",
            "project_type_consensus": "project_type",
        }
    )[["full_name", "project_type"]]
    return result.merge(labels, how="left", on="full_name")


def rq05_correlations(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cfr_column, label in (
        ("ci_change_failure_rate", "CFR de CI"),
        ("release_change_failure_rate", "CFR por entrega"),
    ):
        subset = data[
            ["deployment_frequency_per_week", cfr_column]
        ].dropna()
        result = spearmanr(
            subset["deployment_frequency_per_week"],
            subset[cfr_column],
        )
        rows.append(
            {
                "cfr_variant": cfr_column,
                "label": label,
                "n": int(len(subset)),
                "spearman_rho": float(result.statistic),
                "p_value": float(result.pvalue),
            }
        )
    return pd.DataFrame(rows)


def rq06_tests(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    factors = {
        "stars_quartile": "Popularidade",
        "contributors_quartile": "Contribuidores",
        "age_quartile": "Idade",
        "language_group": "Linguagem",
        "project_type": "Tipo de projeto",
    }
    tests: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for factor, factor_label in factors.items():
        for metric, metric_label in RQ06_METRICS.items():
            subset = data[[factor, metric]].dropna()
            groups = [
                (str(name), group[metric].astype(float).to_numpy())
                for name, group in subset.groupby(factor, observed=True)
                if len(group) >= 2
            ]
            if len(groups) < 2:
                continue
            for group_name, values in groups:
                summaries.append(
                    {
                        "factor": factor,
                        "factor_label": factor_label,
                        "group": group_name,
                        "metric": metric,
                        "metric_label": metric_label,
                        "n": int(len(values)),
                        "median": float(np.median(values)),
                        "q1": float(np.quantile(values, 0.25)),
                        "q3": float(np.quantile(values, 0.75)),
                    }
                )
            arrays = [values for _, values in groups]
            if len(groups) == 2:
                result = mannwhitneyu(arrays[0], arrays[1], alternative="two-sided")
                effect = cliffs_delta(arrays[0], arrays[1])
                method = "Mann-Whitney"
                effect_name = "Cliff's delta"
                magnitude = effect_magnitude(effect, signed=True)
            else:
                if np.ptp(np.concatenate(arrays)) == 0:
                    statistic, p_value = 0.0, 1.0
                else:
                    result = kruskal(*arrays)
                    statistic, p_value = result.statistic, result.pvalue
                effect = max(0.0, float(statistic) / (len(subset) - 1))
                method = "Kruskal-Wallis"
                effect_name = "epsilon_squared"
                magnitude = effect_magnitude(effect)
                result = type("Result", (), {"statistic": statistic, "pvalue": p_value})
            tests.append(
                {
                    "factor": factor,
                    "factor_label": factor_label,
                    "metric": metric,
                    "metric_label": metric_label,
                    "test": method,
                    "groups": len(groups),
                    "n": int(len(subset)),
                    "statistic": float(result.statistic),
                    "p_value_raw": float(result.pvalue),
                    "effect_name": effect_name,
                    "effect_size": float(effect),
                    "effect_magnitude": magnitude,
                }
            )

    tests_frame = pd.DataFrame(tests)
    rejected, corrected, _, _ = multipletests(
        tests_frame["p_value_raw"], alpha=0.05, method="holm"
    )
    tests_frame["p_value_holm"] = corrected
    tests_frame["significant_holm"] = rejected
    return tests_frame, pd.DataFrame(summaries)


def classify_scenario(
    data: pd.DataFrame,
    *,
    lead_time_column: str,
    cfr_column: str,
) -> pd.Series:
    values = []
    for _, row in data.iterrows():
        deployment = classify_deployment_frequency(
            float(row["deployment_frequency_per_week"])
        )
        lead_value = row[lead_time_column]
        cfr_value = row[cfr_column]
        recovery_value = row["median_recovery_hours"]
        lead = classify_lead_time(float(lead_value)) if pd.notna(lead_value) else None
        cfr = (
            classify_change_failure_rate(float(cfr_value))
            if pd.notna(cfr_value)
            else None
        )
        recovery = (
            classify_recovery_time(float(recovery_value))
            if pd.notna(recovery_value)
            else None
        )
        overall = classify_overall_dora(deployment, lead, cfr, recovery)
        values.append(overall.value if overall is not None else pd.NA)
    return pd.Series(values, index=data.index, dtype="string")


def rq07_sensitivity(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenarios = {
        "C1_ref_LT_release_CFR_CI": (
            "lead_time_release_median_hours",
            "ci_change_failure_rate",
        ),
        "C2_LT_commit_CFR_release": (
            "lead_time_commit_median_hours",
            "release_change_failure_rate",
        ),
        "C3_LT_commit_CFR_CI": (
            "lead_time_commit_median_hours",
            "ci_change_failure_rate",
        ),
        "C4_LT_release_CFR_release": (
            "lead_time_release_median_hours",
            "release_change_failure_rate",
        ),
    }
    classifications = data[["full_name"]].copy()
    for name, (lead, cfr) in scenarios.items():
        classifications[name] = classify_scenario(
            data, lead_time_column=lead, cfr_column=cfr
        )

    rows = []
    for first, second in combinations(scenarios, 2):
        subset = classifications[[first, second]].dropna()
        changed = subset[first] != subset[second]
        kappa = cohen_kappa_score(
            subset[first],
            subset[second],
            labels=DORA_ORDER,
            weights="linear",
        )
        rows.append(
            {
                "scenario_a": first,
                "scenario_b": second,
                "n": int(len(subset)),
                "changed_count": int(changed.sum()),
                "changed_proportion": float(changed.mean()),
                "weighted_cohen_kappa": float(kappa),
            }
        )
    return pd.DataFrame(rows), classifications


def dora_counts(data: pd.DataFrame, scenarios: pd.DataFrame) -> pd.DataFrame:
    columns = {
        "deployment_frequency_dora": "Deployment frequency",
        "lead_time_dora": "Lead time",
        "change_failure_rate_dora": "CFR de CI",
        "recovery_time_dora": "Recuperacao",
        "overall_dora": "Geral C1",
    }
    rows = []
    for column, label in columns.items():
        counts = data[column].value_counts(dropna=False)
        for category in [*DORA_ORDER, "Ausente"]:
            key = np.nan if category == "Ausente" else category
            count = int(data[column].isna().sum()) if category == "Ausente" else int(counts.get(key, 0))
            rows.append(
                {"classification": label, "category": category, "count": count}
            )
    for column in scenarios.columns[1:]:
        for category in [*DORA_ORDER, "Ausente"]:
            count = (
                int(scenarios[column].isna().sum())
                if category == "Ausente"
                else int((scenarios[column] == category).sum())
            )
            rows.append(
                {"classification": column, "category": category, "count": count}
            )
    return pd.DataFrame(rows)


def configure_style() -> None:
    sns.set_theme(style="whitegrid", context="paper")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "figure.dpi": 160,
            "savefig.dpi": 220,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def plot_funnel_and_classes(
    funnel_path: Path,
    data: pd.DataFrame,
    output: Path,
) -> None:
    funnel = json.loads(funnel_path.read_text(encoding="utf-8"))["stages"]
    labels = [
        "Processados",
        "Com Actions",
        ">=5 releases",
        ">=50 runs",
        "Amostra final",
    ]
    counts = [item["count"] for item in funnel]
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.7))
    axes[0].barh(labels[::-1], counts[::-1], color=[COLORS["teal"], COLORS["green"], COLORS["gold"], COLORS["coral"], COLORS["ink"]])
    for index, count in enumerate(counts[::-1]):
        axes[0].text(count + 12, index, str(count), va="center", fontsize=8)
    axes[0].set_title("Funil de selecao")
    axes[0].set_xlabel("Repositorios")
    axes[0].set_xlim(0, max(counts) * 1.16)

    order = ["Elite", "High", "Medium", "Low", "Ausente"]
    values = [int((data["overall_dora"] == item).sum()) for item in order[:-1]]
    values.append(int(data["overall_dora"].isna().sum()))
    colors = [COLORS["teal"], COLORS["green"], COLORS["gold"], COLORS["coral"], COLORS["gray"]]
    axes[1].bar(order, values, color=colors)
    for index, count in enumerate(values):
        axes[1].text(index, count + 3, str(count), ha="center", fontsize=8)
    axes[1].set_title("Classificacao DORA geral - C1")
    axes[1].set_ylabel("Repositorios")
    axes[1].tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_lead_and_correlation(data: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    axes[0].scatter(
        data["lead_time_commit_median_hours"],
        data["lead_time_release_median_hours"],
        s=14,
        alpha=0.55,
        color=COLORS["teal"],
        edgecolors="none",
    )
    limits = [
        max(0.1, min(data["lead_time_commit_median_hours"].min(), data["lead_time_release_median_hours"].min())),
        max(data["lead_time_commit_median_hours"].max(), data["lead_time_release_median_hours"].max()),
    ]
    axes[0].plot(limits, limits, linestyle="--", color=COLORS["gray"], linewidth=1)
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Por commit (h)")
    axes[0].set_ylabel("Por release (h)")
    axes[0].set_title("RQ02 - variantes de lead time")

    for axis, cfr, title, color in (
        (axes[1], "ci_change_failure_rate", "CFR de CI", COLORS["coral"]),
        (axes[2], "release_change_failure_rate", "CFR por entrega", COLORS["gold"]),
    ):
        subset = data[["deployment_frequency_per_week", cfr]].dropna()
        axis.scatter(
            subset["deployment_frequency_per_week"],
            subset[cfr] * 100,
            s=14,
            alpha=0.5,
            color=color,
            edgecolors="none",
        )
        rho = spearmanr(subset["deployment_frequency_per_week"], subset[cfr])
        axis.set_xscale("log")
        axis.set_xlabel("Releases por semana")
        axis.set_ylabel("Taxa de falha (%)")
        axis.set_title(f"RQ05 - {title}\nSpearman rho={rho.statistic:.2f}; p={rho.pvalue:.3g}")
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_rq06_effects(tests: pd.DataFrame, output: Path) -> None:
    pivot = tests.pivot(index="factor_label", columns="metric_label", values="effect_size")
    annotations = tests.copy()
    annotations["text"] = annotations.apply(
        lambda row: f"{row['effect_size']:.2f}{'*' if row['significant_holm'] else ''}",
        axis=1,
    )
    annotation_pivot = annotations.pivot(
        index="factor_label", columns="metric_label", values="text"
    )
    fig, axis = plt.subplots(figsize=(7.6, 3.8))
    sns.heatmap(
        pivot,
        annot=annotation_pivot,
        fmt="",
        cmap=sns.light_palette(COLORS["teal"], as_cmap=True),
        vmin=0,
        vmax=max(0.15, float(pivot.max().max())),
        linewidths=0.7,
        cbar_kws={"label": "Tamanho de efeito"},
        ax=axis,
    )
    axis.set_title("RQ06 - efeitos por caracteristica (* p Holm < 0,05)")
    axis.set_xlabel("")
    axis.set_ylabel("")
    axis.tick_params(axis="x", rotation=22)
    axis.tick_params(axis="y", rotation=0)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_rq07(
    sensitivity: pd.DataFrame,
    classifications: pd.DataFrame,
    output: Path,
) -> None:
    scenario_columns = list(classifications.columns[1:])
    short = {name: name.split("_")[0] for name in scenario_columns}
    distribution = pd.DataFrame(
        {
            short[column]: [int((classifications[column] == category).sum()) for category in DORA_ORDER]
            for column in scenario_columns
        },
        index=DORA_ORDER,
    ).T
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    distribution.plot(
        kind="bar",
        stacked=True,
        color=[COLORS["coral"], COLORS["gold"], COLORS["green"], COLORS["teal"]],
        ax=axes[0],
    )
    axes[0].set_title("Distribuicao das categorias")
    axes[0].set_xlabel("Cenario")
    axes[0].set_ylabel("Repositorios classificados")
    axes[0].tick_params(axis="x", rotation=0)
    axes[0].legend(title="", fontsize=7)

    scenario_labels = list(short.values())
    matrix = pd.DataFrame(
        np.full((len(scenario_labels), len(scenario_labels)), np.nan),
        index=scenario_labels,
        columns=scenario_labels,
    )
    annotations = pd.DataFrame("-", index=matrix.index, columns=matrix.columns)
    for label in scenario_labels:
        matrix.loc[label, label] = 0.0
    for _, row in sensitivity.iterrows():
        first = short[row["scenario_a"]]
        second = short[row["scenario_b"]]
        value = row["changed_proportion"] * 100
        matrix.loc[first, second] = value
        matrix.loc[second, first] = value
        text = f"{value:.1f}%\nk={row['weighted_cohen_kappa']:.2f}"
        annotations.loc[first, second] = text
        annotations.loc[second, first] = text
    sns.heatmap(
        matrix,
        annot=annotations,
        fmt="",
        cmap=sns.light_palette(COLORS["coral"], as_cmap=True),
        vmin=0,
        vmax=max(1, float(np.nanmax(matrix.values))),
        linewidths=0.7,
        cbar_kws={"label": "Mudanca de categoria (%)"},
        ax=axes[1],
    )
    axes[1].set_title("Mudanca e kappa ponderado")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("")
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def plot_validation(
    agreement_path: Path,
    evaluations_path: Path,
    output: Path,
) -> None:
    agreement = json.loads(agreement_path.read_text(encoding="utf-8"))
    evaluations = json.loads(evaluations_path.read_text(encoding="utf-8"))[
        "evaluations"
    ]
    labels = ["Tipo", "Entregas", "Corretivas"]
    keys = ["project_type", "releases_are_deliveries", "corrective_releases"]
    kappas = [agreement[key]["fleiss_kappa"] for key in keys]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    axes[0].bar(labels, kappas, color=[COLORS["teal"], COLORS["green"], COLORS["coral"]])
    axes[0].axhline(0, color=COLORS["ink"], linewidth=0.8)
    axes[0].set_ylim(min(-0.25, min(kappas) - 0.1), 1)
    axes[0].set_ylabel("Kappa de Fleiss")
    axes[0].set_title("Concordancia entre rotulacoes")
    for index, value in enumerate(kappas):
        axes[0].text(index, value + (0.035 if value >= 0 else -0.08), f"{value:.2f}", ha="center")

    versions = [item["heuristic"]["version"] for item in evaluations]
    f1 = [item["f1"] for item in evaluations]
    axes[1].bar(versions, f1, color=[COLORS["gold"], COLORS["gray"], COLORS["teal"], COLORS["coral"], COLORS["green"]][: len(versions)])
    axes[1].axhline(0.70, color=COLORS["ink"], linestyle="--", linewidth=1, label="Meta 0,70")
    axes[1].set_ylim(0, 0.8)
    axes[1].set_ylabel("F1")
    axes[1].set_title("Refinamento da heuristica")
    axes[1].tick_params(axis="x", rotation=25)
    axes[1].legend(fontsize=7)
    for index, value in enumerate(f1):
        axes[1].text(index, value + 0.02, f"{value:.2f}", ha="center", fontsize=7)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def build_summary(
    data: pd.DataFrame,
    descriptive: pd.DataFrame,
    correlations: pd.DataFrame,
    rq06: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> dict[str, Any]:
    metrics = {
        row["metric"]: {
            "n": int(row["n"]),
            "median": float(row["median"]),
            "q1": float(row["q1"]),
            "q3": float(row["q3"]),
            "iqr": float(row["iqr"]),
        }
        for _, row in descriptive.iterrows()
    }
    significant = rq06[rq06["significant_holm"]].sort_values("p_value_holm")
    return {
        "sample_size": int(len(data)),
        "metrics": metrics,
        "overall_dora": {
            str(key): int(value)
            for key, value in data["overall_dora"].fillna("Ausente").value_counts().items()
        },
        "recovery_censored_repositories": int(data["median_recovery_hours"].isna().sum()),
        "rq05": correlations.to_dict(orient="records"),
        "rq06_significant_after_holm": significant.to_dict(orient="records"),
        "rq07": sensitivity.to_dict(orient="records"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analises RQ01-RQ07 do Lab03")
    parser.add_argument("--dataset", default="data/repositories_s02.csv")
    parser.add_argument(
        "--consensus-repositories",
        default="data/validation/consensus/consensus_repositories.csv",
    )
    parser.add_argument("--funnel", default="data/selection_funnel.json")
    parser.add_argument(
        "--agreement", default="data/validation/agreement/agreement.json"
    )
    parser.add_argument(
        "--heuristic-evaluations",
        default="data/validation/heuristic_evaluations.json",
    )
    parser.add_argument("--output-dir", default="analysis/results")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output_dir)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(args.dataset)
    consensus = pd.read_csv(args.consensus_repositories)
    enriched = add_rq06_factors(data, consensus)

    descriptive = descriptive_statistics(data)
    correlations = rq05_correlations(data)
    rq06, group_summaries = rq06_tests(enriched)
    sensitivity, classifications = rq07_sensitivity(data)
    counts = dora_counts(data, classifications)

    descriptive.to_csv(output / "descriptive_statistics.csv", index=False)
    correlations.to_csv(output / "rq05_spearman.csv", index=False)
    rq06.to_csv(output / "rq06_tests.csv", index=False)
    group_summaries.to_csv(output / "rq06_group_summaries.csv", index=False)
    sensitivity.to_csv(output / "rq07_sensitivity.csv", index=False)
    classifications.to_csv(output / "rq07_classifications.csv", index=False)
    counts.to_csv(output / "dora_classification_counts.csv", index=False)

    summary = build_summary(data, descriptive, correlations, rq06, sensitivity)
    (output / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    configure_style()
    plot_funnel_and_classes(Path(args.funnel), data, figures / "fig1_funnel_dora.png")
    plot_lead_and_correlation(data, figures / "fig2_rq02_rq05.png")
    plot_rq06_effects(rq06, figures / "fig3_rq06_effects.png")
    plot_rq07(sensitivity, classifications, figures / "fig4_rq07_sensitivity.png")
    plot_validation(
        Path(args.agreement),
        Path(args.heuristic_evaluations),
        figures / "fig5_validation.png",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
