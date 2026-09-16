#!/usr/bin/env python3
"""Servidor web local para execucao e leitura dos dados do Lab02."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
TRIAL_SCRIPT = BASE_DIR / "scripts" / "trial_recorder.py"
METRICS_SCRIPT = BASE_DIR / "scripts" / "static_metrics.py"
DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = BASE_DIR / "trial-workspaces"

KATAS = {
    "kata_01": {
        "title": "Agenda de calibracao",
        "function": "agrupar_calibracoes",
        "source": "calibration_schedule.py",
        "owner": "flavio",
    },
    "kata_02": {
        "title": "Correio pneumatico",
        "function": "planejar_despachos",
        "source": "pneumatic_dispatch.py",
        "owner": "flavio",
    },
    "kata_03": {
        "title": "Emprestimos de ferramentas",
        "function": "resumir_emprestimos",
        "source": "tool_loans.py",
        "owner": "luidi",
    },
    "kata_04": {
        "title": "Ciclos de rega",
        "function": "detectar_ciclos_rega",
        "source": "irrigation_cycles.py",
        "owner": "luidi",
    },
}

class ApiError(ValueError):
    """Erro esperado e seguro para exibir na interface."""


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def required_choice(payload: dict[str, Any], field: str, choices: set[str]) -> str:
    value = str(payload.get(field, "")).strip()
    if value not in choices:
        raise ApiError(f"Valor invalido para {field}.")
    return value


def workspace_for(participant: str, kata: str, treatment: str) -> Path:
    return WORKSPACE_DIR / f"{participant}-{kata}-{treatment}"


def prepare_workspace(participant: str, kata: str, treatment: str) -> tuple[Path, bool]:
    info = KATAS[kata]
    workspace = workspace_for(participant, kata, treatment)
    target = workspace / info["source"]
    if target.is_file():
        return workspace, False

    starter = BASE_DIR / "katas" / kata / "starter" / info["source"]
    if not starter.is_file():
        raise ApiError("Starter da kata nao encontrado.")
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copy2(starter, target)
    return workspace, True


def run_checked(command: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
    if completed.returncode != 0:
        raise ApiError(output or "O comando nao foi concluido.")
    return output


def trial_exists(participant: str, kata: str, treatment: str) -> bool:
    return any(
        row.get("participant") == participant
        and row.get("kata") == kata
        and row.get("treatment") == treatment
        for row in read_csv(DATA_DIR / "trials.csv")
    )


def metrics_exist(participant: str, kata: str, treatment: str) -> bool:
    return any(
        row.get("participant") == participant
        and row.get("kata") == kata
        and row.get("treatment") == treatment
        for row in read_csv(DATA_DIR / "static_metrics.csv")
    )


def parse_test_counts(output: str) -> tuple[int, int]:
    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)
    return (
        int(passed_match.group(1)) if passed_match else 0,
        int(failed_match.group(1)) if failed_match else 0,
    )


def dataset_payload() -> dict[str, Any]:
    return {
        "trials": read_csv(DATA_DIR / "trials.csv"),
        "metrics": read_csv(DATA_DIR / "static_metrics.csv"),
        "active": read_json(DATA_DIR / "active_trial.json"),
        "katas": KATAS,
        "simulation": True,
    }


class Lab02Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/data":
            self.send_json(dataset_payload())
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self.read_body()
            participant = required_choice(payload, "participant", {"flavio", "luidi"})
            kata = required_choice(payload, "kata", set(KATAS))
            treatment = required_choice(payload, "treatment", {"com_ia", "sem_ia"})

            if path == "/api/workspace":
                workspace, created = prepare_workspace(participant, kata, treatment)
                message = "Workspace preparado." if created else "Workspace ja existente."
                self.send_json({"message": message, "workspace": str(workspace)})
                return

            if path == "/api/trials/start":
                if trial_exists(participant, kata, treatment):
                    raise ApiError("Este trial ja foi registrado.")
                workspace, _created = prepare_workspace(participant, kata, treatment)
                output = run_checked(
                    [
                        sys.executable,
                        str(TRIAL_SCRIPT),
                        "--data-dir",
                        str(DATA_DIR),
                        "start",
                        "--participant",
                        participant,
                        "--kata",
                        kata,
                        "--treatment",
                        treatment,
                    ]
                )
                self.send_json({"message": output, "workspace": str(workspace)}, HTTPStatus.CREATED)
                return

            if path == "/api/tests":
                workspace = workspace_for(participant, kata, treatment)
                if not workspace.is_dir():
                    raise ApiError("Prepare o workspace antes de executar os testes.")
                env = os.environ.copy()
                env["KATA_SOLUTION_DIR"] = str(workspace)
                completed = subprocess.run(
                    [sys.executable, "-m", "pytest", str(BASE_DIR / "katas" / kata / "tests"), "-q"],
                    cwd=BASE_DIR,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                output = "\n".join(
                    part for part in (completed.stdout.strip(), completed.stderr.strip()) if part
                )
                passed, failed = parse_test_counts(output)
                self.send_json(
                    {
                        "message": "Testes concluidos.",
                        "output": output,
                        "passed": passed,
                        "failed": failed,
                        "green": completed.returncode == 0,
                    }
                )
                return

            if path == "/api/trials/finish":
                outcome = required_choice(payload, "outcome", {"green", "timebox"})
                try:
                    tests_passed = int(payload.get("tests_passed", 0))
                    tests_failed = int(payload.get("tests_failed", 0))
                except (TypeError, ValueError) as error:
                    raise ApiError("As quantidades de testes devem ser inteiras.") from error
                notes = str(payload.get("notes", "")).strip()
                output = run_checked(
                    [
                        sys.executable,
                        str(TRIAL_SCRIPT),
                        "--data-dir",
                        str(DATA_DIR),
                        "finish",
                        "--outcome",
                        outcome,
                        "--tests-passed",
                        str(tests_passed),
                        "--tests-failed",
                        str(tests_failed),
                        "--notes",
                        notes,
                    ]
                )
                self.send_json({"message": output})
                return

            if path == "/api/trials/cancel":
                output = run_checked(
                    [
                        sys.executable,
                        str(TRIAL_SCRIPT),
                        "--data-dir",
                        str(DATA_DIR),
                        "cancel",
                    ]
                )
                self.send_json({"message": output})
                return

            if path == "/api/metrics":
                if metrics_exist(participant, kata, treatment):
                    raise ApiError("As metricas deste trial ja foram registradas.")
                workspace = workspace_for(participant, kata, treatment)
                output_path = DATA_DIR / "static_metrics.csv"
                output = run_checked(
                    [
                        sys.executable,
                        str(METRICS_SCRIPT),
                        str(workspace),
                        "--participant",
                        participant,
                        "--kata",
                        kata,
                        "--treatment",
                        treatment,
                        "--output",
                        str(output_path),
                    ]
                )
                self.send_json({"message": output})
                return

            self.send_error(HTTPStatus.NOT_FOUND)
        except ApiError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ApiError("Corpo da requisicao invalido.") from error

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Interface web local do Lab02")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Lab02Handler)
    print(f"Lab02 web disponivel em: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
