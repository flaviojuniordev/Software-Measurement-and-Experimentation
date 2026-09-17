"""Starter da Kata 04."""


def detectar_ciclos_rega(
    medicoes, limite_baixo, limite_alto, intervalo_maximo
):
    """Detecta ciclos completos de rega.

    Consulte o README da kata para o contrato completo.
    """

    # Validação dos limites
    if (
        not isinstance(limite_baixo, int)
        or isinstance(limite_baixo, bool)
        or limite_baixo < 0
    ):
        raise ValueError("limite_baixo inválido")

    if (
        not isinstance(limite_alto, int)
        or isinstance(limite_alto, bool)
        or limite_alto < 0
    ):
        raise ValueError("limite_alto inválido")

    if (
        not isinstance(intervalo_maximo, int)
        or isinstance(intervalo_maximo, bool)
        or intervalo_maximo <= 0
    ):
        raise ValueError("intervalo_maximo inválido")

    if limite_baixo >= limite_alto:
        raise ValueError("limite_baixo deve ser menor que limite_alto")

    try:
        medicoes = list(medicoes)
    except TypeError:
        raise ValueError("medições inválidas")

    # Validação das medições
    for medicao in medicoes:
        if not isinstance(medicao, (tuple, list)) or len(medicao) != 3:
            raise ValueError("medição malformada")

        bandeja, minuto, umidade = medicao

        if not isinstance(bandeja, str) or bandeja.strip() == "":
            raise ValueError("bandeja inválida")

        if (
            not isinstance(minuto, int)
            or isinstance(minuto, bool)
            or minuto < 0
        ):
            raise ValueError("minuto inválido")

        if (
            not isinstance(umidade, int)
            or isinstance(umidade, bool)
            or umidade < 0
            or umidade > 100
        ):
            raise ValueError("umidade inválida")

    # Separa as medições por bandeja
    bandejas = {}

    for medicao in medicoes:
        bandeja, minuto, umidade = medicao

        if bandeja not in bandejas:
            bandejas[bandeja] = []

        bandejas[bandeja].append((minuto, umidade))

    ciclos = []

    # Processa cada bandeja separadamente
    for bandeja, leituras in bandejas.items():

        # O sorted mantém a ordem original caso os minutos sejam iguais
        leituras = sorted(leituras, key=lambda x: x[0])

        ciclo_aberto = False
        inicio = None
        menor_umidade = None
        quantidade_leituras = 0
        minuto_anterior = None

        for minuto, umidade in leituras:

            # Verifica se houve uma falha longa de telemetria
            if (
                minuto_anterior is not None
                and minuto - minuto_anterior > intervalo_maximo
            ):
                # Se havia um ciclo aberto, ele é descartado
                if ciclo_aberto:
                    ciclo_aberto = False
                    inicio = None
                    menor_umidade = None
                    quantidade_leituras = 0

            # Se não existe ciclo, verifica se deve começar
            if not ciclo_aberto:
                if umidade <= limite_baixo:
                    ciclo_aberto = True
                    inicio = minuto
                    menor_umidade = umidade
                    quantidade_leituras = 1

            else:
                # Toda leitura durante o ciclo é contabilizada
                quantidade_leituras += 1

                if umidade < menor_umidade:
                    menor_umidade = umidade

                # Verifica se o ciclo terminou
                if umidade >= limite_alto:
                    ciclos.append(
                        (
                            bandeja,
                            inicio,
                            minuto,
                            menor_umidade,
                            quantidade_leituras,
                        )
                    )

                    ciclo_aberto = False
                    inicio = None
                    menor_umidade = None
                    quantidade_leituras = 0

            minuto_anterior = minuto

    # Ordena pelo início e depois pelo nome da bandeja
    ciclos.sort(key=lambda ciclo: (ciclo[1], ciclo[0]))

    return ciclos