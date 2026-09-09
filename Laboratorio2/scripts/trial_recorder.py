#!/usr/bin/env python3
"""Registra os trials do experimento controlado do Lab02.

O comando ``start`` abre um unico trial ativo e o comando ``finish`` o encerra,
gravando uma linha em CSV. Trials que chegam ao time-box sao mantidos como
censurados, com ``time_to_green_seconds`` igual ao limite configurado.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


MAX_TIMEBOX_MINUTES = 35
DEFAULT_TIMEBOX_MINUTES = 35
BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = BASE_DIR / "data"
CSV_FIELDS = [
    "trial_id",
    "participant",
    "kata",
    "treatment",
    "started_at",
    "finished_at",
    "timebox_minutes",
    "elapsed_seconds",
    "time_to_green_seconds",
    "censored",
    "timebox_reached",
    "tests_passed",
    "tests_failed",
    "success_rate",
    "notes",
]


class TrialError(ValueError):
    """Erro de validacao de um registro de trial."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise TrialError("Data invalida. Use ISO 8601, por exemplo 2026-09-09T19:00:00Z.") from error
    if parsed.tzinfo is None:
        raise TrialError("A data deve informar fuso horario, por exemplo o sufixo Z.")
    return parsed.astimezone(timezone.utc)


def validate_timebox(minutes: int) -> int:
    if not 1 <= minutes <= MAX_TIMEBOX_MINUTES:
        raise TrialError(f"O time-box deve estar entre 1 e {MAX_TIMEBOX_MINUTES} minutos.")
    return minutes


def read_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        raise TrialError("Nao existe trial ativo. Execute o comando start primeiro.")
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise TrialError(f"Arquivo de trial ativo invalido: {state_path}") from error


def write_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def start_trial(
    *,
    state_path: Path,
    participant: str,
    kata: str,
    treatment: str,
    timebox_minutes: int,
    started_at: datetime,
) -> dict[str, Any]:
    if state_path.exists():
        active = read_state(state_path)
        raise TrialError(
            "Ja existe um trial ativo para "
            f"{active.get('participant', 'participante desconhecido')} / {active.get('kata', 'kata desconhecida')}. "
            "Encerre-o antes de iniciar outro."
        )
    if not participant.strip() or not kata.strip():
        raise TrialError("Participante e kata sao obrigatorios.")

    state = {
        "trial_id": str(uuid.uuid4()),
        "participant": participant.strip(),
        "kata": kata.strip(),
        "treatment": treatment,
        "timebox_minutes": validate_timebox(timebox_minutes),
        "started_at": format_timestamp(started_at),
    }
    write_state(state_path, state)
    return state


def append_row(csv_path: Path, row: dict[str, Any]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow(row)


def finish_trial(
    *,
    state_path: Path,
    csv_path: Path,
    outcome: str,
    tests_passed: int,
    tests_failed: int,
    notes: str,
    finished_at: datetime,
) -> dict[str, Any]:
    if tests_passed < 0 or tests_failed < 0:
        raise TrialError("As quantidades de testes nao podem ser negativas.")
    if outcome == "green" and (tests_passed == 0 or tests_failed != 0):
        raise TrialError("Um trial green deve terminar com ao menos um teste aprovado e nenhum teste falhando.")

    state = read_state(state_path)
    started_at = parse_timestamp(state["started_at"])
    if finished_at < started_at:
        raise TrialError("O termino nao pode ocorrer antes do inicio do trial.")

    timebox_minutes = validate_timebox(int(state["timebox_minutes"]))
    elapsed_seconds = (finished_at - started_at).total_seconds()
    timebox_seconds = timebox_minutes * 60
    censored = outcome == "timebox"
    if censored:
        time_to_green_seconds = timebox_seconds
    else:
        time_to_green_seconds = elapsed_seconds

    total_tests = tests_passed + tests_failed
    row = {
        "trial_id": state["trial_id"],
        "participant": state["participant"],
        "kata": state["kata"],
        "treatment": state["treatment"],
        "started_at": state["started_at"],
        "finished_at": format_timestamp(finished_at),
        "timebox_minutes": timebox_minutes,
        "elapsed_seconds": f"{elapsed_seconds:.3f}",
        "time_to_green_seconds": f"{time_to_green_seconds:.3f}",
        "censored": str(censored).lower(),
        "timebox_reached": str(censored).lower(),
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "success_rate": f"{(tests_passed / total_tests) if total_tests else 0:.4f}",
        "notes": notes.strip(),
    }
    append_row(csv_path, row)
    state_path.unlink()
    return row


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Registrador de trials do Lab02")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Diretorio do CSV e estado ativo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Inicia um trial.")
    start.add_argument("--participant", required=True)
    start.add_argument("--kata", required=True)
    start.add_argument("--treatment", required=True, choices=("com_ia", "sem_ia"))
    start.add_argument("--timebox-minutes", type=int, default=DEFAULT_TIMEBOX_MINUTES)
    start.add_argument("--started-at", help="Uso para reproducao/testes: ISO 8601 com fuso horario.")

    finish = subparsers.add_parser("finish", help="Encerra o trial ativo e adiciona-o ao CSV.")
    finish.add_argument("--outcome", required=True, choices=("green", "timebox"))
    finish.add_argument("--tests-passed", required=True, type=int)
    finish.add_argument("--tests-failed", required=True, type=int)
    finish.add_argument("--notes", default="")
    finish.add_argument("--finished-at", help="Uso para reproducao/testes: ISO 8601 com fuso horario.")

    subparsers.add_parser("cancel", help="Cancela o trial ativo sem grava-lo no CSV.")

    return parser


def run(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    data_dir = args.data_dir.resolve()
    state_path = data_dir / "active_trial.json"
    csv_path = data_dir / "trials.csv"

    try:
        if args.command == "start":
            started_at = parse_timestamp(args.started_at) if args.started_at else utc_now()
            state = start_trial(
                state_path=state_path,
                participant=args.participant,
                kata=args.kata,
                treatment=args.treatment,
                timebox_minutes=args.timebox_minutes,
                started_at=started_at,
            )
            print(f"Trial iniciado: {state['trial_id']} ({state['participant']} / {state['kata']}).")
            return 0

        if args.command == "cancel":
            state = read_state(state_path)
            state_path.unlink()
            print(f"Trial cancelado sem registro no CSV: {state['trial_id']}.")
            return 0

        finished_at = parse_timestamp(args.finished_at) if args.finished_at else utc_now()
        row = finish_trial(
            state_path=state_path,
            csv_path=csv_path,
            outcome=args.outcome,
            tests_passed=args.tests_passed,
            tests_failed=args.tests_failed,
            notes=args.notes,
            finished_at=finished_at,
        )
        print(f"Trial registrado em {csv_path}: {row['trial_id']}.")
        return 0
    except TrialError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
