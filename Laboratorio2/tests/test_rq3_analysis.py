from pathlib import Path

import pandas as pd
import pytest

from analysis.rq3_analysis import (
    DEFAULT_METRICS,
    DEFAULT_TRIALS,
    build_pairs,
    descriptive_summary,
    holm_adjust,
    inferential_summary,
    leave_one_pair_out,
    load_and_validate,
    wilcoxon_exact_or_permutation,
)


def write_frames(
    tmp_path: Path, metrics: pd.DataFrame, trials: pd.DataFrame
) -> tuple[Path, Path]:
    metrics_path = tmp_path / "static_metrics.csv"
    trials_path = tmp_path / "trials.csv"
    metrics.to_csv(metrics_path, index=False)
    trials.to_csv(trials_path, index=False)
    return metrics_path, trials_path


def test_dataset_completo_corresponde_a_oito_trials_e_quatro_pares() -> None:
    metrics, trials = load_and_validate(DEFAULT_METRICS, DEFAULT_TRIALS)
    pairs = build_pairs(metrics)

    assert len(metrics) == len(trials) == 8
    assert len(pairs) == 4
    assert (pairs["loc_delta"] < 0).all()
    assert (pairs["avg_cyclomatic_complexity_delta"] < 0).all()


def test_resumo_descritivo_calcula_mediana_quartis_e_iqr() -> None:
    metrics, _trials = load_and_validate(DEFAULT_METRICS, DEFAULT_TRIALS)
    summary = descriptive_summary(metrics).set_index(["metric", "treatment"])

    loc_ai = summary.loc[("loc", "com_ia")]
    assert loc_ai["median"] == pytest.approx(49.0)
    assert loc_ai["q1"] == pytest.approx(48.5)
    assert loc_ai["q3"] == pytest.approx(49.25)
    assert loc_ai["iqr"] == pytest.approx(0.75)


def test_inferencia_orienta_todas_as_metricas_em_favor_da_ia() -> None:
    metrics, _trials = load_and_validate(DEFAULT_METRICS, DEFAULT_TRIALS)
    inference = inferential_summary(build_pairs(metrics)).set_index("metric")

    assert inference.loc["loc", "p_value_two_sided"] == pytest.approx(0.125)
    assert inference.loc["loc", "rank_biserial_favors_ai"] == pytest.approx(1.0)
    assert inference.loc[
        "avg_cyclomatic_complexity", "proportion_pairs_favoring_ai"
    ] == pytest.approx(1.0)
    assert inference.loc["maintainability_index", "pairs_favoring_ai"] == 3
    assert inference.loc["duplication_percentage", "zero_differences"] == 3
    assert "permutacao" in inference.loc["duplication_percentage", "method"]


def test_todas_as_diferencas_zero_nao_forcam_wilcoxon() -> None:
    result = wilcoxon_exact_or_permutation([0, 0, 0, 0])

    assert result["statistic"] is None
    assert result["p_value"] is None
    assert result["effective_pairs"] == 0
    assert "nao aplicavel" in result["method"]


def test_holm_e_monotono_e_preserva_resultado_nao_aplicavel() -> None:
    adjusted = holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})

    assert adjusted["a"] == pytest.approx(0.03)
    assert adjusted["c"] == pytest.approx(0.06)
    assert adjusted["b"] == pytest.approx(0.06)
    assert adjusted["d"] is None


def test_leave_one_pair_out_recalcula_quatro_cenarios_por_metrica() -> None:
    metrics, _trials = load_and_validate(DEFAULT_METRICS, DEFAULT_TRIALS)
    leave_one_out = leave_one_pair_out(build_pairs(metrics))

    assert len(leave_one_out) == 16
    assert (leave_one_out.groupby("metric").size() == 4).all()
    assert (leave_one_out["remaining_pairs"] == 3).all()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate", "duplicado"),
        ("invalid_treatment", "tratamentos invalidos"),
        ("out_of_range", "duplication_percentage deve estar"),
        ("missing_correspondence", "Correspondencia"),
        ("missing_pair", "quatro pares"),
    ],
)
def test_rejeita_bases_invalidas(tmp_path: Path, mutation: str, message: str) -> None:
    metrics = pd.read_csv(DEFAULT_METRICS)
    trials = pd.read_csv(DEFAULT_TRIALS)
    if mutation == "duplicate":
        metrics.loc[7, ["participant", "kata", "treatment"]] = metrics.loc[
            6, ["participant", "kata", "treatment"]
        ]
    elif mutation == "invalid_treatment":
        metrics.loc[0, "treatment"] = "talvez_ia"
    elif mutation == "out_of_range":
        metrics.loc[0, "duplication_percentage"] = 101
    elif mutation == "missing_pair":
        metrics = metrics[
            ~((metrics["participant"] == "luidi") & (metrics["kata"] == "kata_04"))
        ]
    else:
        metrics.loc[
            (metrics["participant"] == "flavio") & (metrics["kata"] == "kata_01"),
            "kata",
        ] = "kata_99"
    metrics_path, trials_path = write_frames(tmp_path, metrics, trials)

    with pytest.raises(ValueError, match=message):
        load_and_validate(metrics_path, trials_path)
