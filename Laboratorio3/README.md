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

- cliente REST/GraphQL proprio, sem PyGithub, com HTTPS via `certifi`;
- autenticacao por `GITHUB_TOKEN`;
- paginacao, cache comprimido, retomada, rate limit e backoff exponencial;
- descoberta por faixas de estrelas, sem o teto de 1.000 resultados da busca,
  seguida de ordem pseudoaleatoria reproduzivel;
- selecao de candidatos, metadados, contribuidores e funil;
- releases por GraphQL, com fallback REST paginado em lotes de 30;
- tags e commits por Git parcial, sem blobs, com fallback para a API REST;
- deployment frequency e lead time por release e por commit;
- coleta adaptativa e concorrente de workflow runs, subdividindo somente
  intervalos com 1.000 ou mais resultados;
- filtro defensivo para `push` no default branch e deduplicacao por `run.id`;
- CFR baseado em CI, episodios de falha, recuperacao e censura;
- CFR por entrega com heuristica versionada de release corretiva e censura;
- amostra-ouro reproduzivel, concordancia, consenso e avaliacao da heuristica;
- classificacoes DORA individuais e classificacao geral;
- checkpoint transacional em SQLite, dados brutos normalizados e exportacao em
  Apache Parquet;
- testes sem rede e CI no GitHub Actions.

## Preparacao

Requer Python 3.12 e Git instalado. A partir da raiz do repositorio:

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
python3 -m pipeline --config config.json
```

Para gerar a amostra parcial de 30 repositorios usada no checkpoint da Sprint 2:

```bash
python3 -m pipeline \
  --config config.json \
  --limit 300 \
  --target-included 30 \
  --fast-partial
```

Por padrao, `config.json` permite examinar ate 4.000 candidatos e encerra a
coleta quando 300 repositorios validos forem incluidos. `--limit` substitui o
limite de candidatos, nao o tamanho da amostra final. A opcao
`--target-included` encerra a execucao quando o funil atingir a quantidade
informada de repositorios validos; ela permite gerar amostras parciais sem
confundir candidatos processados com repositorios aprovados.

Para entregas parciais, `--fast-partial` registra e pula candidatos que atingem
o teto de 1.000 workflow runs no intervalo consultado, ultrapassam 5.000 runs na
janela ou possuem mais de 50 releases. Isso evita que um unico repositorio extremo
monopolize a execucao. A coleta definitiva deve omitir essa opcao para remover
esses limites, subdividir os intervalos e produzir a amostra completa exigida.

`config.json` tambem controla os limites de estrelas, releases e workflow runs,
coleta de tags, uso do transporte Git, diretorio do cache Git, semente da ordem
dos candidatos, exportacao Parquet, quantidade de workers, tentativas e timeout.
Nenhuma data academica fica oculta no codigo.

## Arquitetura otimizada da coleta

A otimizacao altera o transporte e a persistencia, nao os filtros, a janela nem
as formulas do experimento:

| Dado | Fonte principal | Salvaguarda |
|---|---|---|
| candidatos, repositorio, contribuidores e workflows | REST | faixas de estrelas, ordem com semente 42, cache e retry |
| releases publicadas | GraphQL com campos minimos | REST, `per_page=30` |
| workflow runs | REST adaptativo, com 4 workers | subdivisao antes do teto de 1.000 |
| tags | `git ls-remote --tags` | REST paginado |
| commits entre releases | tags ausentes em lotes, fetch Git parcial e `git log` | endpoint REST `compare` |

O cache Git e bare e fica em `.cache/git`. Antes das comparacoes, o pipeline
identifica em uma unica consulta local as tags ja presentes e busca somente as
ausentes em lotes limitados, com `--filter=blob:none`. Tags compartilhadas por
comparacoes consecutivas nao sao baixadas novamente, inclusive depois de uma
interrupcao; o conteudo dos arquivos nao e usado. A equivalencia foi verificada
em uma comparacao real do repositorio `psf/requests`: Git e REST retornaram os
mesmos 128 SHAs. Essa estrategia preserva os dados usados nas metricas e evita
armazenar respostas REST gigantes de comparacoes.

O SQLite registra somente o resultado de cada repositorio concluido e permite
retomar no proximo candidato depois de uma interrupcao. Os payloads volumosos
ficam apenas em `data/raw`, sem uma segunda copia no banco. Os CSVs continuam
sendo os artefatos academicos; Parquet e uma representacao normalizada adicional
gerada em lotes para leitura e analise eficientes.

Os candidatos ainda precisam satisfazer `stars:>1000`, mas os ainda nao
processados nao sao percorridos do maior para o menor numero de estrelas. Eles
sao ordenados por uma chave pseudoaleatoria estavel com semente 42. Isso evita
concentrar o inicio da coleta nos maiores e mais ativos projetos e reduz vies de
popularidade. Ao retomar, candidatos ja concluidos aparecem primeiro, garantindo
que uma coleta de 100 validos possa ser ampliada para 300 sem perder os 100.

## Coleta de workflow runs

`pipeline.collectors.collect_workflow_runs` inicia com toda a janela inclusiva.
Cada consulta usa `branch=<default_branch>`, `event=push` e
`created=<inicio>..<fim>`. Se o `total_count` indicar 1.000 resultados ou mais,
o intervalo e dividido ao meio antes de buscar as paginas restantes. O processo
continua recursivamente ate cada consulta ficar abaixo do teto do GitHub.

Intervalos independentes e paginas adicionais sao buscados com concorrencia
limitada. O padrao de quatro workers aumenta o aproveitamento da cota sem criar
concorrencia ilimitada; o mesmo controle de rate limit e retry continua sendo
compartilhado por todas as requisicoes. O terminal informa a quantidade de
intervalos e paginas processadas dentro de cada repositorio.

Os resultados ainda sao validados localmente e deduplicados por `run.id`. Se um
unico dia atingir o teto de 1.000 resultados, a coleta falha explicitamente em
vez de produzir uma metrica silenciosamente truncada.

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

O pipeline tambem exporta a variante de CFR por entrega nas colunas
`release_change_failure_rate`, `release_cfr_evaluated`, `release_cfr_failed` e
`release_cfr_censored`. A classificacao DORA existente continua baseada no CFR
de CI; a nova variante e preservada separadamente para a RQ03(b).

A heuristica corretiva inicial, identificada como `v1`, considera uma release
corretiva quando ocorre pelo menos um destes criterios:

- apenas o numero de patch aumenta em duas tags SemVer validas;
- as release notes ou mensagens de commits contem `fix`, `hotfix` ou `revert`,
  sem diferenciar maiusculas de minusculas.

Uma release avaliada falha quando a proxima release principal e corretiva e foi
publicada em ate sete dias. Releases dos sete ultimos dias da janela sao
censuradas e ficam fora do denominador.

## Validacao manual da heuristica

Os comandos abaixo partem de `Laboratorio3`. O diretorio `data/raw` e produzido
pela coleta e precisa conter o payload correspondente a cada repositorio do
dataset. Os arquivos brutos e o cache permanecem locais e nao sao versionados.

Para acrescentar o CFR por entrega a uma copia de um checkpoint antigo, sem
sobrescrever o artefato consolidado:

```bash
python -m pipeline.validation cfr \
  --dataset data/repositories_s02_partial.csv \
  --raw-dir data/raw \
  --output data/repositories_s02_partial_luidi.csv \
  --start-date 2025-10-01 \
  --end-date 2026-09-30
```

Antes de gerar as planilhas, o comando abaixo recupera somente releases e
comparacoes dos 60 repositorios sorteados. Ele nao repete a coleta pesada de
workflow runs dos 300 repositorios:

```bash
python -m pipeline.validation hydrate-gold-sample \
  --dataset data/repositories_s02.csv \
  --raw-dir data/raw \
  --cache-dir .cache/github \
  --start-date 2025-10-01 \
  --end-date 2026-09-30
```

O modo final sorteia exatamente 60 repositorios com `random_state=42`, gera
arquivos cegos separados para Flavio e Luidi e falha claramente se o dataset
tiver menos de 60:

```bash
python -m pipeline.validation gold-sample \
  --dataset data/repositories_s02.csv \
  --raw-dir data/raw \
  --output-dir data/validation \
  --start-date 2025-10-01 \
  --end-date 2026-09-30
```

O checkpoint historico de 30 repositorios exige a opcao explicita
`--allow-partial`, e os quatro templates gerados recebem o sufixo `_partial`:

```bash
python -m pipeline.validation gold-sample \
  --dataset data/repositories_s02_partial.csv \
  --raw-dir data/raw \
  --output-dir data/validation \
  --start-date 2025-10-01 \
  --end-date 2026-09-30 \
  --allow-partial
```

Os templates dos dois avaliadores deixam todos os julgamentos humanos vazios,
nunca incluem a previsao da heuristica e trazem links para a release e para a
comparacao de commits. Depois de Flavio e Luidi preencherem seus arquivos de
forma independente, a concordancia e as pendencias sao geradas com:

```bash
python -m pipeline.validation agreement \
  --flavio-repositories data/validation/flavio_repositories.csv \
  --flavio-releases data/validation/flavio_releases.csv \
  --luidi-repositories data/validation/luidi_repositories.csv \
  --luidi-releases data/validation/luidi_releases.csv \
  --output-dir data/validation/agreement
```

Com dois avaliadores nao existe maioria. Apos a reuniao, preencha as colunas
`consensus_*` dos arquivos de pendencias e gere o consenso validado:

```bash
python -m pipeline.validation consensus \
  --flavio-repositories data/validation/flavio_repositories.csv \
  --flavio-releases data/validation/flavio_releases.csv \
  --luidi-repositories data/validation/luidi_repositories.csv \
  --luidi-releases data/validation/luidi_releases.csv \
  --repository-resolutions data/validation/agreement/pending_repositories.csv \
  --release-resolutions data/validation/agreement/pending_releases.csv \
  --output-dir data/validation/consensus
```

Por fim, avalie precisao, recall, F1 e matriz de confusao contra o consenso:

```bash
python -m pipeline.validation evaluate \
  --consensus-releases data/validation/consensus/consensus_releases.csv \
  --raw-dir data/raw \
  --history data/validation/heuristic_evaluations.json \
  --version v1
```

Se o F1 ficar abaixo de 0,70, use um novo nome em `--version` e ajuste
`--keywords` e/ou `--no-patch-rule`. Cada versao e acrescentada ao historico;
uma versao existente nunca e substituida silenciosamente.

## Cache e retomada

Cada resposta completa da API e armazenada comprimida em `.cache/github` com a
extensao `.json.gz`; caches antigos `.json` continuam legiveis. A gravacao usa
arquivo temporario e troca atomica, portanto respostas interrompidas nao entram
no cache. `IncompleteRead`, erros HTTP transitorios e JSON incompleto reutilizam
o mesmo retry/backoff do cliente.

O arquivo `data/collection_state.sqlite3` guarda, em transacao, somente os
repositorios ja concluidos e suas linhas consolidadas. Executar novamente o mesmo comando
reaproveita o cache HTTP, o cache Git e esse estado, continuando sem recoletar os
repositorios finalizados. Nao remova esses artefatos durante uma execucao.

## Saidas

- `data/selection_funnel.csv`: decisao de inclusao por repositorio;
- `data/selection_funnel_summary.csv`: totais por etapa;
- `data/selection_funnel.json`: funil e motivos de descarte;
- `data/repositories_s01.csv`: metricas de velocidade, estabilidade e DORA,
  incluindo o CFR por entrega, conforme produzido pelo pipeline;
- `data/repositories_s02.csv`: snapshot final e imutavel da Sprint 2 com 300
  repositorios distintos;
- `data/repositories_s02_partial.csv`: snapshot validado com 30 repositorios
  distintos para a entrega parcial da Sprint 2;
- `data/raw/*.json`: repositorio, workflows, releases, tags, comparacoes e runs.
- `data/collection_state.sqlite3`: checkpoint transacional para retomada;
- `data/parquet/*.parquet`: tabelas normalizadas adicionais, comprimidas com
  Zstandard, para analise eficiente.

O dicionario das colunas esta em `docs/dicionario_dados_s01.md`. A introducao e
as hipoteses formuladas antes da coleta estao em `docs/introducao.md`. A
metodologia definitiva e o funil real estao em `docs/metodologia_s02.md`; o
protocolo parcial permanece em `docs/metodologia_s02_parcial.md` como historico.

## Testes e cobertura

```bash
python3 -m pytest
```

`pytest.ini` executa toda a suite e exige no minimo 80% de cobertura em
`pipeline.metrics`. Os testes usam fixtures, fakes e respostas simuladas; nenhuma
chamada real a API e feita. O mesmo comando e executado por
`.github/workflows/lab03-tests.yml` em pushes e pull requests que alterem o Lab03.

## Escopo ainda pendente

A amostra final de 300 repositorios, as metricas, o dicionario e a metodologia
estao consolidados. Kappas, consenso e precisao/recall/F1 so podem ser produzidos
depois que Flavio e Luidi preencherem independentemente as planilhas da
amostra-ouro. Permanecem para a Sprint 3 as analises estatisticas de RQ01 a RQ07.
