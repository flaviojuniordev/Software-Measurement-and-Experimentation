# Dicionario de dados - Sprints 1 e 2

O snapshot `repositories_s02.csv` registra a amostra final de 300 repositorios
da Sprint 2. `repositories_s01.csv` e a saida operacional do pipeline e possui o
mesmo conteudo na coleta consolidada. O arquivo
`repositories_s02_partial.csv`, com 30 repositorios, e mantido apenas como
checkpoint historico. As quatro colunas de CFR por entrega integram o dataset
final.

## `selection_funnel.csv`

| Coluna | Tipo | Unidade | Definicao ou origem |
|---|---|---|---|
| `full_name` | texto | - | Identificador `owner/repository` da API |
| `stars` | inteiro | estrelas | `stargazers_count` |
| `language` | texto ou vazio | - | Linguagem principal informada pelo GitHub |
| `created_at` | data/hora | UTC | Data de criacao do repositorio |
| `age_days_at_window_end` | inteiro | dias | Diferenca entre o fim da janela e a criacao do repositorio |
| `default_branch` | texto | - | Branch principal informada pela API |
| `contributors_count` | inteiro ou vazio | pessoas | Ultima pagina do endpoint; vazio quando o GitHub recusa historicos grandes |
| `workflows_count` | inteiro | workflows | Workflows cadastrados no GitHub Actions |
| `releases_in_window` | inteiro | releases | Releases publicadas, sem draft ou prerelease, dentro da janela |
| `workflow_runs_count` | inteiro | runs | Runs de `push` no default branch coletadas na janela, antes da classificacao de `conclusion` |
| `valid_workflow_runs_count` | inteiro | runs | Runs classificadas como sucesso ou falha e usadas nas metricas |
| `task1_included` | booleano | - | Atende ao filtro de releases da coleta base |
| `s01_included` | booleano | - | Atende tambem ao minimo de workflow runs validas da Sprint 1 |
| `discard_reason` | texto ou vazio | - | Motivo do descarte no funil, incluindo limites declarados do modo parcial |
| `collection_error` | texto ou vazio | - | Mensagem registrada quando a coleta falha |

## `repositories_s01.csv` e `repositories_s02.csv`

| Coluna | Tipo | Unidade | Definicao ou formula |
|---|---|---|---|
| `tags_count` | inteiro | tags | Quantidade de tags obtidas por `git ls-remote`, com fallback para a API REST |
| `deployment_frequency_per_week` | decimal | releases/semana | Releases principais na janela / semanas da janela |
| `lead_time_release_median_hours` | decimal ou vazio | horas | Mediana de `release - commit mais antigo` por release |
| `lead_time_commit_median_hours` | decimal ou vazio | horas | Mediana de `release - commit` para todos os commits |
| `lead_time_release_observations` | inteiro | releases | Releases com comparacao e commits validos |
| `lead_time_commit_observations` | inteiro | commits | Commits utilizados na variante por commit |
| `compare_errors` | inteiro | comparacoes | Comparacoes ignoradas devido a erro da API |
| `ci_change_failure_rate` | decimal ou vazio | proporcao 0-1 | Falhas de CI / (falhas + sucessos) |
| `release_change_failure_rate` | decimal ou vazio | proporcao 0-1 | Releases seguidas em ate 7 dias por release corretiva / releases avaliadas |
| `release_cfr_evaluated` | inteiro | releases | Releases da janela fora dos sete dias finais e, portanto, avaliaveis |
| `release_cfr_failed` | inteiro | releases | Releases avaliadas cuja proxima release foi corretiva em ate sete dias |
| `release_cfr_censored` | inteiro | releases | Releases publicadas nos sete ultimos dias da janela e excluidas do denominador |
| `failure_episodes_total` | inteiro | episodios | Episodios iniciados por falha apos sucesso, agrupados por workflow |
| `failure_episodes_recovered` | inteiro | episodios | Episodios encerrados por sucesso posterior do mesmo workflow |
| `failure_episodes_censored` | inteiro | episodios | Episodios sem sucesso posterior dentro da janela |
| `censored_episodes_proportion` | decimal ou vazio | proporcao 0-1 | Episodios censurados / total de episodios |
| `median_recovery_hours` | decimal ou vazio | horas | Mediana dos tempos dos episodios efetivamente recuperados |
| `deployment_frequency_dora` | categoria | - | Elite, High, Medium ou Low para deployment frequency |
| `lead_time_dora` | categoria ou vazio | - | Categoria do lead time por release |
| `change_failure_rate_dora` | categoria ou vazio | - | Categoria do CFR de CI |
| `recovery_time_dora` | categoria ou vazio | - | Categoria da mediana de recuperacao |
| `overall_dora` | categoria ou vazio | - | Mediana das quatro pontuacoes, arredondada para baixo |

As demais colunas repetem os metadados documentados no funil. Valores vazios
representam ausencia de observacoes suficientes; o pipeline nao fabrica zero nem
uma classificacao geral quando alguma das quatro metricas esta ausente.

## Planilhas da amostra-ouro

Os arquivos `data/validation/{flavio,luidi}_repositories.csv` possuem as colunas
`repository`, `project_type` e `releases_are_deliveries`. Os arquivos
`data/validation/{flavio,luidi}_releases.csv` possuem `repository`, `release_tag`,
`release_published_at`, `release_url`, `comparison_url` e
`is_corrective_manual`. Os campos de julgamento sao propositalmente vazios na
geracao e aceitam apenas as categorias descritas em `docs/metodologia_s02.md`.

## Tabelas Parquet normalizadas

O diretorio `data/parquet` contem uma representacao adicional e comprimida dos
dados de coleta. Ela nao substitui os CSVs academicos. As tabelas
`repository_metadata`, `workflows`, `releases`, `tags`, `workflow_runs`,
`release_comparisons` e `release_commits` usam `full_name` como chave de origem.
As tabelas `repositories` e `selection_funnel` espelham as saidas consolidadas.
Campos ausentes permanecem nulos; listas e payloads desnecessarios da API nao
sao replicados.
