import pyarrow.parquet as pq

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

    state.save_completed(run_key, "org/repo", selection, row, payload)

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
