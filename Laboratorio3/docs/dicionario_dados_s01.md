# Dicionario de dados - Sprint 1

## `selection_funnel.csv`

| Coluna | Tipo | Unidade | Definicao ou origem |
|---|---|---|---|
| `full_name` | texto | - | Identificador `owner/repository` da API |
| `stars` | inteiro | estrelas | `stargazers_count` |
| `language` | texto ou vazio | - | Linguagem principal informada pelo GitHub |
| `created_at` | data/hora | UTC | Data de criacao do repositorio |
| `age_days_at_window_end` | inteiro | dias | Diferenca entre o fim da janela e a criacao do repositorio |
| `default_branch` | texto | - | Branch principal informada pela API |
| `contributors_count` | inteiro | pessoas | Ultima pagina do endpoint de contribuidores |
| `workflows_count` | inteiro | workflows | Workflows cadastrados no GitHub Actions |
| `releases_in_window` | inteiro | releases | Releases publicadas, sem draft ou prerelease, dentro da janela |
| `workflow_runs_count` | inteiro | runs | Runs de `push` no default branch coletadas na janela, antes da classificacao de `conclusion` |
| `valid_workflow_runs_count` | inteiro | runs | Runs classificadas como sucesso ou falha e usadas nas metricas |
| `task1_included` | booleano | - | Atende ao filtro de releases da coleta base |
| `s01_included` | booleano | - | Atende tambem ao minimo de workflow runs validas da Sprint 1 |
| `discard_reason` | texto ou vazio | - | Motivo do descarte no funil |
| `collection_error` | texto ou vazio | - | Mensagem registrada quando a coleta falha |

## `repositories_s01.csv`

| Coluna | Tipo | Unidade | Definicao ou formula |
|---|---|---|---|
| `tags_count` | inteiro | tags | Quantidade de tags retornadas pela API |
| `deployment_frequency_per_week` | decimal | releases/semana | Releases principais na janela / semanas da janela |
| `lead_time_release_median_hours` | decimal ou vazio | horas | Mediana de `release - commit mais antigo` por release |
| `lead_time_commit_median_hours` | decimal ou vazio | horas | Mediana de `release - commit` para todos os commits |
| `lead_time_release_observations` | inteiro | releases | Releases com comparacao e commits validos |
| `lead_time_commit_observations` | inteiro | commits | Commits utilizados na variante por commit |
| `compare_errors` | inteiro | comparacoes | Comparacoes ignoradas devido a erro da API |
| `ci_change_failure_rate` | decimal ou vazio | proporcao 0-1 | Falhas de CI / (falhas + sucessos) |
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
