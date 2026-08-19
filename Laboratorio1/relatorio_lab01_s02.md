# Lab01S02 - Relatorio inicial da parte do Flavio

## Integrantes

- Flavio de Souza Ferreira Jr
- Luidi Cadete

## Divisao planejada da Sprint 2

**Flavio - coleta base e RQ01/RQ02/RQ06**

- Entregar: paginacao para 1.000 repositorios e arquivo `output/coleta_1000.csv`.
- Validar: idade do repositorio, PRs aceitas e percentual de issues fechadas.
- Escrever no relatorio: hipoteses e resultados preliminares de RQ01, RQ02 e RQ06.

**Luidi - RQ03/RQ04/RQ05/RQ07 e Project**

- Entregar: validacao das metricas restantes e snapshot do GitHub Projects.
- Validar: releases, ultima atualizacao, linguagem primaria e dados ausentes.
- Escrever no relatorio: hipoteses/resultados de RQ03, RQ04, RQ05 e comparacao por linguagem da RQ07.

Esta branch implementa e documenta apenas a parte do **Flavio**. A coleta gera um CSV unico com todos os campos necessarios ao grupo, mas a discussao abaixo cobre RQ01, RQ02 e RQ06.

## Hipoteses informais - Flavio

**RQ01 - Sistemas populares sao maduros/antigos?**  
Hipotese: a maioria dos repositorios populares tera varios anos de existencia, pois projetos acumulam estrelas ao longo do tempo. Ainda assim, devem existir outliers recentes ligados a IA, ferramentas de desenvolvimento e projetos que viralizaram rapidamente.

**RQ02 - Sistemas populares recebem muita contribuicao externa?**  
Hipotese: repositorios populares tendem a ter muitas pull requests aceitas, mas a distribuicao deve ser assimetrica. Projetos com governanca ativa e comunidade grande devem concentrar os maiores valores.

**RQ06 - Sistemas populares possuem alto percentual de issues fechadas?**  
Hipotese: projetos com manutencao ativa devem apresentar percentual alto de issues fechadas, mas alguns repositorios muito populares podem manter muitas issues abertas devido ao volume de usuarios e contribuicoes.

## Pendencias planejadas para Luidi

Luidi deve completar a primeira versao do relatorio com as hipoteses e validacoes de RQ03, RQ04, RQ05 e RQ07. Para RQ05/RQ07, a fonte definida para "linguagens mais populares" deve ser mantida ao longo do laboratorio: GitHub Octoverse 2025, em <https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/>.

## Metodologia de coleta

A coleta usa a API GraphQL do GitHub por meio de script proprio em Python, sem bibliotecas de mineracao de terceiros. A ordenacao dos repositorios e feita pela busca `stars:>1 sort:stars-desc`, com tipo `REPOSITORY`.

Na Sprint 2, a consulta passa a usar paginacao por cursor (`pageInfo.hasNextPage` e `pageInfo.endCursor`) em paginas de 50 repositorios, ate atingir 1.000 repositorios. Para evitar timeout ao consultar `releases.totalCount`, o script coleta primeiro os dados principais e depois complementa as contagens de releases em lotes menores por GraphQL.

O arquivo de dados gerado pela parte do Flavio e:

```text
Laboratorio1/github-mining/output/coleta_1000.csv
```

Para facilitar a revisao local do laboratorio inteiro, tambem foi criada uma interface Tkinter:

```text
Laboratorio1/github-mining/app_lab01.py
```

Ela carrega o CSV, mostra resumos das RQs 01-07, permite filtrar repositorios por linguagem, exibe a comparacao por linguagem da RQ07 e oferece acao para exportar o snapshot do GitHub Projects.

Colunas usadas diretamente por Flavio:

- `repository_rank`
- `name_with_owner`
- `stargazer_count`
- `created_at`
- `age_days`
- `merged_pull_requests`
- `issues_total`
- `issues_closed`
- `closed_issues_ratio`

## Resultados preliminares - Flavio

Resumo da coleta:

| Metrica | Valor preliminar |
|---|---:|
| Repositorios coletados | 1.000 |
| Repositorios unicos | 1.000 |
| Mediana de idade (`age_days`) | 2.829,11 dias |
| Mediana de PRs aceitas (`merged_pull_requests`) | 768 |
| Mediana de issues fechadas (`closed_issues_ratio`) | 87,61% |
| Repositorios sem razao de issues fechadas | 43 |

Validacoes realizadas no CSV:

- `repository_rank` sequencial de 1 a 1000;
- nenhum repositorio duplicado;
- nenhum caso com `issues_closed > issues_total`;
- nenhum valor negativo em PRs aceitas, releases ou contagens de issues;
- `closed_issues_ratio` vazio apenas quando nao ha issues para calcular a razao.

Leitura preliminar: os resultados iniciais sustentam as hipoteses do Flavio. A mediana de idade indica repositorios maduros, a mediana de PRs aceitas sugere colaboracao externa relevante, e a mediana de issues fechadas aponta para manutencao ativa. Os 43 casos sem razao de issues fechadas devem ser ignorados na estatistica de RQ06, pois representam repositorios sem issues.

## Configuracao do processo

O GitHub Projects v2 do grupo deve usar Issues reais do repositorio como cards, com Assignee preenchido. As colunas minimas sao:

```text
Backlog -> To Do -> Doing -> Review -> Done
```

Politica de WIP sugerida: limite de **2 cards em Doing**, um por integrante ativo. Esse limite reduz paralelismo excessivo e facilita visualizar bloqueios.

O snapshot do Project fica planejado para a parte do Luidi nesta Sprint 2.

## Issues sugeridas para a Sprint 2

| Issue | Responsavel | Descricao |
|---|---|---|
| Lab01S02 - coleta 1000 e RQ01/RQ02/RQ06 | Flavio | gerar CSV, validar idade/PRs/issues e escrever a parte correspondente do relatorio |
| Lab01S02 - RQ03/RQ04/RQ05/RQ07 e snapshot | Luidi | validar releases/atualizacao/linguagens, comparar por linguagem e exportar snapshot do Project |

Link do repositorio/GitHub Projects: `<preencher>`
