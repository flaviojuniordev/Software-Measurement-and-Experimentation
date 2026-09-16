"""Starter da Kata 02."""


def _inteiro_positivo(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def planejar_despachos(capsulas, capacidade, max_paradas):
    """Monta viagens do correio pneumático preservando a fila.

    Consulte o README da kata para o contrato completo.
    """
    if not _inteiro_positivo(capacidade) or not _inteiro_positivo(max_paradas):
        raise ValueError("capacidade e max_paradas devem ser inteiros positivos")

    validadas = []
    codigos_vistos = set()
    for capsula in capsulas:
        if not isinstance(capsula, (tuple, list)) or len(capsula) != 4:
            raise ValueError("capsula deve conter codigo, destino, volume e urgente")

        codigo, destino, volume, urgente = capsula
        if not isinstance(codigo, str) or not codigo:
            raise ValueError("codigo deve ser um texto nao vazio")
        if codigo in codigos_vistos:
            raise ValueError("codigos de capsulas nao podem se repetir")
        if not isinstance(destino, str) or not destino:
            raise ValueError("destino deve ser um texto nao vazio")
        if not _inteiro_positivo(volume) or volume > capacidade:
            raise ValueError("volume deve ser positivo e nao exceder a capacidade")
        if not isinstance(urgente, bool):
            raise ValueError("urgente deve ser booleano")

        codigos_vistos.add(codigo)
        validadas.append((codigo, destino, volume, urgente))

    viagens = []
    codigos = []
    destinos = []
    volume_total = 0

    def concluir_viagem_comum():
        nonlocal codigos, destinos, volume_total
        if codigos:
            viagens.append((tuple(codigos), tuple(destinos), volume_total, False))
            codigos = []
            destinos = []
            volume_total = 0

    for codigo, destino, volume, urgente in validadas:
        if urgente:
            concluir_viagem_comum()
            viagens.append(((codigo,), (destino,), volume, True))
            continue

        novo_destino = destino not in destinos
        excede_capacidade = volume_total + volume > capacidade
        excede_paradas = novo_destino and len(destinos) == max_paradas
        if excede_capacidade or excede_paradas:
            concluir_viagem_comum()

        codigos.append(codigo)
        volume_total += volume
        if destino not in destinos:
            destinos.append(destino)

    concluir_viagem_comum()
    return viagens
