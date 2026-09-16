# Dados do experimento

`trials.csv` e `static_metrics.csv` formam um unico conjunto de dados usado pela
interface web.

Os trials `sem_ia` foram implementados manualmente pelo participante. Os trials
`com_ia` foram resolvidos com o OpenAI Codex.

## Historico dos trials manuais

| Trial | Iteracao 1 | Iteracao 2 | Iteracao final | Tempo |
| --- | ---: | ---: | ---: | ---: |
| `flavio / kata_01 / sem_ia` | 6/10 testes | 9/10 testes | 10/10 testes | 27min23s |
| `flavio / kata_02 / sem_ia` | 4/11 testes | 10/11 testes | 11/11 testes | 28min44s |

Na Kata 01, a primeira versao nao ordenava as solicitacoes e validava apenas a
janela. A segunda corrigiu ordenacao e validacao, mas ainda repetia procedimentos.

Na Kata 02, a primeira versao considerava apenas capacidade. A segunda tratou
destinos, urgencia e validacoes, mas ainda aceitava codigos duplicados.
