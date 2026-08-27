#!/usr/bin/env python3
"""Servidor web local da interface do Lab01."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DEFAULT_CSV = BASE_DIR / "output" / "coleta_1000.csv"
SPRINT3_DIR = BASE_DIR / "output" / "sprint3"
SPRINT3_RESULTS = SPRINT3_DIR / "sprint3_results.json"
SPRINT3_LUIDI_RESULTS = SPRINT3_DIR / "luidi_results.json"
QUERY_SCRIPT = BASE_DIR / "query.py"
ANALYSIS_SCRIPT = BASE_DIR / "analyze_lab01_s03_luidi.py"
SNAPSHOT_SCRIPT = BASE_DIR / "project_snapshot.py"

jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()


def read_csv_rows() -> list[dict[str, str]]:
    import csv

    if not DEFAULT_CSV.is_file():
        return []
    with DEFAULT_CSV.open("r", encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def start_job(name: str, command: list[str]) -> None:
    with jobs_lock:
        active = jobs.get(name)
        if active and active["running"]:
            raise RuntimeError("Ja existe um processo em andamento.")
        jobs[name] = {"running": True, "return_code": None, "lines": ["$ " + " ".join(command)]}

    def worker() -> None:
        process = subprocess.Popen(
            command,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy(),
        )
        assert process.stdout is not None
        for line in process.stdout:
            with jobs_lock:
                jobs[name]["lines"].append(line.rstrip())
                jobs[name]["lines"] = jobs[name]["lines"][-200:]
        with jobs_lock:
            jobs[name]["return_code"] = process.wait()
            jobs[name]["running"] = False

    threading.Thread(target=worker, daemon=True).start()


class Lab01Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/data":
            self.send_json({"rows": read_csv_rows(), "analysis": read_json(SPRINT3_RESULTS)})
            return
        if path == "/api/status":
            with jobs_lock:
                active_jobs = {name: data.copy() for name, data in jobs.items()}
            self.send_json(
                {
                    "csv_exists": DEFAULT_CSV.is_file(),
                    "analysis_exists": SPRINT3_RESULTS.is_file(),
                    "jobs": active_jobs,
                }
            )
            return
        if path.startswith("/api/chart/"):
            filename = path.removeprefix("/api/chart/")
            allowed = {
                "rq01_idade.png",
                "rq02_prs_aceitas.png",
                "rq03_releases.png",
                "rq04_atualizacao.png",
                "rq05_linguagens.png",
                "rq06_issues_fechadas.png",
                "rq07_comparacao_linguagens.png",
            }
            if filename not in allowed:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            chart = SPRINT3_DIR / filename
            if not chart.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(chart.stat().st_size))
            self.end_headers()
            self.wfile.write(chart.read_bytes())
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self.read_body()
        try:
            if path == "/api/collect":
                start_job("coleta", [sys.executable, str(QUERY_SCRIPT), "--limit", "1000"])
                self.send_json({"message": "Coleta iniciada."}, HTTPStatus.ACCEPTED)
                return
            if path == "/api/analyze":
                if not DEFAULT_CSV.is_file():
                    raise ValueError("Gere ou carregue o CSV de 1.000 repositorios antes da analise.")
                start_job(
                    "analise",
                    [
                        sys.executable,
                        str(ANALYSIS_SCRIPT),
                        "--csv",
                        str(DEFAULT_CSV),
                        "--output-dir",
                        str(SPRINT3_DIR),
                    ],
                )
                self.send_json({"message": "Analise S03 iniciada."}, HTTPStatus.ACCEPTED)
                return
            if path == "/api/clear":
                with jobs_lock:
                    if any(job["running"] for job in jobs.values()):
                        raise ValueError("Aguarde o processo atual terminar antes de limpar os dados.")
                removed: list[str] = []
                for file_path in (
                    DEFAULT_CSV,
                    SPRINT3_RESULTS,
                    SPRINT3_LUIDI_RESULTS,
                    *SPRINT3_DIR.glob("*.png"),
                ):
                    if file_path.is_file():
                        file_path.unlink()
                        removed.append(file_path.name)
                self.send_json({"message": "Dados locais removidos.", "removed": removed})
                return
            if path == "/api/snapshot":
                owner = str(body.get("owner", "")).strip()
                number = str(body.get("project_number", "")).strip()
                owner_type = str(body.get("owner_type", "user")).strip()
                if not owner or not number:
                    raise ValueError("Informe owner e numero do GitHub Project.")
                output = BASE_DIR / "snapshots" / "lab01s03_project_snapshot.csv"
                start_job(
                    "snapshot",
                    [
                        sys.executable,
                        str(SNAPSHOT_SCRIPT),
                        "--owner",
                        owner,
                        "--owner-type",
                        owner_type,
                        "--project-number",
                        number,
                        "--output",
                        str(output),
                    ],
                )
                self.send_json({"message": "Snapshot iniciado.", "output": str(output)}, HTTPStatus.ACCEPTED)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except (RuntimeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def read_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(content_length).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Corpo da requisicao invalido.") from exc

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Interface web local do Lab01")
    parser.add_argument("--port", type=int, default=8000, help="Porta local do servidor")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Lab01Handler)
    print(f"Lab01 web disponivel em: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
