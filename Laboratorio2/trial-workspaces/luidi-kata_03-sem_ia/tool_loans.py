"""Starter da Kata 03."""


def resumir_emprestimos(eventos, fim_expediente):
    """Reconstrói empréstimos válidos e conta eventos ignorados.

    Consulte o README da kata para o contrato completo.
    """

    # Valida o fim do expediente
    if (
        not isinstance(fim_expediente, int)
        or isinstance(fim_expediente, bool)
        or fim_expediente < 0
    ):
        raise ValueError("fim_expediente deve ser um inteiro não negativo")

    # Tenta transformar os eventos em uma lista
    try:
        eventos = list(eventos)
    except TypeError:
        raise ValueError("eventos malformados")

    # Validação dos eventos
    for evento in eventos:
        if not isinstance(evento, (tuple, list)) or len(evento) != 4:
            raise ValueError("evento malformado")

        minuto, ferramenta, pessoa, acao = evento

        if not isinstance(minuto, int) or isinstance(minuto, bool):
            raise ValueError("minuto deve ser inteiro")

        if minuto < 0 or minuto > fim_expediente:
            raise ValueError("minuto fora do expediente")

        if not isinstance(ferramenta, str) or ferramenta.strip() == "":
            raise ValueError("ferramenta inválida")

        if not isinstance(pessoa, str) or pessoa.strip() == "":
            raise ValueError("pessoa inválida")

        if not isinstance(acao, str) or acao.strip() == "":
            raise ValueError("ação inválida")

        if acao not in ("retirada", "devolucao"):
            raise ValueError("ação desconhecida")

    # Ordena pelo minuto.
    # O sorted do Python mantém a ordem original quando os minutos são iguais.
    eventos_ordenados = sorted(eventos, key=lambda evento: evento[0])

    emprestados = {}
    emprestimos = []
    ignorados = 0

    for evento in eventos_ordenados:
        minuto, ferramenta, pessoa, acao = evento

        if acao == "retirada":
            # Só pode retirar se a ferramenta estiver disponível
            if ferramenta not in emprestados:
                emprestados[ferramenta] = (pessoa, minuto)
            else:
                ignorados += 1

        elif acao == "devolucao":
            # A ferramenta precisa estar emprestada
            # e com a mesma pessoa que está devolvendo
            if (
                ferramenta in emprestados
                and emprestados[ferramenta][0] == pessoa
            ):
                pessoa_emprestimo, inicio = emprestados[ferramenta]

                emprestimos.append(
                    (
                        ferramenta,
                        pessoa_emprestimo,
                        inicio,
                        minuto,
                        "devolucao",
                    )
                )

                del emprestados[ferramenta]

            else:
                ignorados += 1

    # Fecha os empréstimos que ficaram abertos
    for ferramenta, dados in emprestados.items():
        pessoa, inicio = dados

        emprestimos.append(
            (
                ferramenta,
                pessoa,
                inicio,
                fim_expediente,
                "fim_expediente",
            )
        )

    # Ordena por início e depois pelo nome da ferramenta
    emprestimos.sort(key=lambda emprestimo: (emprestimo[2], emprestimo[0]))

    return emprestimos, ignorados