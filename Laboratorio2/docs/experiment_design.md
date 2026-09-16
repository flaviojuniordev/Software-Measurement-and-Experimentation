# Desenho experimental — Lab02

## Escopo e Goal GQM

**Objeto:** uso de um assistente de IA generativa na resolução de tarefas de
programação.

**Goal GQM:** analisar o uso do OpenAI Codex na resolução de katas de programação, com o
propósito de comparar seu efeito frente à codificação manual, com respeito ao tempo
de resolução, à qualidade funcional (defeitos) e à qualidade estrutural do código
produzido, do ponto de vista do grupo pesquisador, no contexto de quatro katas
autorais de dificuldade comparável resolvidas por estudantes de graduação sob um
desenho crossover within-subject e time-box fixo de 35 minutos.

> **Nota de execucao:** os trials `sem_ia` desta versao foram resolvidos manualmente
> pelo participante. Os trials `com_ia` foram resolvidos com o OpenAI Codex.

## Questões de pesquisa e hipóteses

### RQ1 — Tempo

**RQ1:** o uso do OpenAI Codex reduz o tempo necessário para resolver uma kata de
programação?

- **H0-RQ1:** não há diferença no time-to-green entre os trials `com_ia` e
  `sem_ia`.
- **H1-RQ1:** o time-to-green é menor nos trials `com_ia` do que nos trials
  `sem_ia`.

### RQ2 — Qualidade funcional

**RQ2:** o uso do OpenAI Codex reduz a quantidade de defeitos ao fim do trial?

- **H0-RQ2:** a taxa de testes passando e o número de testes falhando ao fim do
  trial não diferem entre os tratamentos.
- **H1-RQ2:** os trials `com_ia` apresentam maior taxa de testes passando e menor
  número de testes falhando do que os trials `sem_ia`.

### RQ3 — Qualidade estrutural

**RQ3:** o uso do OpenAI Codex altera a complexidade ciclomática ou a duplicação do
código produzido?

- **H0-RQ3:** não há diferença entre os tratamentos na complexidade ciclomática
  média por função nem no percentual de duplicação.
- **H1-RQ3:** ao menos uma dessas métricas estruturais difere entre os tratamentos.

## Variáveis e métricas

A variável independente é o **uso do OpenAI Codex**, com dois níveis: `com_ia` e
`sem_ia`. OpenAI Codex é o único assistente permitido nos trials com IA. Nos trials sem
IA, não se usa assistente generativo.

As variáveis dependentes são:

| RQ | Variável dependente | Operacionalização |
| --- | --- | --- |
| RQ1 | Time-to-green | Segundos desde o início até todos os testes de aceitação passarem. Sem sucesso, o trial é censurado em 35 minutos (2.100 s), nunca descartado. Resumo por mediana e IQR. |
| RQ2 | Taxa de testes passando | `passando / (passando + falhando)` no fim do trial. |
| RQ2 | Testes falhando | Contagem absoluta no fim do trial. |
| RQ3 | Complexidade ciclomática | Média aritmética da complexidade McCabe de funções e métodos, coletada pelo Radon. Classes não são contadas novamente como funções. |
| RQ3 | Duplicação | Percentual de linhas duplicadas, coletado pelo jscpd com mínimo de 3 linhas e 20 tokens por clone. |
| RQ3 | LOC (controle) | Soma das linhas de código-fonte (SLOC) do Radon, excluindo testes. Controla o possível efeito de soluções mais verbosas. |
| RQ3 | Maintainability Index (complementar) | MI do Radon agregado entre arquivos por média ponderada por SLOC. |

## Desenho e unidades experimentais

O experimento usa desenho **crossover within-subject**: cada participante recebe
duas katas e resolve cada uma duas vezes, uma com OpenAI Codex e outra por codificacao
manual. Cada participante serve como seu proprio controle na mesma kata. A unidade
experimental e um trial participante-kata-tratamento; estao planejadas oito
unidades (quatro por participante).

As katas são autorais, pouco indexadas, implementadas em Python 3, sem dependências
externas na solução e com testes de aceitação em pytest. Elas exigem transformação
de sequências, validação e estado/agrupamento, buscando dificuldade comparável e
resolução possível por estudante de graduação dentro do limite.

## Contrabalanceamento e ordem

O plano separa as duas execucoes da mesma kata por outro exercicio e inverte qual
tratamento ocorre primeiro em cada par. Isso fornece contrabalanceamento parcial
para o efeito de aprendizagem:

| Ordem | Flavio | Tratamento | Luidi | Tratamento |
| ---: | --- | --- | --- | --- |
| 1 | `kata_01` | `com_ia` | `kata_03` | `sem_ia` |
| 2 | `kata_02` | `sem_ia` | `kata_04` | `com_ia` |
| 3 | `kata_01` | `sem_ia` | `kata_03` | `com_ia` |
| 4 | `kata_02` | `com_ia` | `kata_04` | `sem_ia` |

## Protocolo de execução

1. Usar a mesma máquina e versões registradas de Python, pytest, Radon, Node.js e
   jscpd sempre que possível.
2. Inicializar uma pasta de trabalho limpa copiando apenas o conteúdo de `starter`
   da kata. Não abrir soluções de trials anteriores nem soluções de referência.
3. Iniciar `scripts/trial_recorder.py` com participante, kata e tratamento.
4. Disponibilizar o README e os testes da kata. No tratamento `com_ia`, usar somente
   o OpenAI Codex; no `sem_ia`, não usar IA generativa.
5. Trabalhar por no máximo **35 minutos**. O limite pode ser reduzido antes do
   experimento, mas nunca aumentado.
6. Executar pytest durante o trial. Ao ficar verde, encerrar imediatamente como
   `green`; aos 35 minutos, interromper e encerrar como `timebox`, registrando
   testes passando e falhando.
7. Preservar a solução final sem novas edições e executar `static_metrics.py` nessa
   pasta. Uma linha é anexada a `data/static_metrics.csv`.
8. Guardar identificadores consistentes (`flavio`/`luidi`, `kata_01`…`kata_04`,
   `com_ia`/`sem_ia`) nos dois CSVs.

## Ameaças à validade e mitigação

- **Aprendizado e efeito residual:** cada participante repete suas duas katas no
  tratamento oposto, portanto a segunda execucao pode se beneficiar da primeira.
  As repeticoes sao separadas por outra kata, a ordem inicial dos tratamentos e
  alternada e a solucao anterior nao deve ser consultada, mas a ameaca permanece e
  sera destacada na interpretacao.
- **Familiaridade prévia com IA:** diferenças no domínio de prompts podem favorecer
  um participante. O assistente é fixado em OpenAI Codex e o uso observado deve ser
  relatado como limitação.
- **Vazamento de soluções:** acesso a respostas anteriores contaminaria o
  tratamento. Os starters não contêm respostas, referências temporárias não são
  versionadas e as soluções finais devem permanecer separadas até todos concluírem.
- **Memorização de katas conhecidas:** o modelo ou participante poderia reproduzir
  uma solução vista. Foram criadas quatro katas autorais e pouco indexadas.
- **Diferenca individual de habilidade:** cada participante serve como seu proprio
  controle na mesma kata, mas cada kata pertence a somente um participante. Isso
  limita a separacao entre o efeito da pessoa e o efeito do objeto experimental.
- **Amostra pequena:** dois participantes e oito trials limitam poder estatístico e
  generalização. Serão privilegiados mediana, IQR, dados individuais e tamanho de
  efeito, sem extrapolar para outras populações.
- **Efeito de ordem:** fadiga e pratica podem influenciar resultados. A separacao
  das repeticoes e a alternancia do primeiro tratamento fornecem
  contrabalanceamento parcial; ainda assim, o efeito sera discutido.

## Plano de análise futura — Sprint 3

Na Sprint 3, os resultados serão inspecionados por participante, kata e tratamento.
Para cada métrica serão reportados mediana e IQR, além dos valores individuais. Os
trials sem green continuarão no conjunto como observações censuradas em 2.100 s.

O teste inferencial planejado e o **Wilcoxon pareado**, nao parametrico e coerente
com o desenho within-subject e a amostra pequena. Cada par compara os tratamentos
`com_ia` e `sem_ia` da mesma combinacao participante-kata, produzindo quatro pares.
RQ1 e RQ2 usarao esse pareamento, e RQ3 repetira a comparacao para complexidade e
duplicacao, mantendo LOC como controle e MI como evidencia complementar. Com apenas
quatro pares e possivel efeito de aprendizagem, o Wilcoxon tera carater
exploratorio: diferencas pareadas, valores individuais, medianas/IQR e limitacoes
terao mais peso interpretativo que o valor-p.
