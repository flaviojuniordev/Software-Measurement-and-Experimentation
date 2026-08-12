# Lab01S01 — Flavio de Souza Ferreira Jr e Luidi Cadete (RQ01–RQ06)

Script único da sprint para extrair via **GraphQL própria** os dados necessários às RQs 01–06 e validar em uma amostra de **5–10** repositórios antes da coleta definitiva de 100 repositórios.

## O que esta parte coleta

| RQ | Pergunta | Campo GraphQL |
|---|---|---|
| **RQ01** | Repos populares são maduros/antigos? | `createdAt` (+ idade em dias no script) |
| **RQ02** | Recebem muita contribuição externa? | `pullRequests(states: MERGED).totalCount` |
| **RQ03** | Lançam releases com frequência? | `releases.totalCount` |
| **RQ04** | São atualizados com frequência? | `updatedAt` |
| **RQ05** | São escritos nas linguagens mais populares? | `primaryLanguage.name` |
| **RQ06** | Alto % de issues fechadas? | `issues.totalCount` e `issues(states: CLOSED).totalCount` |

A razão da RQ06 e a análise estatística completa ficam para sprints seguintes. Aqui o foco é **coleta correta + validação rápida**.

## Estrutura

```text
github-mining/
├── query.py                          # script próprio (HTTP + GraphQL)
├── queries/rq01_rq02_rq06.graphql    # query escrita pelo grupo (parte I1)
├── .env.example
├── .gitignore
└── output/                           # evidências JSON da S01 (amostra e coleta final)
```

## Pré-requisito

1. Crie um [Personal Access Token](https://github.com/settings/tokens) (classic: escopo suficiente para ler repositórios públicos; fine-grained: leitura pública).
2. Exporte no terminal:

```bash
export GITHUB_TOKEN=ghp_seu_token
```

## Como rodar

```bash
cd Laboratorio1/github-mining

# gera os dois arquivos de uma vez (a amostra é de Luidi)
python3 query.py --both

# ou separado
python3 query.py --limit 10    # → output/amostra_10_luidi.json
python3 query.py --limit 100   # → output/coleta_100.json
```

| Arquivo | Uso |
|---|---|
| `output/amostra_10_flavio.json` | Validação manual de Flavio (RQ01/02/06) já realizada |
| `output/amostra_10_luidi.json` | Validação manual de Luidi (RQ03/04/05) |
| `output/coleta_100.json` | Coleta definitiva da S01 (todos os campos, após integração) |

## RQs e responsáveis

- Flavio de Souza Ferreira Jr: RQ01, RQ02 e RQ06.
- Luidi Cadete: RQ03, RQ04 e RQ05.

O script e a query já reúnem todas as RQs da S01. Paginação para 1.000 repositórios fica para **Lab01S02**.

Para não exceder o tempo de resposta do GitHub ao calcular `releases.totalCount` de 100 repositórios, a coleta definitiva busca a lista de 100 uma única vez e complementa somente as contagens de releases em lotes GraphQL de 10. A amostra de 10 usa a query completa diretamente. Não há paginação de repositórios.

## Commits

Referencie a Issue correspondente, por exemplo:

```text
#N implementa extração GraphQL RQ01 RQ02 RQ06
```
