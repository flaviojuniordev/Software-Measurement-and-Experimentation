# Ameacas a validade

## Construto

Releases publicadas nao equivalem necessariamente a deploys em producao,
principalmente em bibliotecas e ferramentas. Falhas de GitHub Actions medem
problemas de pipeline, nao incidentes percebidos por usuarios. O CFR por entrega
tambem depende de uma heuristica cuja melhor versao obteve F1 de 0,649. A analise
de sensibilidade confirma o impacto: trocar somente o proxy de CFR mudou 39,6%
das categorias gerais.

## Interna

O estudo e observacional e nao controla maturidade, tamanho da equipe, dominio,
governanca ou estrategia de release. Idade, linguagem e numero de contribuidores
estao associados a algumas metricas e podem atuar como confundidores. Datas de
autor de commits podem ser alteradas por rebase e squash. A rotulacao de Flavio
foi assistida por IA e nao constitui avaliacao cega; por isso, divergencias foram
resolvidas pelo julgamento independente de Luidi.

## Externa

A amostra inclui apenas repositorios publicos com pelo menos 1.000 estrelas,
GitHub Actions, cinco releases e 50 runs validos. Projetos privados, pequenos,
sem releases formais ou hospedados fora do GitHub nao estao representados. Os
resultados descrevem projetos open source populares e nao devem ser
generalizados diretamente para equipes corporativas.

## Conclusao

As distribuicoes sao assimetricas e possuem valores extremos; por isso foram
usados mediana, IQR e testes nao parametricos. Vinte comparacoes da RQ06 foram
corrigidas pelo metodo de Holm e acompanhadas de tamanho de efeito. Alguns
subgrupos, especialmente os tipos de projeto da amostra rotulada de 60
repositorios, possuem tamanho reduzido. Valores ausentes e censurados foram
mantidos, mas podem reduzir o poder e alterar o perfil da amostra completa.
