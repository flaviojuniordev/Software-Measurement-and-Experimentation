# Laboratorio 02

## Card 1 - Registro dos trials

O registrador de trials cria um CSV para as analises de RQ1 e RQ2. Ele mantem
somente um trial ativo por vez para evitar mistura de tempos e resultados.

O campo `time_to_green_seconds` e a medida primaria da RQ1. Quando o trial
chega ao limite sem passar todos os testes, o registro e mantido como censurado
no valor do time-box, em vez de ser descartado.

### Campos gerados

- `participant`, `kata` e `treatment`: identificam o trial.
- `started_at`, `finished_at` e `elapsed_seconds`: auditoria do tempo observado.
- `time_to_green_seconds`, `censored` e `timebox_reached`: dados da RQ1.
- `tests_passed`, `tests_failed` e `success_rate`: dados da RQ2.

### Uso

Inicie o trial antes de resolver a kata:

```bash
python3 scripts/trial_recorder.py start \
  --participant flavio \
  --kata kata-01 \
  --treatment com_ia
```

Quando todos os testes de aceitacao passarem, encerre como `green`:

```bash
python3 scripts/trial_recorder.py finish \
  --outcome green \
  --tests-passed 8 \
  --tests-failed 0
```

Ao atingir o limite de 35 minutos sem sucesso, encerre como `timebox` e informe
os resultados da ultima execucao dos testes:

```bash
python3 scripts/trial_recorder.py finish \
  --outcome timebox \
  --tests-passed 5 \
  --tests-failed 3 \
  --notes "faltou tratar entrada vazia"
```

O arquivo final fica em `data/trials.csv`. O limite pode ser reduzido com
`--timebox-minutes`, mas o script rejeita valores acima de 35 minutos.

Para cancelar um inicio feito apenas para teste, sem criar uma linha no CSV:

```bash
python3 scripts/trial_recorder.py cancel
```

### Testes

```bash
python3 -m unittest discover -s tests -v
```
