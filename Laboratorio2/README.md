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

## Card 2 — Preparação do experimento (Lab02S01)

Esta etapa acrescenta quatro katas autorais, seus testes de aceitação, o desenho
experimental e a coleta de métricas estáticas de RQ3. O assistente padronizado é o
ChatGPT e cada trial tem time-box máximo de **35 minutos**.

O desenho completo, as hipóteses, variáveis, contrabalanceamento e ameaças à
validade estão em [`docs/experiment_design.md`](docs/experiment_design.md).

### Preparar o ambiente

Requer Python 3, Node.js e npm. A partir de `Laboratorio2`:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\Activate.ps1     # PowerShell
python3 -m pip install -r requirements.txt
npm install
```

`requirements.txt` instala pytest e Radon. `npm install` instala o jscpd localmente.
O script de métricas também informa os comandos de instalação quando não encontra
uma dessas ferramentas.

### Katas e testes de aceitação

- `kata_01`: agenda de calibração;
- `kata_02`: despachos do correio pneumático;
- `kata_03`: empréstimos de ferramentas;
- `kata_04`: ciclos de rega.

Os starters contêm apenas a assinatura e `NotImplementedError`. Portanto, os testes
da kata selecionada começam vermelhos, como esperado:

```bash
pytest katas/kata_01/tests -q
pytest katas/kata_02/tests -q
pytest katas/kata_03/tests -q
pytest katas/kata_04/tests -q
```

O comando `pytest` sem caminho executa somente os testes de infraestrutura em
`tests/`; isso evita confundir starters intencionalmente vermelhos com regressões do
projeto.

### Inicializar um starter antes de cada trial

Crie uma pasta exclusiva por participante/kata/tratamento e copie **somente** o
starter. Exemplo em PowerShell, a partir de `Laboratorio2`:

```powershell
New-Item -ItemType Directory -Force trial-workspaces/luidi-kata_04-com_ia
Copy-Item katas/kata_04/starter/* trial-workspaces/luidi-kata_04-com_ia/
```

Exemplo em Linux/macOS:

```bash
mkdir -p trial-workspaces/luidi-kata_04-com_ia
cp katas/kata_04/starter/* trial-workspaces/luidi-kata_04-com_ia/
```

Para testar a cópia em vez do starter original, aponte `KATA_SOLUTION_DIR` para ela:

```powershell
$env:KATA_SOLUTION_DIR = (Resolve-Path trial-workspaces/luidi-kata_04-com_ia)
pytest katas/kata_04/tests -q
Remove-Item Env:KATA_SOLUTION_DIR
```

Nunca edite o starter versionado durante um trial. Preserve cada solução final em
sua pasta até que os dois participantes terminem todas as katas, evitando vazamento.

### Coletar métricas estáticas (RQ3)

Depois de encerrar o registrador e sem alterar a solução final:

```bash
python3 scripts/static_metrics.py trial-workspaces/luidi-kata_04-com_ia \
  --participant luidi \
  --kata kata_04 \
  --treatment com_ia
```

O resultado é anexado a `data/static_metrics.csv` com participante, kata,
tratamento, LOC/SLOC, complexidade ciclomática média por função/método, Maintainability
Index ponderado por SLOC e percentual de linhas duplicadas. Testes, caches e pastas
ocultas dentro da solução são excluídos. O jscpd usa clones de no mínimo 3 linhas e
20 tokens, configuração mantida igual em todos os trials.

### Verificar a infraestrutura

```bash
python3 -m unittest discover -s tests -v
pytest
```
