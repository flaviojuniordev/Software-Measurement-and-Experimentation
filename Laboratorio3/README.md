# Laboratorio 03 - Mineracao de metricas DORA

Pipeline proprio para minerar metricas DORA de repositorios publicos que usam
GitHub Actions. A implementacao da Sprint 1 integra a infraestrutura de coleta de
Flavio com a coleta de CI e as metricas de estabilidade de Luidi em um unico
comando.

O limite inicial de candidatos nao deve ser confundido com os 300 repositorios
validos exigidos ao final da Sprint 2. O funil registra cada descarte, inclusive
repositorios sem Actions, com menos de cinco releases publicadas ou com menos de
50 workflow runs validos na janela.

## Funcionalidades implementadas

- cliente REST proprio, sem PyGithub, com HTTPS via `certifi`;
- autenticacao por `GITHUB_TOKEN`;
- paginacao, cache, retomada, rate limit e backoff exponencial;
- selecao de candidatos, metadados, contribuidores e funil;
- coleta de releases, tags e commits entre releases;
- deployment frequency e lead time por release e por commit;
- coleta mensal de workflow runs usando o mesmo cliente compartilhado;
- filtro defensivo para `push` no default branch e deduplicacao por `run.id`;
- CFR baseado em CI, episodios de falha, recuperacao e censura;
- classificacoes DORA individuais e classificacao geral;
- checkpoints, dados brutos, testes sem rede e CI no GitHub Actions.

## Preparacao

Requer Python 3.12 ou superior. A partir da raiz do repositorio:

```bash
cd Laboratorio3
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
export GITHUB_TOKEN="seu-token"
```

No PowerShell, ative o ambiente com `.venv\Scripts\Activate.ps1`, use `python`
quando `python3` nao estiver disponivel e defina o token com:

```powershell
$env:GITHUB_TOKEN = "seu-token"
```

O token deve ter acesso de leitura aos dados publicos consultados e nunca deve ser
salvo no repositorio.

## Configuracao e comando unico

As datas da janela de 12 meses estao fixadas em `config.json`. A coleta completa
pode ser executada com:

```bash
python3 -m pipeline --config config.json --limit 300
```

Para gerar a amostra parcial de 30 repositorios usada no checkpoint da Sprint 2:

```bash
python3 -m pipeline \
  --config config.json \
  --limit 300 \
  --target-included 30 \
  --fast-partial
```

`--limit` controla quantos candidatos podem ser examinados. A opcao
`--target-included` encerra a execucao quando o funil atingir a quantidade
informada de repositorios validos; ela permite gerar amostras parciais sem
confundir candidatos processados com repositorios aprovados.

Para entregas parciais, `--fast-partial` registra e pula candidatos que atingem
o teto de 1.000 workflow runs em algum mes, ultrapassam 5.000 runs na janela ou
possuem mais de 50 releases. Isso evita que um unico repositorio extremo
monopolize a execucao. A coleta definitiva deve omitir essa opcao para remover
esses limites, subdividir os intervalos e produzir a amostra completa exigida.

`config.json` tambem controla os limites de estrelas, releases e workflow runs,
coleta de tags, diretorios, tentativas e timeout. Nenhuma data academica fica
oculta no codigo.

## Coleta de workflow runs

`pipeline.collectors.collect_workflow_runs` divide a janela inclusiva por meses
reais do calendario. Cada consulta usa `branch=<default_branch>`, `event=push` e
`created=<inicio>..<fim>`, e e executada por `GitHubClient.paginate`. Assim, a
coleta reutiliza automaticamente paginacao, cache, retomada, rate limit e backoff.

Os resultados ainda sao validados localmente e deduplicados por `run.id`. Se um
mes atingir o teto de 1.000 resultados imposto pelo GitHub para uma consulta
filtrada, o repositorio e registrado como erro de coleta em vez de produzir uma
metrica silenciosamente truncada.

## CFR, recuperacao e classificacao

As regras ficam centralizadas em `pipeline.metrics`:

- `success` e sucesso;
- `failure`, `timed_out` e `startup_failure` sao falhas;
- demais conclusoes, incluindo valores vazios, sao ignoradas;
- o CFR e `falhas / (falhas + sucessos)`, na escala `0.0` a `1.0`;
- episodios sao calculados separadamente por `workflow_id`;
- um episodio comeca na primeira falha apos um sucesso observado e termina no
  `updated_at` do proximo sucesso do mesmo workflow;
- falhas consecutivas formam um unico episodio;
- episodio sem sucesso posterior permanece censurado, sem duracao artificial;
- a recuperacao do repositorio e a mediana, em horas, dos episodios recuperados;
- classificacoes usam Elite, High, Medium e Low; a geral usa a mediana das quatro
  pontuacoes, arredondada para baixo, e fica vazia se alguma metrica estiver ausente.

## Cache e retomada

Cada resposta da API e armazenada em `.cache/github`. Executar novamente o mesmo
comando reutiliza as respostas e continua os checkpoints sem repetir chamadas ja
armazenadas. Nao remova o cache durante uma execucao.

## Saidas

- `data/selection_funnel.csv`: decisao de inclusao por repositorio;
- `data/selection_funnel_summary.csv`: totais por etapa;
- `data/selection_funnel.json`: funil e motivos de descarte;
- `data/repositories_s01.csv`: metricas de velocidade, estabilidade e DORA;
- `data/repositories_s02_partial.csv`: snapshot validado com 30 repositorios
  distintos para a entrega parcial da Sprint 2;
- `data/raw/*.json`: repositorio, workflows, releases, tags, comparacoes e runs.

O dicionario das colunas esta em `docs/dicionario_dados_s01.md`. A introducao e
as hipoteses formuladas antes da coleta estao em `docs/introducao.md`. O protocolo
e o funil da entrega parcial estao em `docs/metodologia_s02_parcial.md`.

## Testes e cobertura

```bash
python3 -m pytest
```

`pytest.ini` executa toda a suite e exige no minimo 80% de cobertura em
`pipeline.metrics`. Os testes usam fixtures, fakes e respostas simuladas; nenhuma
chamada real a API e feita. O mesmo comando e executado por
`.github/workflows/lab03-tests.yml` em pushes e pull requests que alterem o Lab03.

## Escopo ainda nao implementado

Permanecem para as proximas etapas o CFR por release corretiva e sua validacao
manual, a amostra final da Sprint 2 e as analises estatisticas de RQ05 a RQ07.
Esses itens nao fazem parte da integracao atual.
