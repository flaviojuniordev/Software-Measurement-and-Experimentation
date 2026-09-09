from pathlib import Path
import os
import sys

import pytest


DEFAULT_STARTER = Path(__file__).resolve().parents[1] / "starter"
SOLUTION_DIR = Path(os.environ.get("KATA_SOLUTION_DIR", DEFAULT_STARTER))
sys.path.insert(0, str(SOLUTION_DIR))
from calibration_schedule import agrupar_calibracoes  # noqa: E402


def test_agrupa_por_diferenca_entre_solicitacoes_consecutivas():
    entrada = [
        ("balanca-b", 20, "nivelar"),
        ("balanca-a", 16, "limpar"),
        ("balanca-a", 10, "limpar"),
        ("balanca-a", 14, "nivelar"),
    ]
    assert agrupar_calibracoes(entrada, 5) == [
        ("balanca-a", 10, 16, ("limpar", "nivelar"), 3),
        ("balanca-b", 20, 20, ("nivelar",), 1),
    ]


def test_janela_e_inclusiva():
    entrada = [("forno", 4, "temperatura"), ("forno", 9, "vedacao")]
    assert agrupar_calibracoes(entrada, 5) == [
        ("forno", 4, 9, ("temperatura", "vedacao"), 2)
    ]


def test_abre_novo_grupo_quando_a_janela_e_excedida():
    entrada = [("forno", 4, "temperatura"), ("forno", 10, "vedacao")]
    assert agrupar_calibracoes(entrada, 5) == [
        ("forno", 4, 4, ("temperatura",), 1),
        ("forno", 10, 10, ("vedacao",), 1),
    ]


def test_equipamentos_sao_agrupados_independentemente():
    entrada = [("b", 1, "p1"), ("a", 2, "p2"), ("b", 3, "p3")]
    assert agrupar_calibracoes(entrada, 3) == [
        ("b", 1, 3, ("p1", "p3"), 2),
        ("a", 2, 2, ("p2",), 1),
    ]


def test_lista_vazia():
    assert agrupar_calibracoes([], 5) == []


@pytest.mark.parametrize(
    "entrada,janela",
    [
        ([("", 1, "nivelar")], 5),
        ([("forno", -1, "nivelar")], 5),
        ([("forno", 1, "")], 5),
        ([("forno", 1)], 5),
        ([("forno", 1, "nivelar")], -1),
    ],
)
def test_rejeita_entrada_invalida(entrada, janela):
    with pytest.raises(ValueError):
        agrupar_calibracoes(entrada, janela)
