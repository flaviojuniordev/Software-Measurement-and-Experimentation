# Rotulacao humana de Flavio

Flavio realizou julgamentos humanos independentes sobre a amostra-ouro:

- `data/validation/flavio_repositories.csv`: 60 repositorios;
- `data/validation/flavio_releases.csv`: 300 releases.

Esses dois arquivos sao as planilhas oficiais de Flavio para o calculo de
concordancia com os rotulos independentes de Luidi. As planilhas de Luidi ainda
precisam ser preenchidas antes do calculo do kappa.

Os arquivos `flavio_repositories_detalhado.csv` e
`flavio_releases_detalhado.csv` preservam as justificativas e a confianca
qualitativa associadas aos mesmos julgamentos. Todas as linhas desses arquivos
identificam `evaluator=Flavio` e `eligible_for_human_agreement=sim`. Para a
analise, use os arquivos oficiais acima, evitando contar duas vezes os mesmos
rotulos.

Os arquivos `ai_suggestions_repositories.csv` e
`ai_suggestions_releases.csv` sao material auxiliar preparado por Flavio. Nesta
versao, os 360 rotulos coincidem com as sugestoes auxiliares; Flavio confirmou
que registrou seus julgamentos de modo independente. As sugestoes baseadas em IA
ou na heuristica nao constituem um terceiro avaliador humano e nao entram no
calculo de concordancia.

## Campos de repositorio

- `project_type`: `biblioteca/framework`, `aplicacao/servico`,
  `ferramenta CLI` ou `outro`;
- `releases_are_deliveries`: `sim`, `nao` ou `incerto`;
- `type_confidence` e `delivery_confidence`: confianca qualitativa;
- `rationale`: justificativa resumida.

## Campos de release

- `is_corrective`: `sim` ou `nao`;
- `release_url`: pagina da release;
- `comparison_url`: commits entre a release anterior e a atual;
- `confidence`: confianca qualitativa;
- `rationale`: sinais que motivaram a classificacao.
