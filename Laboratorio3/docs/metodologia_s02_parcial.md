# Metodologia - entrega parcial da Sprint 2

## Escopo

Esta entrega apresenta um checkpoint reproduzivel com 30 repositorios validos e
distintos. O enunciado estabelece 300 repositorios apos os filtros para a amostra
final da Sprint 2; portanto, os resultados deste snapshot sao preliminares e nao
devem ser interpretados como a amostra completa.

## Fonte e janela

Os dados foram obtidos pela API REST publica do GitHub, usando cliente proprio,
token em variavel de ambiente, paginacao, cache e retomada. A janela fixa cobre
2025-10-01 a 2026-09-30, totalizando 12 meses. Foram considerados apenas runs de
`push` no default branch e releases publicadas que nao eram draft ou prerelease.

## Funil de selecao

O pipeline examinou 140 candidatos ordenados por estrelas ate atingir a meta:

| Etapa | Quantidade |
|---|---:|
| Candidatos processados | 140 |
| Com GitHub Actions | 131 |
| Com pelo menos 5 releases | 69 |
| Com pelo menos 50 workflow runs validos | 30 |
| Incluidos no snapshot parcial | 30 |

Os descartes foram: 62 por releases insuficientes, 9 sem GitHub Actions, 4 por
runs insuficientes, 12 por erro ou teto da coleta parcial e 23 pelo limite de
volume de releases do modo parcial.

## Modo parcial

Para impedir que um unico projeto muito ativo consumisse toda a janela da
entrega, o comando usou `--fast-partial`. Nesse modo, o repositorio e descartado,
sem gerar linha truncada, quando possui mais de 50 releases, mais de 5.000 runs
na janela ou quando um mes atinge o teto de 1.000 runs da consulta filtrada. A
coleta final deve omitir essa opcao e processar os intervalos subdivididos.

## Metricas e integridade

O snapshot contem deployment frequency, as duas variantes de lead time, CFR de
CI, episodios de falha, censura, tempo mediano de recuperacao e classificacoes
DORA. As 30 linhas possuem nome unico, payload bruto correspondente e valores
para deployment frequency, lead time, CFR de CI e contagem de runs validos.

Quatro repositorios nao possuem mediana de recuperacao porque nenhum episodio de
falha recuperado foi observado na janela. Esses valores permanecem vazios em vez
de serem convertidos artificialmente em zero.

## Artefatos

- `data/repositories_s02_partial.csv`: dataset parcial com 30 repositorios;
- `data/selection_funnel.csv`: decisao individual para os 140 candidatos;
- `data/selection_funnel_summary.csv`: totais por etapa;
- `data/selection_funnel.json`: resumo e motivos de descarte;
- `docs/dicionario_dados_s01.md`: definicao, tipo e unidade das colunas.

A heuristica de release corretiva, a validacao manual e o consenso da
amostra-ouro pertencem ao outro card da Sprint 2 e nao sao apresentados como
concluidos neste checkpoint.
