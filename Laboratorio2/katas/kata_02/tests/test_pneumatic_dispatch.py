from pathlib import Path
import os
import sys

import pytest


DEFAULT_STARTER = Path(__file__).resolve().parents[1] / "starter"
SOLUTION_DIR = Path(os.environ.get("KATA_SOLUTION_DIR", DEFAULT_STARTER))
sys.path.insert(0, str(SOLUTION_DIR))
from pneumatic_dispatch import planejar_despachos  # noqa: E402


def test_combina_a_maior_sequencia_que_cabe():
    capsulas = [
        ("c1", "bio", 3, False),
        ("c2", "quimica", 4, False),
        ("c3", "bio", 1, False),
        ("c4", "bio", 2, False),
    ]
    assert planejar_despachos(capsulas, 8, 2) == [
        (("c1", "c2", "c3"), ("bio", "quimica"), 8, False),
        (("c4",), ("bio",), 2, False),
    ]


def test_limite_de_destinos_fecha_a_viagem():
    capsulas = [
        ("c1", "a", 1, False),
        ("c2", "b", 1, False),
        ("c3", "c", 1, False),
    ]
    assert planejar_despachos(capsulas, 10, 2) == [
        (("c1", "c2"), ("a", "b"), 2, False),
        (("c3",), ("c",), 1, False),
    ]


def test_urgente_viaja_sozinha_e_separa_as_vizinhas():
    capsulas = [
        ("c1", "a", 1, False),
        ("u1", "b", 2, True),
        ("c2", "a", 1, False),
    ]
    assert planejar_despachos(capsulas, 10, 3) == [
        (("c1",), ("a",), 1, False),
        (("u1",), ("b",), 2, True),
        (("c2",), ("a",), 1, False),
    ]


def test_destino_repetido_nao_consume_nova_parada():
    capsulas = [("c1", "a", 1, False), ("c2", "a", 2, False)]
    assert planejar_despachos(capsulas, 5, 1) == [
        (("c1", "c2"), ("a",), 3, False)
    ]


def test_lista_vazia():
    assert planejar_despachos([], 5, 2) == []


@pytest.mark.parametrize(
    "capsulas,capacidade,max_paradas",
    [
        ([], 0, 2),
        ([], 5, 0),
        ([("c1", "a", 6, False)], 5, 2),
        ([("c1", "", 1, False)], 5, 2),
        ([("c1", "a", 1, "sim")], 5, 2),
        ([("c1", "a", 1, False), ("c1", "b", 1, False)], 5, 2),
    ],
)
def test_rejeita_entrada_invalida(capsulas, capacidade, max_paradas):
    with pytest.raises(ValueError):
        planejar_despachos(capsulas, capacidade, max_paradas)
