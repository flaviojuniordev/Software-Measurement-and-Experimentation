# Metodologia - Sprint 2

## Delineamento e fonte dos dados

O estudo e observacional e analisa repositorios publicos hospedados no GitHub.
Os dados foram coletados por um cliente proprio, sem PyGithub, usando a API REST,
a API GraphQL e o protocolo Git. A autenticacao ocorre exclusivamente pela
variavel de ambiente `GITHUB_TOKEN`. O cliente implementa paginacao, cache
comprimido, retomada por checkpoint SQLite, leitura de rate limit e repeticao com
backoff exponencial.

A janela fixa e inclusiva vai de 2025-10-01 a 2026-09-30. Um candidato precisava
ter pelo menos 1.000 estrelas, GitHub Actions configurado, cinco releases
principais publicadas na janela e 50 execucoes validas de workflow. Foram
consideradas apenas releases que nao eram draft ou prerelease e runs de evento
`push` na branch principal. A ordem dos candidatos ainda nao processados foi
pseudoaleatoria, com semente 42, para reduzir a concentracao nos projetos de
maior popularidade.

## Funil de selecao

A execucao definitiva omitiu os limites exclusivos do checkpoint parcial e
encerrou ao atingir 300 repositorios validos. O funil observado foi:

| Etapa | Quantidade |
|---|---:|
| Candidatos processados | 922 |
| Com GitHub Actions | 759 |
| Com pelo menos 5 releases | 365 |
| Com pelo menos 50 workflow runs validos | 300 |
| Incluidos na amostra final | 300 |

Entre os candidatos processados, 163 foram descartados por ausencia de GitHub
Actions, 393 por releases insuficientes, 60 por runs insuficientes e seis por
erro de coleta. O CSV final contem 300 identificadores `owner/repository`
distintos.

## Coleta e persistencia

Releases foram consultadas por GraphQL com os campos estritamente necessarios e
fallback REST paginado. Workflow runs foram coletadas pela API REST; intervalos
com 1.000 ou mais resultados foram subdivididos recursivamente ate ficarem abaixo
do teto da busca. Intervalos e paginas independentes usaram quatro workers com o
mesmo controle compartilhado de cota.

Tags foram obtidas por `git ls-remote`. Commits entre releases foram coletados em
repositorios bare parciais, sem blobs, com fallback para o endpoint REST
`compare`. A equivalencia entre os dois transportes foi verificada em
`psf/requests`, no intervalo entre `v2.31.0` e `v2.32.0`, com os mesmos 128 SHAs.
Cada repositorio concluido foi registrado em SQLite antes da atualizacao dos
CSVs. Os CSVs sao os artefatos principais e as tabelas Parquet sao uma
representacao normalizada adicional.

## Definicoes operacionais

Deployment frequency e o numero de releases principais na janela dividido pela
quantidade de semanas. O lead time possui duas variantes: mediana, por release,
entre a publicacao e o commit mais antigo da comparacao; e mediana global das
idades de todos os commits associados as releases.

O change failure rate de CI e `falhas / (falhas + sucessos)`. `failure`,
`timed_out` e `startup_failure` contam como falha; `success` conta como sucesso;
demais conclusoes sao ignoradas. Um episodio de recuperacao comeca na primeira
falha posterior a um sucesso observado do mesmo workflow e termina no proximo
sucesso. Episodios sem sucesso posterior sao censurados e nao recebem duracao
artificial.

A variante de CFR por entrega considera uma release falha quando a proxima
release principal e classificada como corretiva e ocorre em ate sete dias. A
heuristica `v1` classifica como corretiva uma alteracao somente de patch SemVer
ou a presenca de `fix`, `hotfix` ou `revert` nas notas ou mensagens de commits.
Releases nos sete ultimos dias da janela sao censuradas. O dataset registra as
quantidades avaliadas, falhas e censuradas separadamente.

As quatro metricas recebem as categorias Elite, High, Medium ou Low conforme os
limiares definidos no protocolo do laboratorio. A classificacao geral e a
mediana das quatro pontuacoes, arredondada para baixo, e permanece ausente quando
alguma metrica necessaria nao pode ser calculada.

## Validacao manual

Uma amostra-ouro de 60 repositorios e sorteada do dataset final com
`random_state=42`. Para cada repositorio, cinco releases principais da janela
sao sorteadas com uma semente estavel derivada do nome do repositorio. O sistema
gera arquivos separados para Flavio e Luidi, sem mostrar a previsao automatica,
com links diretos para a release e para a comparacao de commits.

Cada avaliador deve registrar, de forma independente: tipo do projeto
(`biblioteca/framework`, `aplicacao/servico`, `ferramenta CLI` ou `outro`), se as
releases representam entregas reais (`sim`, `nao` ou `incerto`) e se cada uma das
300 releases sorteadas e corretiva (`sim` ou `nao`). Nenhum julgamento humano e
preenchido automaticamente.

Depois da rotulagem, o script calcula concordancia observada e kappa de Fleiss
nas tres dimensoes; como o grupo possui dois integrantes, tambem calcula kappa de
Cohen. Nao ha desempate por maioria: divergencias sao exportadas e resolvidas em
reuniao, com registro explicito do consenso. O consenso de releases e usado como
referencia para precisao, recall, F1 e matriz de confusao da heuristica. Se o F1
for inferior a 0,70, uma nova versao deve ser documentada e reavaliada sem apagar
os resultados anteriores.

## Reprodutibilidade e qualidade

O arquivo `config.json` fixa janela, filtros, semente e meta da amostra. O
dicionario em `docs/dicionario_dados_s01.md` documenta tipo, unidade, formula ou
origem de cada coluna. A suite automatizada cobre coleta, cache, retomada,
persistencia e casos de borda das metricas sem acessar a rede durante os testes.
Valores ausentes representam falta de observacoes suficientes e nao sao
convertidos artificialmente em zero. Na amostra final, 19 repositorios nao
possuem episodio recuperado e, por isso, nao recebem mediana de recuperacao. Em
um repositorio, todas as 34 releases observadas ficaram na faixa censurada dos
sete dias finais; seu CFR por entrega fica vazio porque o denominador e zero.

## Artefatos

- `data/repositories_s02.csv`: amostra final com 300 repositorios e metricas;
- `data/selection_funnel.csv`: decisao por candidato;
- `data/selection_funnel_summary.csv`: totais das etapas;
- `data/selection_funnel.json`: etapas e motivos de descarte;
- `data/validation/flavio_*.csv`: planilhas cegas de Flavio;
- `data/validation/luidi_*.csv`: planilhas cegas de Luidi;
- `docs/dicionario_dados_s01.md`: dicionario de dados completo.
