"""Starter da Kata 02."""


def planejar_despachos(capsulas, capacidade, max_paradas):
    """Monta viagens do correio pneumático preservando a fila.

    Consulte o README da kata para o contrato completo.
    """
    if (
        not isinstance(capacidade, int)
        or isinstance(capacidade, bool)
        or capacidade <= 0
        or not isinstance(max_paradas, int)
        or isinstance(max_paradas, bool)
        or max_paradas <= 0
    ):
        raise ValueError("limites invalidos")

    validadas = []
    codigos_vistos = set()
    for capsula in capsulas:
        if not isinstance(capsula, (tuple, list)) or len(capsula) != 4:
            raise ValueError("capsula invalida")
        codigo, destino, volume, urgente = capsula
        if not isinstance(codigo, str) or not codigo:
            raise ValueError("codigo invalido")
        if codigo in codigos_vistos:
            raise ValueError("codigo duplicado")
        if not isinstance(destino, str) or not destino:
            raise ValueError("destino invalido")
        if (
            not isinstance(volume, int)
            or isinstance(volume, bool)
            or volume <= 0
            or volume > capacidade
        ):
            raise ValueError("volume invalido")
        if not isinstance(urgente, bool):
            raise ValueError("urgente invalido")
        codigos_vistos.add(codigo)
        validadas.append(capsula)

    viagens = []
    codigos = []
    destinos = []
    volume_total = 0

    def fechar_viagem():
        nonlocal codigos, destinos, volume_total
        if codigos:
            viagens.append((tuple(codigos), tuple(destinos), volume_total, False))
            codigos = []
            destinos = []
            volume_total = 0

    for codigo, destino, volume, urgente in validadas:
        if urgente:
            fechar_viagem()
            viagens.append(((codigo,), (destino,), volume, True))
            continue

        novo_destino = destino not in destinos
        if (
            volume_total + volume > capacidade
            or (novo_destino and len(destinos) >= max_paradas)
        ):
            fechar_viagem()

        codigos.append(codigo)
        if destino not in destinos:
            destinos.append(destino)
        volume_total += volume

    fechar_viagem()
    return viagens
