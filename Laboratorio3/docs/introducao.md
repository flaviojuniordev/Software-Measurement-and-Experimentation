# Introducao e hipoteses iniciais

As metricas DORA sao usadas para caracterizar a capacidade de uma equipe entregar
software com velocidade e estabilidade. Entretanto, repositorios publicos do
GitHub nao registram diretamente deploys e falhas em producao. Este estudo utiliza
releases, commits e execucoes do GitHub Actions como proxies observaveis, reconhecendo
que uma release de uma biblioteca nao equivale necessariamente a um deploy em um
ambiente produtivo.

O objetivo e minerar dados de repositorios open source populares que utilizam
GitHub Actions e descrever seu desempenho segundo definicoes operacionais comuns.
O pipeline foi projetado para ser reexecutavel por outro grupo, com paginacao,
cache, retomada, tratamento de rate limit, testes automatizados e registro do funil
de selecao.

As hipoteses abaixo foram formuladas antes da observacao dos resultados.

## RQ01 - Frequencia de deploys

Espera-se que a maioria dos repositorios apresente frequencia moderada de releases,
entre mensal e semanal. Embora os projetos sejam populares e usem CI/CD, muitos sao
bibliotecas ou ferramentas que nao precisam publicar uma nova versao diariamente.

## RQ02 - Lead time for changes

Espera-se que o lead time calculado por release seja maior e mais variavel que o
lead time por commit. Um unico commit antigo incluido em uma release aumenta muito
a variante baseada no commit mais antigo, mas possui menor influencia sobre a
mediana de todos os commits.

## RQ03 - Change failure rate

Espera-se que a taxa baseada em falhas de CI seja superior a taxa baseada em
releases corretivas. O pipeline de CI tambem captura problemas de testes, lint e
configuracao que podem ser corrigidos antes de qualquer entrega aos usuarios.

## RQ04 - Tempo de recuperacao

Espera-se que a maioria dos episodios de falha de CI seja recuperada em menos de
24 horas, pois projetos populares tendem a receber manutencao frequente. Ainda
assim, espera-se encontrar episodios censurados, sem uma execucao bem-sucedida ate
o final da janela.

## RQ05 - Frequencia de deploy e taxa de falha

Espera-se uma associacao fraca ou potencialmente inversa entre frequencia de
deploy e change failure rate. Uma frequencia maior nao implica necessariamente
mais instabilidade: entregas menores, automacao e feedback rapido podem permitir
que velocidade e estabilidade coexistam. A hipotese sera examinada separadamente
para os proxies de falha de CI e de release corretiva.

## RQ06 - Caracteristicas associadas ao desempenho DORA

Espera-se que caracteristicas como popularidade, numero de contribuidores, idade,
linguagem principal e tipo de projeto estejam associadas a diferencas nas metricas
DORA. Essas relacoes podem refletir ecossistemas, praticas de automacao e perfis de
manutencao distintos; nao serao interpretadas como evidencia de causalidade.

## RQ07 - Sensibilidade as definicoes operacionais

Espera-se que parte dos repositorios mude de categoria quando releases forem
substituidas ou ampliadas por pre-releases e tags, ou quando forem usadas variantes
de lead time e CFR. Ao mesmo tempo, espera-se maior estabilidade de classificacao
para projetos cujos indicadores estejam distantes dos limites entre Elite, High,
Medium e Low. Nenhum percentual de mudanca ou nivel de concordancia e antecipado.

Essas expectativas nao constituem resultados e poderao ser confirmadas ou
contraditas somente apos a coleta completa e as analises das proximas sprints.
