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
OpenAI Codex e cada trial tem time-box máximo de **35 minutos**.

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

`requirements.txt` instala pytest, Radon, Pandas, NumPy, SciPy, Matplotlib e
Seaborn. `npm install` instala o jscpd localmente. O script de métricas também
informa os comandos de instalação quando não encontra uma dessas ferramentas.

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

Nunca edite o starter versionado durante um trial. Preserve e versione cada solucao
final em sua pasta de `trial-workspaces`, usando no commit o numero da Issue do
trial correspondente. Os CSVs gerados em `data/` tambem fazem parte da entrega; o
unico arquivo temporario ignorado pelo Git e `data/active_trial.json`.

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

## Interface web local

A interface consolida execucao, cronometro, testes, metricas e leitura dos CSVs em uma unica visao.
Os trials `sem_ia` desta versao foram resolvidos manualmente; os trials `com_ia` foram resolvidos com o OpenAI Codex.

```bash
source .venv/bin/activate
python3 web_lab02.py --port 8001
```

Acesse `http://127.0.0.1:8001` no navegador.

## Sprint 3 - Analise de RQ1 e RQ2

O script `analysis/rq1_rq2_analysis.py` valida os oito trials e seus quatro pares,
calcula mediana/IQR, diferencas pareadas, reducao percentual e speedup. Ele tambem
aplica o Wilcoxon pareado com tratamento explicito de empates e ausencia de
variacao, calcula tamanho de efeito e gera tabelas, um resumo JSON e cinco
visualizacoes em PNG/SVG.

```bash
source .venv/bin/activate
python3 analysis/rq1_rq2_analysis.py
```

Os artefatos reproduziveis ficam em `analysis/results/` e `analysis/figures/`.
A interpretacao pronta para o relatorio, incluindo as limitacoes decorrentes de
`n = 4`, esta em [`docs/results_rq1_rq2.md`](docs/results_rq1_rq2.md).

## Sprint 3 - Analise de RQ3 e dashboard final

O script `analysis/rq3_analysis.py` valida a correspondencia entre os oito trials
e as oito medicoes estaticas, calcula resumos por tratamento e diferencas
pareadas para LOC, complexidade, Maintainability Index e duplicacao. A analise
inclui Wilcoxon exato ou permutacional, correlacao bisserial de postos, intervalos
bootstrap exploratorios, correcao de Holm e sensibilidade leave-one-pair-out.

```bash
source .venv/bin/activate
python3 analysis/rq1_rq2_analysis.py
python3 analysis/rq3_analysis.py
python3 -m pytest
```

No PowerShell do Windows, ative o ambiente com
`.venv\Scripts\Activate.ps1` e substitua `python3` por `python` se necessario.
Os CSVs e JSONs reproduziveis ficam em `analysis/results/`; as cinco figuras de
RQ3 sao geradas em PNG e SVG dentro de `analysis/figures/`. O resumo JSON inclui
os hashes SHA-256 de `data/trials.csv` e `data/static_metrics.csv`.

A metodologia, os valores observados, a resposta preliminar e as limitacoes de
`n = 4` estao em [`docs/results_rq3.md`](docs/results_rq3.md).

### Abrir o dashboard consolidado

Gere primeiro as duas analises e depois inicie o servidor:

```bash
python3 analysis/rq1_rq2_analysis.py
python3 analysis/rq3_analysis.py
python3 web_lab02.py --port 8001
```

Acesse `http://127.0.0.1:8001` e abra **Analise Sprint 3**. Essa tela le os JSONs
e CSVs gerados pelos scripts, apresenta RQ1, RQ2 e RQ3 sem estatisticas fixas no
JavaScript e permite abrir cada grafico completo em uma nova aba.
