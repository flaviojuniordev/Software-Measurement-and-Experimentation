# Lab01S02 - GitHub Mining

Planejamento e execucao da Sprint 2 mantendo a divisao usada na Sprint 1.

## Divisao de responsabilidades

**Flavio - coleta base e RQ01/RQ02/RQ06**

- Entregar: paginacao para 1.000 repositorios e arquivo `output/coleta_1000.csv`.
- Validar: idade do repositorio, PRs aceitas e percentual de issues fechadas.
- Escrever no relatorio: hipoteses e resultados preliminares de RQ01, RQ02 e RQ06.

**Luidi - RQ03/RQ04/RQ05/RQ07 e Project**

- Entregar: validacao das metricas restantes e snapshot do GitHub Projects.
- Validar: releases, ultima atualizacao, linguagem primaria e dados ausentes.
- Escrever no relatorio: hipoteses/resultados de RQ03, RQ04, RQ05 e comparacao por linguagem da RQ07.

Esta branch tambem inclui uma interface visual geral para o Lab01. A interface nao pertence a uma pessoa especifica: ela carrega o CSV do grupo, resume RQ01-RQ07 e oferece acao para snapshot do GitHub Projects.

## O que o script coleta

| RQ | Pergunta | Campo/valor usado |
|---|---|---|
| **RQ01** | Sistemas populares sao maduros/antigos? | `createdAt` + `age_days` |
| **RQ02** | Recebem muita contribuicao externa? | `pullRequests(states: MERGED).totalCount` |
| **RQ03** | Lancam releases com frequencia? | `releases.totalCount` |
| **RQ04** | Sao atualizados com frequencia? | `updatedAt` + `days_since_update` |
| **RQ05** | Sao escritos nas linguagens mais populares? | `primaryLanguage.name` |
| **RQ06** | Possuem alto percentual de issues fechadas? | `issues.closed / issues.total` |

Para RQ05/RQ07, Luidi deve manter a fonte definida pelo grupo para "linguagens mais populares": GitHub Octoverse 2025, em <https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/>.

## Estrutura

```text
github-mining/
+-- query.py                          # coleta de repositorios + paginacao + CSV
+-- app_lab01.py                      # interface visual do Lab01
+-- project_snapshot.py               # exportacao do GitHub Projects v2
+-- queries/rq01_rq02_rq06.graphql    # query GraphQL das RQs 01-06
+-- output/                           # evidencias de coleta
+-- snapshots/                        # snapshots do Project por sprint
```

## Como rodar

Configure `GITHUB_TOKEN` em `.env` ou no ambiente e execute:

```bash
cd Laboratorio1/github-mining

# validacao pequena
python3 query.py --limit 10 --no-save

# Sprint 2: coleta paginada dos 1.000 repositorios em CSV
python3 query.py --limit 1000
```

Arquivo entregue pela parte do Flavio:

```text
output/coleta_1000.csv
```

## Interface visual do Lab01

```bash
cd Laboratorio1/github-mining
python3 app_lab01.py
```

A interface carrega `output/coleta_1000.csv`, mostra resumo das RQs 01-07, lista validacoes, permite filtrar e paginar a tabela de repositorios, mostra a comparacao por linguagem da RQ07 e possui uma aba para exportar o snapshot do GitHub Projects. O botao `Coletar 1000` executa `query.py --limit 1000` e recarrega o CSV ao final.

Fluxo esperado na interface:

1. Abrir `app_lab01.py`.
2. Para demonstrar do zero, clicar em `Limpar dados e CSV`.
3. Na aba `Coleta`, clicar em `Coletar 1000 repositorios e gerar CSV`.
4. Acompanhar o progresso pela aba `Log`.
5. Ao final, conferir o arquivo `output/coleta_1000.csv`, que pode ser aberto no Excel.
6. Navegar pelas abas `Resumo`, `RQs`, `Validacao`, `Linguagens e RQ07` e `Repositorios`.
7. Na aba `Repositorios`, usar busca, filtro de linguagem e paginacao local para revisar os 1.000 itens sem sobrecarregar a tabela.
8. Na aba `Project`, exportar o snapshot quando o token possuir permissao `read:project`.

## Validacao da parte do Flavio

O CSV deve ser conferido especialmente nestes pontos:

- 1.000 linhas de dados e 1.000 repositorios unicos;
- `repository_rank` sequencial de 1 a 1000;
- `age_days` preenchido para RQ01;
- `merged_pull_requests` nao negativo para RQ02;
- `issues_closed <= issues_total` para RQ06;
- `closed_issues_ratio` vazio apenas quando `issues_total` for zero.

Valores vazios em `closed_issues_ratio` sao esperados quando o repositorio nao possui issues; nesses casos nao existe denominador para calcular a razao.

## Sprints 2 e 3

Para a coleta paginada da Sprint 2, execute:

```bash
python3 query.py --limit 1000
```

A interface principal do Lab01 e um site local. Ela concentra a coleta, o acompanhamento de log, as RQs, a busca pelos repositorios, a comparacao por linguagem, os graficos da Sprint 3 e o snapshot do GitHub Projects.

```bash
python3 web_lab01.py
```

Abra `http://127.0.0.1:8000` no navegador. Na aba `S03 - Analise`, o botao gera os resultados das sete RQs e os graficos em `output/sprint3/`, prontos para o relatorio. A parte de RQ03, RQ04, RQ05 e RQ07 tambem pode ser reproduzida sem a interface:

```bash
python3 analyze_lab01_s03_luidi.py
```

O script salva `luidi_results.json`, atualiza o `sprint3_results.json` combinado e preserva a implementacao de RQ01, RQ02 e RQ06 no script separado do Flavio.

```text
github-mining/
├── web_lab01.py                      # servidor local da interface web
├── web/                              # frontend HTML, CSS e JavaScript
├── analyze_lab01_s03.py              # analise e graficos de RQ01, RQ02 e RQ06
├── analyze_lab01_s03_luidi.py        # analise e graficos de RQ03, RQ04, RQ05 e RQ07
└── project_snapshot.py               # snapshot do GitHub Projects v2
```

## Commits

Referencie a Issue correspondente em cada commit:

```text
#12 implementa paginacao e CSV da S02 para RQ01 RQ02 RQ06
```
