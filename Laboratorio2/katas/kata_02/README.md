# Kata 02 — Despachos do correio pneumático

Um laboratório envia cápsulas por um correio pneumático. As cápsulas chegam em uma
fila e devem ser reunidas em viagens sem mudar a ordem de chegada.

Implemente:

```python
planejar_despachos(capsulas, capacidade, max_paradas)
```

Cada cápsula é `(codigo, destino, volume, urgente)`, onde `urgente` é booleano.
Uma viagem comum recebe a maior sequência possível sem ultrapassar `capacidade` e
sem exceder `max_paradas` destinos distintos. A ordem dos destinos é a ordem da
primeira ocorrência na viagem.

Uma cápsula urgente sempre viaja sozinha: ela fecha uma viagem comum anterior,
forma sua própria viagem e a cápsula seguinte inicia outra viagem.

Cada viagem retornada é:

```text
(codigos, destinos, volume_total, urgente)
```

`codigos` e `destinos` são tuplas. A lista vazia produz lista vazia. Lance
`ValueError` quando capacidade ou máximo de paradas não forem inteiros positivos;
quando uma cápsula estiver malformada; quando código ou destino forem vazios;
quando o volume não for inteiro positivo ou exceder a capacidade; quando `urgente`
não for booleano; ou quando houver códigos repetidos.

## Exemplo

```python
capsulas = [
    ("c1", "bio", 3, False),
    ("c2", "quimica", 4, False),
    ("c3", "raio-x", 2, True),
    ("c4", "bio", 5, False),
]

planejar_despachos(capsulas, capacidade=8, max_paradas=2)
# [
#   (("c1", "c2"), ("bio", "quimica"), 7, False),
#   (("c3",), ("raio-x",), 2, True),
#   (("c4",), ("bio",), 5, False),
# ]
```

## Executar os testes

```bash
pytest katas/kata_02/tests -q
```

