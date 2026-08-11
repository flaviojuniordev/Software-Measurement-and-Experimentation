# Lab01S01 — Flavio de Souza Ferreira Jr (RQ01 + RQ02 + RQ06)

Parte individual da sprint: extrair via **GraphQL própria** os dados necessários às RQs 01, 02 e 06, validar em amostra de **5–10** repositórios e deixar pronto para integração no script único do grupo.

## O que esta parte coleta

| RQ | Pergunta | Campo GraphQL |
|---|---|---|
| **RQ01** | Repos populares são maduros/antigos? | `createdAt` (+ idade em dias no script) |
| **RQ02** | Recebem muita contribuição externa? | `pullRequests(states: MERGED).totalCount` |
| **RQ06** | Alto % de issues fechadas? | `issues.totalCount` e `issues(states: CLOSED).totalCount` |

A razão da RQ06 e a análise estatística completa ficam para sprints seguintes. Aqui o foco é **coleta correta + validação rápida**.

## Estrutura

```text
github-mining/
├── query.py                          # script próprio (HTTP + GraphQL)
├── queries/rq01_rq02_rq06.graphql    # query escrita pelo grupo (parte I1)
├── .env.example
├── .gitignore
└── output/                           # JSON gerado localmente (ignorado no git)
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

# gera os dois arquivos de uma vez
python3 query.py --both

# ou separado
python3 query.py --limit 10    # → output/amostra_10_flavio.json
python3 query.py --limit 100   # → output/coleta_100.json
```

| Arquivo | Uso |
|---|---|
| `output/amostra_10_flavio.json` | Validação manual de Flavio (RQ01/02/06) |
| `output/amostra_10_luidi.json` | Validação manual de Luidi (RQ03/04/05) — quando ele fizer a parte dele |
| `output/coleta_100.json` | Coleta definitiva da S01 (todos os campos, após integração) |

## Integração (depois, com Luidi Cadete)

1. Unir os campos das RQ03/RQ04/RQ05 na mesma query GraphQL.
2. Rodar com `--limit 100` no script único do grupo.
3. Paginação para 1.000 repositórios fica para **Lab01S02**.

## Commits

Referencie a Issue correspondente, por exemplo:

```text
#N implementa extração GraphQL RQ01 RQ02 RQ06
```
