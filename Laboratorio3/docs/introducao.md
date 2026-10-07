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

Essas expectativas nao constituem resultados e poderao ser confirmadas ou
contraditas somente apos a coleta completa e as analises das proximas sprints.
