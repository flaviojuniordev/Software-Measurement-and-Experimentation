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
| `task1_included` | booleano | - | Atende aos filtros implementados na Task 1 |
| `discard_reason` | texto ou vazio | - | Motivo do descarte no funil |
| `collection_error` | texto ou vazio | - | Mensagem registrada quando a coleta falha |

## `repositories_task1.csv`

| Coluna | Tipo | Unidade | Definicao ou formula |
|---|---|---|---|
| `tags_count` | inteiro | tags | Quantidade de tags retornadas pela API |
| `deployment_frequency_per_week` | decimal | releases/semana | Releases principais na janela / semanas da janela |
| `lead_time_release_median_hours` | decimal ou vazio | horas | Mediana de `release - commit mais antigo` por release |
| `lead_time_commit_median_hours` | decimal ou vazio | horas | Mediana de `release - commit` para todos os commits |
| `lead_time_release_observations` | inteiro | releases | Releases com comparacao e commits validos |
| `lead_time_commit_observations` | inteiro | commits | Commits utilizados na variante por commit |
| `compare_errors` | inteiro | comparacoes | Comparacoes ignoradas devido a erro da API |

As demais colunas repetem os metadados documentados no funil. As metricas de
workflow runs, CFR, recuperacao e classificacao DORA serao acrescentadas na Task 2.
