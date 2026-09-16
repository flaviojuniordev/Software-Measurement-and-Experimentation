"""Starter da Kata 01."""


def _inteiro_nao_negativo(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def agrupar_calibracoes(solicitacoes, janela_minutos):
    """Agrupa solicitações próximas do mesmo equipamento.

    Consulte o README da kata para o contrato completo.
    """
    if not _inteiro_nao_negativo(janela_minutos):
        raise ValueError("janela_minutos deve ser um inteiro nao negativo")

    por_equipamento = {}
    for solicitacao in solicitacoes:
        if not isinstance(solicitacao, (tuple, list)) or len(solicitacao) != 3:
            raise ValueError("solicitacao deve ter equipamento, minuto e procedimento")

        equipamento, minuto, procedimento = solicitacao
        if not isinstance(equipamento, str) or not equipamento:
            raise ValueError("equipamento deve ser um texto nao vazio")
        if not _inteiro_nao_negativo(minuto):
            raise ValueError("minuto deve ser um inteiro nao negativo")
        if not isinstance(procedimento, str) or not procedimento:
            raise ValueError("procedimento deve ser um texto nao vazio")

        por_equipamento.setdefault(equipamento, []).append((minuto, procedimento))

    grupos = []
    for equipamento, itens in por_equipamento.items():
        itens.sort(key=lambda item: item[0])
        inicio = fim = None
        procedimentos = []
        procedimentos_vistos = set()
        quantidade = 0

        def concluir_grupo():
            if inicio is not None:
                grupos.append(
                    (
                        equipamento,
                        inicio,
                        fim,
                        tuple(procedimentos),
                        quantidade,
                    )
                )

        for minuto, procedimento in itens:
            if fim is None or minuto - fim > janela_minutos:
                concluir_grupo()
                inicio = minuto
                procedimentos = []
                procedimentos_vistos = set()
                quantidade = 0

            fim = minuto
            quantidade += 1
            if procedimento not in procedimentos_vistos:
                procedimentos_vistos.add(procedimento)
                procedimentos.append(procedimento)

        concluir_grupo()

    return sorted(grupos, key=lambda grupo: (grupo[1], grupo[0]))
