from pathlib import Path
import os
import sys

import pytest


DEFAULT_STARTER = Path(__file__).resolve().parents[1] / "starter"
SOLUTION_DIR = Path(os.environ.get("KATA_SOLUTION_DIR", DEFAULT_STARTER))
sys.path.insert(0, str(SOLUTION_DIR))
from irrigation_cycles import detectar_ciclos_rega  # noqa: E402


def test_detecta_ciclo_com_entrada_fora_de_ordem():
    medicoes = [("norte", 8, 64), ("norte", 2, 28), ("norte", 5, 22)]
    assert detectar_ciclos_rega(medicoes, 30, 60, 5) == [
        ("norte", 2, 8, 22, 3)
    ]


def test_nova_leitura_baixa_nao_reinicia_o_ciclo():
    medicoes = [("sul", 1, 30), ("sul", 2, 20), ("sul", 3, 70)]
    assert detectar_ciclos_rega(medicoes, 30, 60, 5) == [
        ("sul", 1, 3, 20, 3)
    ]


def test_falha_longa_descarta_ciclo_aberto_e_processa_nova_leitura():
    medicoes = [
        ("sul", 1, 20),
        ("sul", 10, 25),
        ("sul", 12, 65),
    ]
    assert detectar_ciclos_rega(medicoes, 30, 60, 5) == [
        ("sul", 10, 12, 25, 2)
    ]


def test_ciclo_aberto_no_fim_e_descartado():
    assert detectar_ciclos_rega([("sul", 1, 20), ("sul", 3, 40)], 30, 60, 5) == []


def test_bandejas_sao_independentes_e_resultado_e_ordenado():
    medicoes = [
        ("b", 1, 20),
        ("a", 1, 25),
        ("a", 2, 65),
        ("b", 3, 61),
    ]
    assert detectar_ciclos_rega(medicoes, 30, 60, 5) == [
        ("a", 1, 2, 25, 2),
        ("b", 1, 3, 20, 2),
    ]


def test_lista_vazia():
    assert detectar_ciclos_rega([], 30, 60, 5) == []


@pytest.mark.parametrize(
    "medicoes,baixo,alto,intervalo",
    [
        ([], 60, 30, 5),
        ([], 30, 60, 0),
        ([("", 1, 20)], 30, 60, 5),
        ([("a", -1, 20)], 30, 60, 5),
        ([("a", 1, 101)], 30, 60, 5),
        ([("a", 1)], 30, 60, 5),
    ],
)
def test_rejeita_entrada_invalida(medicoes, baixo, alto, intervalo):
    with pytest.raises(ValueError):
        detectar_ciclos_rega(medicoes, baixo, alto, intervalo)
