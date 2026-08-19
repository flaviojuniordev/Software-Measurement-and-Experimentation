#!/usr/bin/env python3
"""Valida e resume as RQ03, RQ04, RQ05 e RQ07 da Lab01S02.

O script trabalha somente com o CSV já coletado pelo grupo. Ele não consulta a
API do GitHub e não modifica o arquivo de entrada.

Uso:
  python3 validate_luidi.py
"""

from __future__ import annotations

import csv
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "output" / "coleta_1000.csv"
OUTPUT_FILE = BASE_DIR / "output" / "validacao_luidi_s02.txt"
MISSING_LANGUAGE = "Sem linguagem detectada"
MIN_REPOSITORIES_PER_LANGUAGE = 10
OCTOVERSE_URL = (
    "https://github.blog/news-insights/octoverse/"
    "octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/"
)
OCTOVERSE_TOP_LANGUAGES = {
    "TypeScript",
    "Python",
    "JavaScript",
    "Java",
    "C#",
    "PHP",
    "Shell",
    "C++",
    "HCL",
    "Go",
}

REQUIRED_COLUMNS = {
    "repository_rank",
    "name_with_owner",
    "merged_pull_requests",
    "releases_count",
    "days_since_update",
    "primary_language",
}


def parse_non_negative_number(
    raw_value: str | None,
    *,
    field: str,
    repository: str,
    problems: list[str],
) -> float | None:
    value = (raw_value or "").strip()
    if not value:
        problems.append(f"{repository}: {field} vazio")
        return None

    try:
        number = float(value)
    except ValueError:
        problems.append(f"{repository}: {field} não numérico ({value!r})")
        return None

    if not math.isfinite(number) or number < 0:
        problems.append(f"{repository}: {field} inválido ({value!r})")
        return None
    return number


def format_number(value: float, decimals: int = 2) -> str:
    if value.is_integer():
        return f"{int(value):,}".replace(",", ".")
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def format_stats(values: list[float]) -> str:
    return (
        f"mediana {format_number(statistics.median(values))}; "
        f"média {format_number(statistics.mean(values))}; "
        f"mínimo {format_number(min(values))}; "
        f"máximo {format_number(max(values))}"
    )


def upper_outliers(values: list[float]) -> tuple[float, list[float]]:
    if len(values) < 4:
        return max(values), []
    quartiles = statistics.quantiles(values, n=4, method="inclusive")
    threshold = quartiles[2] + 1.5 * (quartiles[2] - quartiles[0])
    return threshold, [value for value in values if value > threshold]


def markdown_ranking(items: Iterable[tuple[str, int]]) -> list[str]:
    return [f"{index}. {name}: {count}" for index, (name, count) in enumerate(items, 1)]


def load_rows() -> tuple[list[dict[str, object]], list[str]]:
    if not INPUT_FILE.is_file():
        raise FileNotFoundError(f"CSV não encontrado: {INPUT_FILE}")

    problems: list[str] = []
    parsed_rows: list[dict[str, object]] = []
    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = set(reader.fieldnames or [])
        missing_columns = sorted(REQUIRED_COLUMNS - columns)
        if missing_columns:
            raise ValueError(
                "CSV sem colunas obrigatórias: " + ", ".join(missing_columns)
            )

        for row_number, row in enumerate(reader, start=2):
            repository = (row.get("name_with_owner") or "").strip()
            if not repository:
                repository = f"linha {row_number} sem name_with_owner"
                problems.append(f"{repository}: identificação ausente")

            releases = parse_non_negative_number(
                row.get("releases_count"),
                field="releases_count",
                repository=repository,
                problems=problems,
            )
            days = parse_non_negative_number(
                row.get("days_since_update"),
                field="days_since_update",
                repository=repository,
                problems=problems,
            )
            merged_prs = parse_non_negative_number(
                row.get("merged_pull_requests"),
                field="merged_pull_requests",
                repository=repository,
                problems=problems,
            )
            language = (row.get("primary_language") or "").strip() or MISSING_LANGUAGE

            parsed_rows.append(
                {
                    "repository": repository,
                    "releases": releases,
                    "days": days,
                    "merged_prs": merged_prs,
                    "language": language,
                }
            )

    if not parsed_rows:
        raise ValueError("O CSV não contém repositórios.")
    return parsed_rows, problems


def build_report(rows: list[dict[str, object]], problems: list[str]) -> str:
    release_rows = [row for row in rows if row["releases"] is not None]
    update_rows = [row for row in rows if row["days"] is not None]
    releases = [float(row["releases"]) for row in release_rows]
    days = [float(row["days"]) for row in update_rows]

    if not releases or not days:
        raise ValueError("Não há valores numéricos suficientes para RQ03 e RQ04.")

    language_counts = Counter(str(row["language"]) for row in rows)
    missing_languages = language_counts[MISSING_LANGUAGE]
    detected_languages = len(rows) - missing_languages

    zero_releases = sum(value == 0 for value in releases)
    maximum_releases = max(releases)
    maximum_release_count = sum(value == maximum_releases for value in releases)
    top_releases = sorted(
        release_rows,
        key=lambda row: (-float(row["releases"]), str(row["repository"])),
    )[:10]
    release_threshold, release_outlier_values = upper_outliers(releases)
    release_outlier_rows = sorted(
        (row for row in release_rows if float(row["releases"]) > release_threshold),
        key=lambda row: -float(row["releases"]),
    )

    updated_7 = sum(value <= 7 for value in days)
    updated_30 = sum(value <= 30 for value in days)
    updated_90 = sum(value <= 90 for value in days)
    older_year = sum(value > 365 for value in days)
    oldest_updates = sorted(
        update_rows,
        key=lambda row: (-float(row["days"]), str(row["repository"])),
    )[:10]
    update_threshold, update_outlier_values = upper_outliers(days)
    update_outlier_rows = sorted(
        (row for row in update_rows if float(row["days"]) > update_threshold),
        key=lambda row: -float(row["days"]),
    )

    octoverse_count = sum(
        count
        for language, count in language_counts.items()
        if language in OCTOVERSE_TOP_LANGUAGES
    )
    octoverse_share = octoverse_count / detected_languages if detected_languages else 0.0

    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if (
            row["language"] != MISSING_LANGUAGE
            and row["releases"] is not None
            and row["days"] is not None
            and row["merged_prs"] is not None
        ):
            groups[str(row["language"])].append(row)

    language_comparison: list[dict[str, object]] = []
    for language, language_rows in groups.items():
        if len(language_rows) < MIN_REPOSITORIES_PER_LANGUAGE:
            continue
        language_comparison.append(
            {
                "language": language,
                "count": len(language_rows),
                "prs": statistics.median(float(row["merged_prs"]) for row in language_rows),
                "releases": statistics.median(
                    float(row["releases"]) for row in language_rows
                ),
                "days": statistics.median(float(row["days"]) for row in language_rows),
            }
        )
    language_comparison.sort(key=lambda item: (-int(item["count"]), str(item["language"])))

    rq03_supported = statistics.median(releases) > 0 and zero_releases < len(releases) / 2
    rq04_supported = updated_90 > len(days) / 2
    rq05_supported = octoverse_share > 0.5

    lines = [
        "# Validação Lab01S02 - Luidi Cadete",
        "",
        f"Base analisada: `{INPUT_FILE.name}` ({len(rows)} repositórios).",
        "Análise feita exclusivamente sobre o CSV, sem nova consulta à API do GitHub.",
        "",
        "## 1. Hipóteses informais",
        "",
        "- **RQ03:** repositórios populares tendem a publicar releases, mas projetos de documentação e listas devem concentrar parte relevante dos valores zero.",
        "- **RQ04:** a maioria dos repositórios populares deve apresentar atualização recente, especialmente dentro dos últimos 90 dias.",
        "- **RQ05:** as linguagens primárias devem se concentrar nas linguagens destacadas pelo GitHub Octoverse 2025, com forte presença de TypeScript, Python e JavaScript.",
        "- **RQ07:** as medianas de contribuições, releases e tempo desde a atualização devem variar entre linguagens; linguagens frequentes e ligadas a projetos ativos tendem a ter mais PRs, mais releases e atualização mais recente.",
        "",
        "## 2. Resultados",
        "",
        "### RQ03 - Releases",
        "",
        f"- Valores válidos: {len(releases)}; inválidos/ausentes: {len(rows) - len(releases)}.",
        f"- Estatísticas: {format_stats(releases)}.",
        f"- Repositórios com zero releases: {zero_releases} ({zero_releases / len(releases):.1%}).",
        "- Top 10 repositórios com mais releases:",
    ]
    lines.extend(
        f"  {index}. {row['repository']}: {format_number(float(row['releases']))}"
        for index, row in enumerate(top_releases, 1)
    )
    lines.extend(
        [
            f"- Outliers superiores pelo critério de 1,5 x IQR: {len(release_outlier_values)} valores acima de {format_number(release_threshold)} releases.",
            "- Outliers mais relevantes: "
            + "; ".join(
                f"{row['repository']} ({format_number(float(row['releases']))})"
                for row in release_outlier_rows[:5]
            )
            + ".",
            f"- Atenção: {maximum_release_count} repositórios atingem exatamente o máximo observado de {format_number(maximum_releases)} releases; esse agrupamento no limite deve ser interpretado com cautela como possível saturação da métrica de origem.",
            "",
            "### RQ04 - Atualização",
            "",
            f"- Valores válidos: {len(days)}; inválidos/ausentes: {len(rows) - len(days)}.",
            f"- Estatísticas em dias: {format_stats(days)}.",
            f"- Atualizados nos últimos 7 dias: {updated_7} ({updated_7 / len(days):.1%}).",
            f"- Atualizados nos últimos 30 dias: {updated_30} ({updated_30 / len(days):.1%}).",
            f"- Atualizados nos últimos 90 dias: {updated_90} ({updated_90 / len(days):.1%}).",
            f"- Sem atualização há mais de 1 ano: {older_year} ({older_year / len(days):.1%}).",
            "- As faixas de 7, 30 e 90 dias são cumulativas.",
            "- Top 10 repositórios há mais tempo sem atualização:",
        ]
    )
    lines.extend(
        f"  {index}. {row['repository']}: {format_number(float(row['days']))} dias"
        for index, row in enumerate(oldest_updates, 1)
    )
    lines.extend(
        [
            f"- Outliers superiores pelo critério de 1,5 x IQR: {len(update_outlier_values)} valores acima de {format_number(update_threshold)} dias.",
            "- Outliers mais relevantes: "
            + "; ".join(
                f"{row['repository']} ({format_number(float(row['days']))} dias)"
                for row in update_outlier_rows[:5]
            )
            + ".",
            "",
            "### RQ05 - Linguagem primária",
            "",
            f"- Repositórios sem linguagem detectada: {missing_languages} ({missing_languages / len(rows):.1%}).",
            f"- Repositórios com linguagem detectada: {detected_languages}.",
            "- Valores vazios foram classificados como **Sem linguagem detectada**.",
            "- Ranking das linguagens mais frequentes:",
        ]
    )
    lines.extend(
        f"  {line}" for line in markdown_ranking(language_counts.most_common())
    )
    lines.extend(
        [
            "- Referência: GitHub Octoverse 2025. O ranking por contribuidores coloca TypeScript, Python e JavaScript nas três primeiras posições, seguido por Java e C#; o top 10 também inclui PHP, Shell, C++, HCL e Go.",
            f"- Fonte: {OCTOVERSE_URL}",
            f"- Entre os repositórios com linguagem detectada, {octoverse_count} ({octoverse_share:.1%}) usam uma linguagem do top 10 do Octoverse 2025.",
            "",
            "### RQ07 - Comparação por linguagem",
            "",
            f"Foram incluídas somente linguagens com pelo menos {MIN_REPOSITORIES_PER_LANGUAGE} repositórios e registros válidos nas três métricas. Registros sem linguagem foram excluídos desta comparação.",
            "",
            "| Linguagem | Repositórios | Mediana de PRs aceitas | Mediana de releases | Mediana de dias desde atualização |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    lines.extend(
        "| {language} | {count} | {prs} | {releases} | {days} |".format(
            language=item["language"],
            count=item["count"],
            prs=format_number(float(item["prs"])),
            releases=format_number(float(item["releases"])),
            days=format_number(float(item["days"])),
        )
        for item in language_comparison
    )

    if language_comparison:
        most_common = language_comparison[:5]
        highest_prs = max(most_common, key=lambda item: float(item["prs"]))
        highest_releases = max(most_common, key=lambda item: float(item["releases"]))
        most_recent = min(most_common, key=lambda item: float(item["days"]))
        lines.extend(
            [
                "",
                "Leitura das cinco linguagens mais frequentes:",
                "- "
                + ", ".join(
                    f"{item['language']} ({item['count']} repositórios)" for item in most_common
                )
                + ".",
                f"- {highest_prs['language']} apresenta a maior mediana de PRs aceitas nesse grupo ({format_number(float(highest_prs['prs']))}).",
                f"- {highest_releases['language']} apresenta a maior mediana de releases ({format_number(float(highest_releases['releases']))}).",
                f"- {most_recent['language']} apresenta a atualização mediana mais recente ({format_number(float(most_recent['days']))} dias).",
                "- As diferenças são descritivas e não demonstram que a linguagem causa maior atividade.",
            ]
        )

    lines.extend(
        [
            "",
            "## 3. Valores ausentes e outliers",
            "",
            f"- Problemas numéricos encontrados: {len(problems)}.",
            f"- Linguagem ausente não causa erro: os {missing_languages} casos foram mantidos como **{MISSING_LANGUAGE}**.",
            "- Releases e tempo sem atualização possuem distribuições assimétricas; por isso, as medianas representam melhor o comportamento típico que as médias.",
            "- Os outliers foram preservados no relatório, pois podem representar projetos antigos, projetos com publicação intensa ou diferenças reais de processo.",
        ]
    )
    if problems:
        lines.append("- Primeiros problemas: " + "; ".join(problems[:10]) + ".")

    lines.extend(
        [
            "",
            "## 4. Conclusão",
            "",
            "- **RQ03:** "
            + ("os dados sustentam" if rq03_supported else "os dados não sustentam integralmente")
            + " a hipótese de que a maioria dos repositórios populares publica releases.",
            "- **RQ04:** "
            + ("os dados sustentam" if rq04_supported else "os dados não sustentam")
            + " a hipótese de atualização frequente, considerando o limite de 90 dias.",
            "- **RQ05:** "
            + ("os dados sustentam" if rq05_supported else "os dados sustentam apenas parcialmente")
            + " a hipótese de concentração nas linguagens populares do Octoverse 2025.",
            "- **RQ07:** há diferenças entre as medianas por linguagem, mas a comparação é descritiva e não permite concluir causalidade.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        rows, problems = load_rows()
        report = build_report(rows, problems)
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(report, encoding="utf-8")
    except (OSError, csv.Error, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print(report, end="")
    print(f"\nRelatório salvo em: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
