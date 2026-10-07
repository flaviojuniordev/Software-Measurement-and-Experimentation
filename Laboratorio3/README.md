# Laboratorio 03 - Mineracao de metricas DORA

Pipeline proprio para minerar dados publicos de repositorios que usam GitHub
Actions. A Sprint 1 processa 300 repositorios candidatos e registra, no funil,
quantos permanecem apos os filtros. O numero de candidatos nao deve ser confundido
com os 300 repositorios validos exigidos ao final da Sprint 2.

## Escopo da Task 1 - Flavio

- cliente REST sem PyGithub;
- verificacao HTTPS usando a cadeia de certificados do `certifi`;
- paginacao, cache, retomada, rate limit e backoff exponencial;
- selecao e metadados de 300 repositorios populares;
- deteccao de GitHub Actions;
- coleta de releases, tags e commits entre releases;
- funil de selecao;
- deployment frequency e lead time por release e por commit;
- testes automatizados e CI.

A coleta detalhada dos workflow runs, o CFR e o tempo de recuperacao pertencem a
Task 2 e serao integrados sobre esta base.

## Preparacao

Requer Python 3.12 ou superior.

```bash
cd Laboratorio3
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
export GITHUB_TOKEN="seu-token"
```

O token deve ter acesso de leitura aos dados publicos consultados e nunca deve ser
salvo no repositorio.

## Executar a coleta

As datas da janela nao foram informadas no enunciado recebido. Substitua os valores
abaixo pelas datas oficiais fornecidas pelo professor:

```bash
python3 -m pipeline \
  --config config.json \
  --start-date 2025-10-01 \
  --end-date 2026-09-30 \
  --limit 300
```

O exemplo ilustra apenas o formato do comando. Nao use essas datas no artigo sem
confirmar a janela oficial. Tambem e possivel preencher `start_date` e `end_date`
diretamente em `config.json` e executar:

```bash
python3 -m pipeline --config config.json
```

## Retomada e cache

Cada resposta da API e armazenada em `.cache/github`. Se o processo for
interrompido, o mesmo comando reutiliza as respostas existentes e continua a
coleta sem consumir novamente as mesmas chamadas. Os CSVs e o funil sao atualizados
apos cada repositorio processado.

Para recomecar uma coleta do zero, remova manualmente `.cache/github` e os arquivos
gerados em `data`. Nao apague o cache durante uma execucao.

## Saidas

- `data/selection_funnel.csv`: decisao de inclusao por repositorio;
- `data/selection_funnel_summary.csv`: quantidade restante em cada etapa;
- `data/selection_funnel.json`: funil e motivos de descarte;
- `data/repositories_task1.csv`: metricas da Task 1;
- `data/raw/*.json`: releases, tags, workflows e comparacoes por repositorio.

O dicionario das colunas esta em `docs/dicionario_dados_s01.md`.

## Testes

```bash
python3 -m pytest
```

Os testes usam fixtures locais e respostas simuladas. Nenhuma chamada real a API e
feita durante a suite. A cobertura minima de 80% e aplicada ao modulo de metricas.
