#!/usr/bin/env python3
"""Coleta métricas estáticas da solução final de um trial do Lab02."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BASE_DIR / "data" / "static_metrics.csv"
CSV_FIELDS = [
    "participant",
    "kata",
    "treatment",
    "loc",
    "avg_cyclomatic_complexity",
    "maintainability_index",
    "duplication_percentage",
]


class MetricsError(RuntimeError):
    """Erro esperado ao preparar ou coletar métricas."""


def python_files(solution_dir: Path) -> list[Path]:
    """Lista código Python, sem testes, caches e diretórios ocultos."""
    files = []
    for path in solution_dir.rglob("*.py"):
        relative_parts = path.relative_to(solution_dir).parts
        excluded = any(
            part in {"tests", "__pycache__"} or part.startswith(".")
            for part in relative_parts
        )
        if not excluded:
            files.append(path)
    return sorted(files)


def require_radon() -> None:
    if importlib.util.find_spec("radon") is None:
        raise MetricsError(
            "Radon não encontrado. A partir de Laboratorio2, execute: "
            "python3 -m pip install -r requirements.txt"
        )


def jscpd_command() -> list[str]:
    local_names = ("jscpd.cmd", "jscpd") if sys.platform == "win32" else ("jscpd",)
    for name in local_names:
        candidate = BASE_DIR / "node_modules" / ".bin" / name
        if candidate.is_file():
            return [str(candidate)]

    executable = shutil.which("jscpd")
    if executable:
        return [executable]

    npx = shutil.which("npx")
    if npx:
        # --no-install impede download silencioso durante um trial.
        return [npx, "--no-install", "jscpd"]

    raise MetricsError(
        "jscpd não encontrado. Instale Node.js e, a partir de Laboratorio2, "
        "execute: npm install"
    )


def run_json(command: Sequence[str], tool_name: str) -> dict[str, Any]:
    completed = subprocess.run(
        list(command), capture_output=True, text=True, encoding="utf-8", check=False
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        raise MetricsError(f"{tool_name} falhou (código {completed.returncode}): {details}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise MetricsError(f"{tool_name} retornou JSON inválido.") from error


def complexity_values(items: list[dict[str, Any]]) -> list[float]:
    """Extrai complexidade de funções/métodos sem contar classes duas vezes."""
    values: list[float] = []
    for item in items:
        item_type = item.get("type")
        if item_type in {"F", "M", "function", "method"} and "complexity" in item:
            values.append(float(item["complexity"]))
        for nested_key in ("methods", "closures"):
            nested = item.get(nested_key)
            if isinstance(nested, list):
                values.extend(complexity_values(nested))
    return values


def radon_metrics(solution_dir: Path) -> tuple[int, float, float]:
    require_radon()
    base = [sys.executable, "-m", "radon"]
    target = str(solution_dir)
    raw = run_json([*base, "raw", "-j", target], "Radon raw")
    cc = run_json([*base, "cc", "-j", target], "Radon cc")
    mi = run_json([*base, "mi", "-j", target], "Radon mi")

    loc_by_file = {
        path: int(values.get("sloc", 0))
        for path, values in raw.items()
        if isinstance(values, dict)
    }
    loc = sum(loc_by_file.values())

    complexities: list[float] = []
    for blocks in cc.values():
        if isinstance(blocks, list):
            complexities.extend(complexity_values(blocks))
    avg_complexity = fmean(complexities) if complexities else 0.0

    weighted_sum = 0.0
    weighted_loc = 0
    unweighted: list[float] = []
    for path, values in mi.items():
        if not isinstance(values, dict) or "mi" not in values:
            continue
        score = float(values["mi"])
        unweighted.append(score)
        file_loc = loc_by_file.get(path, 0)
        if file_loc:
            weighted_sum += score * file_loc
            weighted_loc += file_loc
    maintainability = (
        weighted_sum / weighted_loc
        if weighted_loc
        else (fmean(unweighted) if unweighted else 0.0)
    )
    return loc, avg_complexity, maintainability


def duplication_from_report(report: dict[str, Any]) -> float:
    """Lê o percentual de linhas duplicadas dos formatos atuais do jscpd."""
    statistics = report.get("statistics", {})
    total = statistics.get("total", {}) if isinstance(statistics, dict) else {}
    lines = total.get("lines", {}) if isinstance(total, dict) else {}
    if isinstance(lines, dict) and "percentage" in lines:
        return float(lines["percentage"])
    if isinstance(total, dict) and "percentage" in total:
        return float(total["percentage"])
    raise MetricsError("Relatório do jscpd não contém o percentual total de linhas duplicadas.")


def duplication_metric(solution_dir: Path) -> float:
    command = jscpd_command()
    # Manter o relatório temporário no projeto evita restrições de escrita que o
    # processo Node filho pode encontrar no diretório temporário global.
    with tempfile.TemporaryDirectory(prefix=".jscpd-", dir=BASE_DIR) as temp_dir:
        report_dir = Path(temp_dir)
        try:
            target = Path(
                os.path.relpath(solution_dir.resolve(), BASE_DIR.resolve())
            ).as_posix()
        except ValueError:
            # No Windows, unidades diferentes nao possuem caminho relativo comum.
            target = solution_dir.resolve().as_posix()
        completed = subprocess.run(
            [
                *command,
                "--format",
                "python",
                "--reporters",
                "json",
                "--output",
                report_dir.name,
                "--min-lines",
                "3",
                "--min-tokens",
                "20",
                "--no-gitignore",
                "--ignore",
                "**/{tests,__pycache__,.*}/**",
                target,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            cwd=BASE_DIR,
        )
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout).strip()
            missing = any(
                text in details.lower()
                for text in ("could not determine executable", "not found", "canceled")
            )
            if command[-1] == "jscpd" and missing:
                raise MetricsError(
                    "jscpd não encontrado. A partir de Laboratorio2, execute: npm install"
                )
            raise MetricsError(f"jscpd falhou (código {completed.returncode}): {details}")

        reports = sorted(report_dir.rglob("*.json"))
        if not reports:
            raise MetricsError("jscpd não gerou o relatório JSON esperado.")
        try:
            report = json.loads(reports[0].read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise MetricsError("jscpd gerou um relatório JSON inválido.") from error
        return duplication_from_report(report)


def append_metrics(csv_path: Path, row: dict[str, Any]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow(row)


def collect_metrics(
    *, solution_dir: Path, participant: str, kata: str, treatment: str, output: Path
) -> dict[str, Any]:
    solution_dir = solution_dir.resolve()
    if not solution_dir.is_dir():
        raise MetricsError(f"Diretório de solução não encontrado: {solution_dir}")
    if not python_files(solution_dir):
        raise MetricsError(f"Nenhum arquivo Python de solução encontrado em: {solution_dir}")
    if not participant.strip() or not kata.strip():
        raise MetricsError("Participante e kata são obrigatórios.")

    loc, avg_complexity, maintainability = radon_metrics(solution_dir)
    duplication = duplication_metric(solution_dir)
    row = {
        "participant": participant.strip(),
        "kata": kata.strip(),
        "treatment": treatment,
        "loc": loc,
        "avg_cyclomatic_complexity": f"{avg_complexity:.3f}",
        "maintainability_index": f"{maintainability:.3f}",
        "duplication_percentage": f"{duplication:.3f}",
    }
    append_metrics(output.resolve(), row)
    return row


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Coleta Radon e jscpd da solução final de um trial."
    )
    parser.add_argument("solution_dir", type=Path, help="Diretório da solução final.")
    parser.add_argument("--participant", required=True)
    parser.add_argument("--kata", required=True)
    parser.add_argument("--treatment", required=True, choices=("com_ia", "sem_ia"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    try:
        row = collect_metrics(
            solution_dir=args.solution_dir,
            participant=args.participant,
            kata=args.kata,
            treatment=args.treatment,
            output=args.output,
        )
    except MetricsError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 2
    print(
        "Métricas registradas em "
        f"{args.output.resolve()}: {row['participant']} / {row['kata']} / {row['treatment']}."
    )
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
