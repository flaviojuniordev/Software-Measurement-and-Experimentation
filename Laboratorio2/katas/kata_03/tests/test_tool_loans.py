from pathlib import Path
import os
import sys

import pytest


DEFAULT_STARTER = Path(__file__).resolve().parents[1] / "starter"
SOLUTION_DIR = Path(os.environ.get("KATA_SOLUTION_DIR", DEFAULT_STARTER))
sys.path.insert(0, str(SOLUTION_DIR))
from tool_loans import resumir_emprestimos  # noqa: E402


def test_reconstroi_eventos_fora_de_ordem():
    eventos = [
        (12, "furadeira", "ana", "devolucao"),
        (4, "furadeira", "ana", "retirada"),
        (7, "furadeira", "bia", "retirada"),
    ]
    assert resumir_emprestimos(eventos, 20) == (
        [("furadeira", "ana", 4, 12, "devolucao")],
        1,
    )


def test_devolucao_por_outra_pessoa_e_ignorada():
    eventos = [
        (1, "chave", "ana", "retirada"),
        (4, "chave", "bia", "devolucao"),
        (6, "chave", "ana", "devolucao"),
    ]
    assert resumir_emprestimos(eventos, 10) == (
        [("chave", "ana", 1, 6, "devolucao")],
        1,
    )


def test_emprestimo_aberto_fecha_no_fim_do_expediente():
    assert resumir_emprestimos([(3, "serrote", "caio", "retirada")], 15) == (
        [("serrote", "caio", 3, 15, "fim_expediente")],
        0,
    )


def test_ferramenta_pode_ser_emprestada_novamente():
    eventos = [
        (1, "chave", "ana", "retirada"),
        (2, "chave", "ana", "devolucao"),
        (3, "chave", "bia", "retirada"),
        (5, "chave", "bia", "devolucao"),
    ]
    assert resumir_emprestimos(eventos, 8) == (
        [
            ("chave", "ana", 1, 2, "devolucao"),
            ("chave", "bia", 3, 5, "devolucao"),
        ],
        0,
    )


def test_eventos_no_mesmo_minuto_preservam_ordem_original():
    eventos = [
        (2, "chave", "ana", "retirada"),
        (2, "chave", "ana", "devolucao"),
    ]
    assert resumir_emprestimos(eventos, 8) == (
        [("chave", "ana", 2, 2, "devolucao")],
        0,
    )


def test_lista_vazia():
    assert resumir_emprestimos([], 8) == ([], 0)


@pytest.mark.parametrize(
    "eventos,fim",
    [
        ([], -1),
        ([(9, "chave", "ana", "retirada")], 8),
        ([(1, "", "ana", "retirada")], 8),
        ([(1, "chave", "ana", "perda")], 8),
        ([(1, "chave", "ana")], 8),
    ],
)
def test_rejeita_entrada_invalida(eventos, fim):
    with pytest.raises(ValueError):
        resumir_emprestimos(eventos, fim)
