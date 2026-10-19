"""Estado transacional e exportação analítica da coleta."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


STATE_SCHEMA_VERSION = 1


class CollectionState:
    """Checkpoint por repositório e staging normalizado em SQLite."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS completed_repositories (
                run_key TEXT NOT NULL,
                full_name TEXT NOT NULL,
                selection_json TEXT NOT NULL,
                repository_json TEXT,
                PRIMARY KEY (run_key, full_name)
            );
            CREATE TABLE IF NOT EXISTS normalized_records (
                run_key TEXT NOT NULL,
                table_name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                record_json TEXT NOT NULL,
                PRIMARY KEY (run_key, table_name, full_name, ordinal)
            );
            """
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CollectionState":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def load_completed(
        self, run_key: str
    ) -> dict[str, tuple[dict[str, Any], dict[str, Any] | None]]:
        rows = self._connection.execute(
            """
            SELECT full_name, selection_json, repository_json
            FROM completed_repositories
            WHERE run_key = ?
            """,
            (run_key,),
        )
        return {
            full_name: (
                json.loads(selection_json),
                json.loads(repository_json) if repository_json else None,
            )
            for full_name, selection_json, repository_json in rows
        }

    def save_completed(
        self,
        run_key: str,
        full_name: str,
        selection: Mapping[str, Any],
        repository_row: Mapping[str, Any] | None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO completed_repositories
                    (run_key, full_name, selection_json, repository_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    run_key,
                    full_name,
                    _json(selection),
                    _json(repository_row) if repository_row is not None else None,
                ),
            )
            self._connection.execute(
                "DELETE FROM normalized_records WHERE run_key = ? AND full_name = ?",
                (run_key, full_name),
            )
            if payload is not None:
                self._save_payload_records(run_key, full_name, payload)

    def records(self, run_key: str, table_name: str) -> Iterable[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT record_json
            FROM normalized_records
            WHERE run_key = ? AND table_name = ?
            ORDER BY full_name, ordinal
            """,
            (run_key, table_name),
        )
        for (record_json,) in rows:
            yield json.loads(record_json)

    def _save_payload_records(
        self,
        run_key: str,
        full_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        tables: dict[str, list[dict[str, Any]]] = {
            "repository_metadata": [dict(payload.get("repository") or {})],
            "workflows": [dict(item) for item in payload.get("workflows") or []],
            "releases": [dict(item) for item in payload.get("releases") or []],
            "tags": [dict(item) for item in payload.get("tags") or []],
            "workflow_runs": [
                dict(item) for item in payload.get("workflow_runs") or []
            ],
            "release_comparisons": [],
            "release_commits": [],
        }
        for comparison in payload.get("comparisons") or []:
            comparison_row = {
                key: comparison.get(key)
                for key in (
                    "base_tag",
                    "head_tag",
                    "release_published_at",
                    "error",
                    "error_status",
                )
            }
            tables["release_comparisons"].append(comparison_row)
            for commit in comparison.get("commits") or []:
                tables["release_commits"].append(
                    {
                        "base_tag": comparison.get("base_tag"),
                        "head_tag": comparison.get("head_tag"),
                        "release_published_at": comparison.get(
                            "release_published_at"
                        ),
                        **dict(commit),
                    }
                )

        for table_name, records in tables.items():
            for ordinal, record in enumerate(records):
                record.setdefault("full_name", full_name)
                self._connection.execute(
                    """
                    INSERT INTO normalized_records
                        (run_key, table_name, full_name, ordinal, record_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_key, table_name, full_name, ordinal, _json(record)),
                )


def collection_run_key(values: Mapping[str, Any]) -> str:
    payload = {"schema_version": STATE_SCHEMA_VERSION, **dict(values)}
    encoded = _json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def export_parquet(
    output_dir: str | Path,
    state: CollectionState,
    run_key: str,
    *,
    selection_rows: list[dict[str, Any]],
    repository_rows: list[dict[str, Any]],
) -> list[Path]:
    """Exporta tabelas normalizadas; o CSV acadêmico permanece inalterado."""

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - validado na instalação
        raise RuntimeError(
            "A exportacao Parquet requer a dependencia pyarrow."
        ) from exc

    target = Path(output_dir) / "parquet"
    target.mkdir(parents=True, exist_ok=True)
    tables: dict[str, list[dict[str, Any]]] = {
        "selection_funnel": selection_rows,
        "repositories": repository_rows,
    }
    for name in (
        "repository_metadata",
        "workflows",
        "releases",
        "tags",
        "release_comparisons",
        "release_commits",
    ):
        tables[name] = list(state.records(run_key, name))

    written: list[Path] = []
    for name, records in tables.items():
        path = target / f"{name}.parquet"
        if not records:
            path.unlink(missing_ok=True)
            continue
        temporary = path.with_suffix(".parquet.tmp")
        table = pa.Table.from_pylist(records)
        pq.write_table(table, temporary, compression="zstd")
        temporary.replace(path)
        written.append(path)

    workflow_path = target / "workflow_runs.parquet"
    workflow_schema = pa.schema(
        [
            ("id", pa.int64()),
            ("workflow_id", pa.int64()),
            ("event", pa.string()),
            ("head_branch", pa.string()),
            ("conclusion", pa.string()),
            ("status", pa.string()),
            ("created_at", pa.string()),
            ("run_started_at", pa.string()),
            ("updated_at", pa.string()),
            ("html_url", pa.string()),
            ("full_name", pa.string()),
        ]
    )
    workflow_records = state.records(run_key, "workflow_runs")
    workflow_temporary = workflow_path.with_suffix(".parquet.tmp")
    writer = None
    try:
        while batch := list(_take(workflow_records, 10_000)):
            table = pa.Table.from_pylist(batch, schema=workflow_schema)
            if writer is None:
                writer = pq.ParquetWriter(
                    workflow_temporary, workflow_schema, compression="zstd"
                )
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    if writer is not None:
        workflow_temporary.replace(workflow_path)
        written.append(workflow_path)
    else:
        workflow_path.unlink(missing_ok=True)
        workflow_temporary.unlink(missing_ok=True)
    return written


def _take(records: Iterator[dict[str, Any]], count: int) -> Iterable[dict[str, Any]]:
    for _ in range(count):
        try:
            yield next(records)
        except StopIteration:
            return


def _json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
