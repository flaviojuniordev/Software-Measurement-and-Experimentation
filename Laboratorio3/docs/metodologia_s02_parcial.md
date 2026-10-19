# Metodologia - entrega parcial da Sprint 2

## Escopo

Esta entrega apresenta um checkpoint reproduzivel com 30 repositorios validos e
distintos. O enunciado estabelece 300 repositorios apos os filtros para a amostra
final da Sprint 2; portanto, os resultados deste snapshot sao preliminares e nao
devem ser interpretados como a amostra completa.

## Fonte e janela

O checkpoint original foi obtido pela API REST publica do GitHub. A coleta
definitiva preserva as mesmas fontes semanticas, filtros e janela, mas usa REST,
GraphQL e o protocolo Git conforme o tipo de dado. O cliente usa token em
variavel de ambiente, paginacao, cache e retomada. A janela fixa cobre
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
na janela ou quando o intervalo consultado atinge o teto de 1.000 runs. A
coleta final deve omitir essa opcao e processar os intervalos subdivididos.

## Estrategia de coleta definitiva otimizada

A mudanca de arquitetura nao altera a metodologia academica. Ela reduz o volume
transferido e torna interrupcoes recuperaveis:

1. a busca de candidatos percorre faixas de estrelas para superar o limite de
   1.000 resultados de uma unica busca do GitHub; os candidatos ainda nao
   processados recebem uma ordem pseudoaleatoria reproduzivel com semente 42,
   evitando concentrar a amostra somente nos projetos de maior popularidade;
2. releases usam GraphQL com apenas os campos necessarios; o fallback REST usa
   paginas de 30 itens;
3. workflow runs comecam em uma consulta anual e o intervalo e subdividido
   recursivamente quando o `total_count` alcanca o teto de 1.000; intervalos e
   paginas independentes usam concorrencia limitada e o mesmo rate limiter;
4. tags usam `git ls-remote`, sem checkout, e possuem fallback REST;
5. commits entre duas releases sao obtidos de um repositorio bare parcial; as
   tags ja presentes sao reutilizadas e somente as ausentes sao buscadas em
   lotes, sem blobs, antes dos comandos `git log`; o endpoint REST `compare`
   permanece como fallback;
6. respostas completas sao comprimidas, e um checkpoint SQLite registra apenas
   o resultado de cada repositorio concluido, sem duplicar os workflow runs.
   Tabelas Parquet normalizadas sao exportadas em lotes a partir dos JSONs como
   representacao adicional aos CSVs e JSONs exigidos.

A equivalencia do caminho Git foi validada em `psf/requests`, entre as tags
`v2.31.0` e `v2.32.0`: tanto Git quanto REST retornaram exatamente os mesmos
128 SHAs. Essa validacao verifica o conjunto que alimenta o lead time, sem mudar
as regras de inclusao ou as formulas DORA.

## Metricas e integridade

O snapshot contem deployment frequency, as duas variantes de lead time, CFR de
CI, episodios de falha, censura, tempo mediano de recuperacao e classificacoes
DORA. As 30 linhas possuem nome unico, payload bruto correspondente e valores
para deployment frequency, lead time, CFR de CI e contagem de runs validos.

Quatro repositorios nao possuem mediana de recuperacao porque nenhum episodio de
falha recuperado foi observado na janela. Esses valores permanecem vazios em vez
de serem convertidos artificialmente em zero.

## Heuristica de release corretiva e CFR por entrega

A heuristica inicial e versionada como `v1`. Ela marca uma release como
corretiva quando pelo menos um dos criterios abaixo e satisfeito:

1. as tags anterior e atual seguem SemVer e apenas o numero de patch aumenta;
2. as release notes ou uma mensagem de commit entre as releases contem os
   termos `fix`, `hotfix` ou `revert`, sem diferenciar maiusculas de minusculas.

Para o CFR por entrega, uma release R falha se a proxima release principal for
classificada como corretiva e ocorrer no maximo sete dias depois. Releases
publicadas nos sete ultimos dias da janela sao censuradas e excluidas do
denominador. O pipeline registra separadamente releases avaliadas, falhas e
censuradas, alem da taxa `falhas / avaliadas`. O CFR de CI permanece disponivel
como a outra variante obrigatoria da RQ03.

## Protocolo da amostra-ouro

O script usa a semente fixa `random_state=42`. No modo final, ele sorteia
exatamente 60 repositorios do dataset definitivo e cinco releases principais de
cada repositorio. Se houver menos de 60 repositorios, o modo final termina com
erro. O modo `--allow-partial` e deliberadamente separado: neste checkpoint ele
usa os 30 repositorios disponiveis e identifica os templates com o sufixo
`_partial`.

Flavio e Luidi rotulam seus proprios arquivos de modo cego e independente. Os
templates nao exibem a classificacao da heuristica. Cada avaliador registra o
tipo do projeto, se releases representam entregas reais e, para as cinco
releases sorteadas, se cada uma e corretiva. Nenhum rotulo e preenchido
automaticamente.

Depois da rotulagem, o script calcula o kappa de Fleiss exigido pelo enunciado e
o kappa de Cohen como complemento apropriado aos dois avaliadores atualmente
previstos, nas tres dimensoes. Com dois avaliadores nao existe maioria: toda
divergencia e exportada como pendencia e so recebe consenso depois de discussao
em reuniao. O gerador de consenso rejeita qualquer pendencia sem resolucao
humana explicita.

O consenso de releases e a referencia para avaliar a heuristica. O script
calcula precisao, recall, F1 e a matriz de confusao. Cada versao registra seus
criterios e resultados em um historico cumulativo. Se o F1 ficar abaixo de
0,70, uma nova versao pode ser definida e comparada, sem substituir a anterior.
Enquanto os dois arquivos independentes e o consenso nao existirem, nenhum
kappa, consenso ou resultado de classificacao e apresentado.

## Artefatos

- `data/repositories_s02_partial.csv`: dataset parcial com 30 repositorios;
- `data/selection_funnel.csv`: decisao individual para os 140 candidatos;
- `data/selection_funnel_summary.csv`: totais por etapa;
- `data/selection_funnel.json`: resumo e motivos de descarte;
- `docs/dicionario_dados_s01.md`: definicao, tipo e unidade das colunas.

O checkpoint continua parcial: tem 30 repositorios, enquanto o requisito final
e uma amostra de pelo menos 300 repositorios e uma amostra-ouro de 60 sorteada
do dataset definitivo. Os resultados humanos e estatisticos permanecem
pendentes ate a conclusao da rotulagem independente.
