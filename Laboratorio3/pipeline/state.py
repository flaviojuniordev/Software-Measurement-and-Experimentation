"""Estado transacional e exportação analítica da coleta."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping


STATE_SCHEMA_VERSION = 1


class CollectionState:
    """Checkpoint leve por repositório; payloads permanecem em ``data/raw``."""

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
            """
        )
        self._remove_legacy_normalized_records()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CollectionState":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _remove_legacy_normalized_records(self) -> None:
        legacy = self._connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'normalized_records'
            """
        ).fetchone()
        if legacy is None:
            return
        self._connection.execute("DROP TABLE normalized_records")
        self._connection.commit()
        self._connection.execute("VACUUM")

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
    """Exporta Parquet em lotes a partir dos JSONs brutos, sem duplicar no SQLite."""

    del state, run_key

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - validado na instalação
        raise RuntimeError(
            "A exportacao Parquet requer a dependencia pyarrow."
        ) from exc

    target = Path(output_dir) / "parquet"
    target.mkdir(parents=True, exist_ok=True)
    summary_tables: dict[str, list[dict[str, Any]]] = {
        "selection_funnel": selection_rows,
        "repositories": repository_rows,
    }
    written: list[Path] = []
    for name, records in summary_tables.items():
        path = target / f"{name}.parquet"
        if not records:
            path.unlink(missing_ok=True)
            continue
        temporary = path.with_suffix(".parquet.tmp")
        table = pa.Table.from_pylist(records)
        pq.write_table(table, temporary, compression="zstd")
        temporary.replace(path)
        written.append(path)

    schemas = {
        "repository_metadata": pa.schema(
            [
                ("id", pa.int64()),
                ("full_name", pa.string()),
                ("html_url", pa.string()),
                ("stargazers_count", pa.int64()),
                ("language", pa.string()),
                ("created_at", pa.string()),
                ("updated_at", pa.string()),
                ("default_branch", pa.string()),
                ("archived", pa.bool_()),
                ("fork", pa.bool_()),
            ]
        ),
        "workflows": pa.schema(
            [
                ("id", pa.int64()),
                ("name", pa.string()),
                ("path", pa.string()),
                ("state", pa.string()),
                ("html_url", pa.string()),
                ("full_name", pa.string()),
            ]
        ),
        "releases": pa.schema(
            [
                ("tag_name", pa.string()),
                ("published_at", pa.string()),
                ("draft", pa.bool_()),
                ("prerelease", pa.bool_()),
                ("body", pa.string()),
                ("html_url", pa.string()),
                ("full_name", pa.string()),
            ]
        ),
        "tags": pa.schema(
            [
                ("name", pa.string()),
                ("commit_sha", pa.string()),
                ("full_name", pa.string()),
            ]
        ),
        "workflow_runs": pa.schema(
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
        ),
        "release_comparisons": pa.schema(
            [
                ("base_tag", pa.string()),
                ("head_tag", pa.string()),
                ("release_published_at", pa.string()),
                ("error", pa.string()),
                ("error_status", pa.int64()),
                ("full_name", pa.string()),
            ]
        ),
        "release_commits": pa.schema(
            [
                ("base_tag", pa.string()),
                ("head_tag", pa.string()),
                ("release_published_at", pa.string()),
                ("sha", pa.string()),
                ("author_date", pa.string()),
                ("message", pa.string()),
                ("full_name", pa.string()),
            ]
        ),
    }
    buffers: dict[str, list[dict[str, Any]]] = {name: [] for name in schemas}
    writers: dict[str, Any] = {}
    temporaries = {
        name: (target / f"{name}.parquet").with_suffix(".parquet.tmp")
        for name in schemas
    }

    def flush(name: str) -> None:
        records = buffers[name]
        if not records:
            return
        table = pa.Table.from_pylist(records, schema=schemas[name])
        writer = writers.get(name)
        if writer is None:
            writer = pq.ParquetWriter(
                temporaries[name], schemas[name], compression="zstd"
            )
            writers[name] = writer
        writer.write_table(table)
        records.clear()

    def append(name: str, record: dict[str, Any]) -> None:
        buffers[name].append(record)
        if len(buffers[name]) >= 10_000:
            flush(name)

    raw_dir = Path(output_dir) / "raw"
    try:
        for repository_row in repository_rows:
            full_name = str(repository_row["full_name"])
            raw_path = raw_dir / f"{full_name.replace('/', '__')}.json"
            try:
                payload = json.loads(raw_path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"Payload bruto ausente para exportar Parquet: {full_name}"
                ) from exc
            repository = dict(payload.get("repository") or {})
            repository["full_name"] = full_name
            append("repository_metadata", repository)
            for workflow in payload.get("workflows") or []:
                append("workflows", {**dict(workflow), "full_name": full_name})
            for release in payload.get("releases") or []:
                append("releases", {**dict(release), "full_name": full_name})
            for tag in payload.get("tags") or []:
                commit = tag.get("commit") or {}
                append(
                    "tags",
                    {
                        "name": tag.get("name"),
                        "commit_sha": commit.get("sha"),
                        "full_name": full_name,
                    },
                )
            for run in payload.get("workflow_runs") or []:
                append("workflow_runs", {**dict(run), "full_name": full_name})
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
                append(
                    "release_comparisons",
                    {**comparison_row, "full_name": full_name},
                )
                for commit in comparison.get("commits") or []:
                    append(
                        "release_commits",
                        {
                            "base_tag": comparison.get("base_tag"),
                            "head_tag": comparison.get("head_tag"),
                            "release_published_at": comparison.get(
                                "release_published_at"
                            ),
                            **dict(commit),
                            "full_name": full_name,
                        },
                    )
        for name in schemas:
            flush(name)
    finally:
        for writer in writers.values():
            writer.close()

    for name in schemas:
        path = target / f"{name}.parquet"
        temporary = temporaries[name]
        if name in writers:
            temporary.replace(path)
            written.append(path)
        else:
            path.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)
    return written


def _json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
