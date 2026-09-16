"""Starter da Kata 01."""


def _procedimentos_unicos(grupo):
    vistos = set()
    procedimentos = []
    for _, procedimento in grupo:
        if procedimento not in vistos:
            vistos.add(procedimento)
            procedimentos.append(procedimento)
    return tuple(procedimentos)


def agrupar_calibracoes(solicitacoes, janela_minutos):
    """Agrupa solicitações próximas do mesmo equipamento.

    Consulte o README da kata para o contrato completo.
    """
    if (
        not isinstance(janela_minutos, int)
        or isinstance(janela_minutos, bool)
        or janela_minutos < 0
    ):
        raise ValueError("janela invalida")

    por_equipamento = {}
    for solicitacao in solicitacoes:
        if not isinstance(solicitacao, (tuple, list)) or len(solicitacao) != 3:
            raise ValueError("solicitacao invalida")
        equipamento, minuto, procedimento = solicitacao
        if not isinstance(equipamento, str) or not equipamento:
            raise ValueError("equipamento invalido")
        if (
            not isinstance(minuto, int)
            or isinstance(minuto, bool)
            or minuto < 0
        ):
            raise ValueError("minuto invalido")
        if not isinstance(procedimento, str) or not procedimento:
            raise ValueError("procedimento invalido")
        por_equipamento.setdefault(equipamento, []).append((minuto, procedimento))

    resultado = []
    for equipamento, itens in por_equipamento.items():
        itens.sort(key=lambda item: item[0])
        grupo = []
        for minuto, procedimento in itens:
            if grupo and minuto - grupo[-1][0] > janela_minutos:
                resultado.append(
                    (
                        equipamento,
                        grupo[0][0],
                        grupo[-1][0],
                        _procedimentos_unicos(grupo),
                        len(grupo),
                    )
                )
                grupo = []
            grupo.append((minuto, procedimento))
        if grupo:
            resultado.append(
                (
                    equipamento,
                    grupo[0][0],
                    grupo[-1][0],
                    _procedimentos_unicos(grupo),
                    len(grupo),
                )
            )

    return sorted(resultado, key=lambda grupo: (grupo[1], grupo[0]))
