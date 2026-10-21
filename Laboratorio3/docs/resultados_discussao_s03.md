# Resultados e discussao - Sprint 3

## RQ01 - Frequencia de deploy

A mediana foi de 0,422 releases por semana (IQR 0,211-0,964). Pela classificacao
adotada, 7 repositorios ficaram em Elite, 64 em High, 139 em Medium e 90 em Low.
A hipotese de uma cadencia predominantemente moderada foi parcialmente
confirmada: a categoria mais comum foi Medium, mas 30% da amostra ficou em Low.

## RQ02 - Lead time for changes

O lead time por release apresentou mediana de 260,12 h (IQR 75,91-998,06),
enquanto a variante por commit teve mediana de 275,78 h (IQR
69,78-1.039,11). Em 178 dos 300 repositorios, a variante por release foi maior;
em 121 ocorreu o contrario e houve um empate. A expectativa de que a variante
por release seria globalmente maior e mais dispersa nao se confirmou nas
estatisticas agregadas, embora tenha ocorrido na maioria dos pares. A diferenca
decorre da composicao de commits e do fato de a mediana global por commit dar
mais peso a releases com muitos commits.

## RQ03 - Change failure rate

O CFR de CI teve mediana de 6,30% (IQR 2,96%-12,80%) e classificou 236
repositorios como Elite. O CFR por entrega teve mediana de 43,48% (IQR
20,00%-68,72%), com um valor ausente por censura total do denominador. A
hipotese de CFR de CI superior foi contradita. Entretanto, a concordancia pobre
para releases corretivas (Fleiss = -0,163) e o melhor F1 de apenas 0,649 mostram
que a variante por entrega e sensivel a erro de classificacao e deve ser lida
como exploratoria.

## RQ04 - Tempo de recuperacao

Entre os 281 repositorios com ao menos um episodio recuperado, a mediana foi de
3,54 h (IQR 1,05-11,15). Desses, 236 (84,0%) apresentaram mediana inferior a 24
horas. Dezenove repositorios nao receberam mediana de recuperacao por ausencia
de episodio recuperado. A hipotese de recuperacao predominantemente inferior a
um dia foi confirmada, sem substituir os casos censurados por duracoes
artificiais.

## RQ05 - Frequencia versus falha

Para o CFR de CI, a correlacao de Spearman foi positiva e fraca (rho = 0,131;
p = 0,0228; n = 300). Para o CFR por entrega, a associacao foi positiva e forte
(rho = 0,662; p < 0,001; n = 299). A hipotese de associacao fraca ou inversa foi
contradita. A diferenca entre os dois proxies, somada a baixa validade da
heuristica corretiva, impede interpretar a associacao como causalidade ou como
evidencia de falhas reais em producao.

## RQ06 - Caracteristicas associadas

Foram executados 20 testes entre cinco fatores e quatro metricas, com correcao
de Holm. Cinco associacoes permaneceram significativas:

| Fator | Metrica | p de Holm | Epsilon quadrado | Magnitude |
|---|---|---:|---:|---|
| Idade | Lead time | 2,16e-11 | 0,197 | grande |
| Idade | Deployment frequency | 4,00e-05 | 0,097 | media |
| Linguagem | Lead time | 4,00e-05 | 0,115 | media |
| Linguagem | Deployment frequency | 4,58e-04 | 0,096 | media |
| Contribuidores | Lead time | 0,0042 | 0,064 | media |

Repositorios mais novos (Q1) tiveram maior frequencia mediana (0,777/semana) e
menor lead time (86,73 h), enquanto os mais antigos (Q4) tiveram 0,288/semana e
865,61 h. Popularidade e tipo de projeto nao permaneceram significativos apos a
correcao. Os resultados sao associativos, nao causais.

## RQ07 - Sensibilidade operacional

Foram comparadas quatro combinacoes: C1 (lead time por release + CFR de CI), C2
(lead time por commit + CFR por release), C3 (lead time por commit + CFR de CI)
e C4 (lead time por release + CFR por release). A troca apenas da variante de
lead time (C1-C3) alterou 15,7% das categorias e produziu kappa ponderado de
0,785. A troca apenas do CFR (C1-C4) alterou 39,6%, com kappa de 0,446. A maior
mudanca ocorreu entre C1 e C2: 48,6%, com kappa de 0,305.

As conclusoes sao relativamente robustas a variante de lead time, mas nao a
escolha do proxy de falha. A classificacao geral de referencia C1 resultou em 18
Elite, 112 High, 135 Medium, 16 Low e 19 ausentes. Assim, qualquer afirmacao
sobre o nivel DORA geral deve declarar explicitamente a definicao operacional.
