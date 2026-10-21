# Pre-classificacao assistida por IA

Os arquivos `data/validation/ai_suggestions_repositories.csv` e
`data/validation/ai_suggestions_releases.csv` foram preparados por Flavio como
material auxiliar de revisao. O campo `suggestion_source` descreve o metodo da
sugestao, nao a autoria dos arquivos. Eles nao sao rotulos humanos independentes
e nao podem ser usados no calculo de
kappa, consenso ou precisao/recall/F1.

Para os repositorios, a sugestao considera descricao, topicos e finalidade
declarada no GitHub. Para as releases, a sugestao reproduz a heuristica `v1`:
incremento apenas de patch SemVer ou ocorrencia de `fix`, `hotfix` ou `revert`
nas release notes ou mensagens de commits. A coluna `rationale` informa os
sinais encontrados e `confidence` indica apenas a confianca da sugestao, nao uma
probabilidade estatistica.

O alto numero de releases sugeridas como corretivas e um alerta esperado: uma
release pode conter algum commit de correcao sem ser predominantemente
corretiva. Por isso, cada avaliador deve ler as evidencias e registrar sua
propria decisao nos arquivos oficiais, sem copiar estas sugestoes e sem consultar
o arquivo do outro avaliador.
