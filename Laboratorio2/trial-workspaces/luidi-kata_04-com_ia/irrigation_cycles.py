"""Starter da Kata 04."""


def detectar_ciclos_rega(
    medicoes, limite_baixo, limite_alto, intervalo_maximo
):
    """Detecta ciclos completos de rega.

    Consulte o README da kata para o contrato completo.
    """
    limites = (limite_baixo, limite_alto, intervalo_maximo)
    if any(isinstance(valor, bool) or not isinstance(valor, int) for valor in limites):
        raise ValueError("Os limites devem ser inteiros.")
    if limite_baixo < 0 or limite_alto < 0 or intervalo_maximo <= 0:
        raise ValueError("Os limites devem ser não negativos e o intervalo, positivo.")
    if limite_baixo >= limite_alto:
        raise ValueError("O limite baixo deve ser menor que o limite alto.")

    por_bandeja = {}
    for ordem, medicao in enumerate(medicoes):
        if not isinstance(medicao, (tuple, list)) or len(medicao) != 3:
            raise ValueError("Medição inválida.")

        bandeja, minuto, umidade = medicao
        if not isinstance(bandeja, str) or not bandeja.strip():
            raise ValueError("A bandeja deve ter um nome não vazio.")
        if isinstance(minuto, bool) or not isinstance(minuto, int) or minuto < 0:
            raise ValueError("O minuto deve ser um inteiro não negativo.")
        if (
            isinstance(umidade, bool)
            or not isinstance(umidade, int)
            or not 0 <= umidade <= 100
        ):
            raise ValueError("A umidade deve ser um inteiro entre 0 e 100.")

        por_bandeja.setdefault(bandeja, []).append((minuto, ordem, umidade))

    ciclos = []
    for bandeja, leituras in por_bandeja.items():
        ciclo = None
        minuto_anterior = None

        for minuto, _, umidade in sorted(leituras):
            if (
                minuto_anterior is not None
                and minuto - minuto_anterior > intervalo_maximo
            ):
                ciclo = None
            minuto_anterior = minuto

            if ciclo is None:
                if umidade <= limite_baixo:
                    ciclo = [minuto, umidade, 1]
                continue

            ciclo[1] = min(ciclo[1], umidade)
            ciclo[2] += 1
            if umidade >= limite_alto:
                ciclos.append((bandeja, ciclo[0], minuto, ciclo[1], ciclo[2]))
                ciclo = None

    return sorted(ciclos, key=lambda item: (item[1], item[0]))
