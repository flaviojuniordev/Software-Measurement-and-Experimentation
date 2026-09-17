"""Starter da Kata 03."""


def resumir_emprestimos(eventos, fim_expediente):
    """Reconstrói empréstimos válidos e conta eventos ignorados.

    Consulte o README da kata para o contrato completo.
    """
    if (
        isinstance(fim_expediente, bool)
        or not isinstance(fim_expediente, int)
        or fim_expediente < 0
    ):
        raise ValueError("O fim do expediente deve ser um inteiro não negativo.")

    eventos_validados = []
    for ordem, evento in enumerate(eventos):
        if not isinstance(evento, (tuple, list)) or len(evento) != 4:
            raise ValueError("Evento inválido.")

        minuto, ferramenta, pessoa, acao = evento
        if (
            isinstance(minuto, bool)
            or not isinstance(minuto, int)
            or not 0 <= minuto <= fim_expediente
        ):
            raise ValueError("Minuto fora do expediente.")
        if not isinstance(ferramenta, str) or not ferramenta.strip():
            raise ValueError("A ferramenta deve ter um nome não vazio.")
        if not isinstance(pessoa, str) or not pessoa.strip():
            raise ValueError("A pessoa deve ter um nome não vazio.")
        if not isinstance(acao, str) or acao not in ("retirada", "devolucao"):
            raise ValueError("Ação desconhecida.")

        eventos_validados.append((minuto, ordem, ferramenta, pessoa, acao))

    abertos = {}
    emprestimos = []
    ignorados = 0

    for minuto, _, ferramenta, pessoa, acao in sorted(eventos_validados):
        if acao == "retirada":
            if ferramenta in abertos:
                ignorados += 1
            else:
                abertos[ferramenta] = (pessoa, minuto)
            continue

        emprestimo = abertos.get(ferramenta)
        if emprestimo is None or emprestimo[0] != pessoa:
            ignorados += 1
            continue

        _, inicio = abertos.pop(ferramenta)
        emprestimos.append(
            (ferramenta, pessoa, inicio, minuto, "devolucao")
        )

    for ferramenta, (pessoa, inicio) in abertos.items():
        emprestimos.append(
            (ferramenta, pessoa, inicio, fim_expediente, "fim_expediente")
        )

    emprestimos.sort(key=lambda item: (item[2], item[0]))
    return emprestimos, ignorados
