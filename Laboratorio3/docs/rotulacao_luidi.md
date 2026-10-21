# Rotulacao independente de Luidi Cadete Silva

Luidi realizou uma classificacao independente da amostra-ouro, sem usar os
rotulos preenchidos por Flavio nem a saida da heuristica automatica como fonte
de decisao. Os valores de Flavio so foram consultados depois da gravacao dos
arquivos de Luidi Cadete Silva, e apenas para confirmar a compatibilidade estrutural.

Foram produzidos os seguintes artefatos:

- `data/validation/luidi_repositories.csv`: 60 repositorios;
- `data/validation/luidi_releases.csv`: 300 releases;
- `data/validation/luidi_repositories_detalhado.csv`: justificativas e
  confianca para os repositorios;
- `data/validation/luidi_releases_detalhado.csv`: justificativas e confianca
  para as releases.

Os dois primeiros arquivos seguem o mesmo esquema minimo usado nas planilhas
oficiais de Flavio. Os arquivos detalhados registram
`evaluator=Luidi Cadete Silva` e `eligible_for_human_agreement=sim`, porque estes
julgamentos foram feitos por Luidi e correspondem a sua rotulacao
humana independente.

## Criterios aplicados

- `project_type`: classificado como `biblioteca/framework`,
  `aplicacao/servico`, `ferramenta CLI` ou `outro`, conforme o modo principal de
  uso do artefato;
- `releases_are_deliveries`: avalia se as releases identificam uma versao
  consumivel pelo usuario; casos documentais ambiguos recebem `incerto`;
- `is_corrective_manual`: recebe `sim` somente quando notas de release e commits
  indicam que a finalidade predominante e corrigir defeitos, regressao, falha de
  seguranca ou problema recente. Releases de funcionalidades, manutencao geral
  ou conteudo misto sem predominancia corretiva recebem `nao`.

O numero de versao foi usado apenas como evidencia contextual. Um incremento de
patch, sozinho, nao determinou o rotulo. Foram lidas as release notes e as
mensagens de commits armazenadas pela coleta para cada item sorteado.

