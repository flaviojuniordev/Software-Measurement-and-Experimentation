import pyarrow.parquet as pq
import sqlite3

from pipeline.output import save_repository_payload
from pipeline.state import CollectionState, collection_run_key, export_parquet


def test_state_restores_repository_and_exports_normalized_parquet(tmp_path):
    state = CollectionState(tmp_path / "state.sqlite3")
    run_key = collection_run_key({"window": "2025"})
    selection = {"full_name": "org/repo", "s01_included": True}
    row = {"full_name": "org/repo", "ci_change_failure_rate": 0.2}
    payload = {
        "repository": {"full_name": "org/repo", "stars": 1000},
        "workflows": [{"id": 1, "name": "CI"}],
        "releases": [{"tag_name": "v1", "published_at": "2025-01-01T00:00:00Z"}],
        "tags": [{"name": "v1", "commit": {"sha": "abc"}}],
        "workflow_runs": [{"id": 10, "conclusion": "success"}],
        "comparisons": [
            {
                "base_tag": "v0",
                "head_tag": "v1",
                "release_published_at": "2025-01-01T00:00:00Z",
                "error": None,
                "commits": [
                    {
                        "sha": "abc",
                        "author_date": "2024-12-31T00:00:00Z",
                        "message": "feat",
                    }
                ],
            }
        ],
    }

    save_repository_payload(tmp_path, "org/repo", payload)
    state.save_completed(run_key, "org/repo", selection, row)

    assert state.load_completed(run_key)["org/repo"] == (selection, row)
    paths = export_parquet(
        tmp_path,
        state,
        run_key,
        selection_rows=[selection],
        repository_rows=[row],
    )
    assert paths
    commits = pq.read_table(tmp_path / "parquet" / "release_commits.parquet")
    assert commits.to_pylist()[0]["sha"] == "abc"
    state.close()


def test_state_migrates_legacy_normalized_table_without_losing_checkpoint(tmp_path):
    path = tmp_path / "state.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE completed_repositories (
            run_key TEXT NOT NULL,
            full_name TEXT NOT NULL,
            selection_json TEXT NOT NULL,
            repository_json TEXT,
            PRIMARY KEY (run_key, full_name)
        );
        CREATE TABLE normalized_records (
            run_key TEXT, table_name TEXT, full_name TEXT,
            ordinal INTEGER, record_json TEXT
        );
        INSERT INTO completed_repositories VALUES
            ('run', 'org/repo', '{"full_name":"org/repo"}', NULL);
        INSERT INTO normalized_records VALUES
            ('run', 'workflow_runs', 'org/repo', 0, '{"id":1}');
        """
    )
    connection.close()

    state = CollectionState(path)

    assert state.load_completed("run")["org/repo"][0]["full_name"] == "org/repo"
    tables = state._connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    assert ("normalized_records",) not in tables
    state.close()
