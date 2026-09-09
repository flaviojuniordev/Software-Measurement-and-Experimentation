# Kata 04 — Ciclos de rega

Uma fazenda vertical mede a umidade de várias bandejas. Um ciclo de rega começa
quando a umidade fica menor ou igual ao limite baixo e termina quando chega ao
limite alto. Falhas longas de telemetria invalidam um ciclo em andamento.

Implemente:

```python
detectar_ciclos_rega(medicoes, limite_baixo, limite_alto, intervalo_maximo)
```

Cada medição é `(bandeja, minuto, umidade)`. A entrada pode estar fora de ordem e
deve ser processada separadamente por bandeja, em ordem de minuto; empates preservam
a ordem original.

Regras:

- inicia-se um ciclo na primeira leitura `<= limite_baixo`;
- durante um ciclo, novas leituras baixas não o reiniciam;
- o primeiro valor `>= limite_alto` encerra o ciclo;
- se a diferença entre duas medições consecutivas da bandeja for maior que
  `intervalo_maximo`, descarte o ciclo aberto antes de processar a nova medição;
- ciclos que continuarem abertos no fim também são descartados.

Cada resultado é `(bandeja, inicio, fim, menor_umidade, quantidade_leituras)`.
Ordene por início e depois pelo nome da bandeja.

Os três limites devem ser inteiros não negativos, `limite_baixo` deve ser menor que
`limite_alto` e `intervalo_maximo` deve ser positivo. Cada medição deve ter bandeja
não vazia, minuto inteiro não negativo e umidade inteira entre 0 e 100. Lance
`ValueError` quando o contrato for violado.

## Exemplo

```python
medicoes = [
    ("norte", 8, 64),
    ("norte", 2, 28),
    ("norte", 5, 22),
]

detectar_ciclos_rega(medicoes, 30, 60, 5)
# [("norte", 2, 8, 22, 3)]
```

## Executar os testes

```bash
pytest katas/kata_04/tests -q
```

