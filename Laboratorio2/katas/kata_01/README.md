# Kata 01 — Agenda de calibração

Uma oficina recebe solicitações de calibração de vários equipamentos. Solicitações
próximas do mesmo equipamento devem virar uma única visita, evitando deslocamentos
desnecessários.

Implemente:

```python
agrupar_calibracoes(solicitacoes, janela_minutos)
```

Cada solicitação é uma tupla `(equipamento, minuto, procedimento)`. A entrada pode
estar fora de ordem. Para cada equipamento, ordene as solicitações pelo minuto e
agrupe solicitações consecutivas quando a diferença entre seus minutos for menor ou
igual a `janela_minutos`.

Cada grupo deve ser uma tupla:

```text
(equipamento, inicio, fim, procedimentos, quantidade)
```

- `inicio` e `fim` são o primeiro e o último minuto do grupo;
- `procedimentos` é uma tupla sem repetições, na ordem cronológica da primeira
  ocorrência;
- `quantidade` conta todas as solicitações, inclusive procedimentos repetidos.

Ordene o resultado por `inicio` e, em caso de empate, pelo nome do equipamento.
A lista vazia produz lista vazia. Lance `ValueError` se a janela for um inteiro
negativo ou se alguma solicitação não tiver exatamente um equipamento não vazio,
um minuto inteiro não negativo e um procedimento não vazio.

## Exemplo

```python
solicitacoes = [
    ("balanca-b", 20, "nivelar"),
    ("balanca-a", 10, "limpar"),
    ("balanca-a", 14, "nivelar"),
    ("balanca-a", 16, "limpar"),
]

agrupar_calibracoes(solicitacoes, 5)
# [
#   ("balanca-a", 10, 16, ("limpar", "nivelar"), 3),
#   ("balanca-b", 20, 20, ("nivelar",), 1),
# ]
```

## Executar os testes

A partir de `Laboratorio2`:

```bash
pytest katas/kata_01/tests -q
```

