# Protocolo de consenso e validacao da heuristica

## Composicao da amostra

A amostra-ouro contem 60 repositorios sorteados com `random_state=42` e cinco
releases por repositorio, totalizando 300 releases. Os dois arquivos de
rotulacao cobrem exatamente os mesmos itens e nao possuem rotulos vazios ou
fora do dominio esperado.

## Independencia das rotulacoes

A rotulacao atribuida a Flavio foi produzida a partir da pre-classificacao
assistida por IA e posteriormente revisada. A rotulacao de Luidi foi realizada
de forma independente. Como a primeira planilha coincide integralmente com a
pre-classificacao automatica, ela nao e tratada como um segundo julgamento
humano cego na interpretacao dos resultados.

Ainda assim, a concordancia entre as duas planilhas foi calculada para manter a
rastreabilidade exigida pelo protocolo:

| Dimensao | Itens | Concordancia observada | Kappa de Cohen | Kappa de Fleiss |
|---|---:|---:|---:|---:|
| Tipo do projeto | 60 | 0,883 | 0,827 | 0,827 |
| Release representa entrega | 60 | 0,983 | 0,659 | 0,658 |
| Release corretiva | 300 | 0,510 | 0,084 | -0,163 |

Foram encontradas oito divergencias nos rotulos de repositorio e 147 nos
rotulos de releases. O baixo acordo para releases corretivas indica que o
construto e ambiguo e que os criterios automaticos nao substituem uma revisao
contextual das notas e commits.

## Regra de consenso

Nos itens em que as duas planilhas concordam, o rotulo compartilhado foi
mantido. Nas divergencias, adotou-se o julgamento independente de Luidi, pois a
planilha de Flavio continha a mesma informacao usada pela pre-classificacao.
Essa regra e deterministica e esta materializada nos arquivos
`data/validation/consensus/consensus_repositories.csv` e
`data/validation/consensus/consensus_releases.csv`.

## Avaliacao e refinamento da heuristica

A heuristica inicial considera uma release corretiva quando existe mudanca
apenas no patch SemVer ou quando aparecem os termos `fix`, `hotfix` ou `revert`.
Ela foi comparada com os 300 rotulos de consenso. Como o F1 ficou abaixo de
0,70, quatro variantes adicionais foram testadas sem apagar o resultado
original.

| Versao | Patch SemVer | Palavras-chave | Precisao | Recall | F1 |
|---|---|---|---:|---:|---:|
| v1 | sim | fix, hotfix, revert | 0,484 | 0,986 | 0,649 |
| v2_no_patch | nao | fix, hotfix, revert | 0,491 | 0,957 | 0,649 |
| v3_patch_only | sim | nenhuma | 0,621 | 0,652 | 0,636 |
| v4_strong_keywords | nao | hotfix, revert | 0,330 | 0,210 | 0,257 |
| v5_patch_strong | sim | hotfix, revert | 0,523 | 0,739 | 0,613 |

Nenhuma versao atingiu F1 de 0,70. A v1 permaneceu como definicao operacional
principal por apresentar o maior F1, ainda que por margem pequena. O CFR por
release e, portanto, analisado como proxy exploratorio e recebe peso reduzido
nas conclusoes. Novas regras nao foram ajustadas especificamente para maximizar
o resultado desta amostra, evitando sobreajuste ao conjunto de 300 releases.
