from pathlib import Path

import pandas as pd
import pytest

from analysis.rq1_rq2_analysis import (
    DEFAULT_TRIALS,
    build_pairs,
    inferential_summary,
    load_trials,
    sign_flip_distribution,
)


def test_dataset_completo_forma_quatro_pares() -> None:
    trials = load_trials(DEFAULT_TRIALS)
    pairs = build_pairs(trials)

    assert len(trials) == 8
    assert len(pairs) == 4
    assert (pairs["time_delta_seconds"] < 0).all()
    assert pairs["speedup"].median() > 1


def test_wilcoxon_de_tempo_reflete_resolucao_de_quatro_pares() -> None:
    pairs = build_pairs(load_trials(DEFAULT_TRIALS))
    inference = inferential_summary(pairs).set_index("metric")
    time = inference.loc["time_to_green_seconds"]

    assert time["p_value_two_sided"] == pytest.approx(0.125)
    assert time["p_value_directional"] == pytest.approx(0.0625)
    assert time["rank_biserial_ai_minus_manual"] == pytest.approx(-1.0)
    assert time["probability_pair_favors_ai"] == pytest.approx(1.0)


def test_rq2_sem_variacao_e_reportada_sem_forcar_wilcoxon() -> None:
    pairs = build_pairs(load_trials(DEFAULT_TRIALS))
    inference = inferential_summary(pairs).set_index("metric")

    for metric in ("success_rate", "tests_failed"):
        row = inference.loc[metric]
        assert row["p_value_two_sided"] == pytest.approx(1.0)
        assert row["effective_pairs"] == 0
        assert "nao aplicavel" in row["method"]


def test_permutacao_exata_tem_dezesseis_mundos() -> None:
    pairs = build_pairs(load_trials(DEFAULT_TRIALS))
    distribution, observed, p_value = sign_flip_distribution(
        pairs["time_delta_seconds"]
    )

    assert len(distribution) == 16
    assert observed < 0
    assert p_value == pytest.approx(0.125)


def test_rejeita_trial_duplicado(tmp_path: Path) -> None:
    trials = pd.read_csv(DEFAULT_TRIALS)
    duplicated = pd.concat([trials, trials.iloc[[0]]], ignore_index=True)
    path = tmp_path / "trials.csv"
    duplicated.to_csv(path, index=False)

    with pytest.raises(ValueError, match="trial_ids duplicados"):
        load_trials(path)
