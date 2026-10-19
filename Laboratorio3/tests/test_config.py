import json
from datetime import date

import pytest

from pipeline.config import ConfigError, PipelineConfig


def write_config(tmp_path, start="2025-01-01", end="2025-12-31"):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "observation": {"start_date": start, "end_date": end},
                "collection": {"candidate_limit": 300},
                "runtime": {
                    "cache_dir": ".cache",
                    "output_dir": "output",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_loads_config_and_resolves_paths(tmp_path):
    config = PipelineConfig.from_file(write_config(tmp_path))

    assert config.start_date == date(2025, 1, 1)
    assert config.end_date == date(2025, 12, 31)
    assert config.candidate_limit == 300
    assert config.cache_dir == (tmp_path / ".cache").resolve()
    assert config.output_dir == (tmp_path / "output").resolve()


def test_command_line_values_override_file(tmp_path):
    config = PipelineConfig.from_file(
        write_config(tmp_path),
        start_date="2026-01-01",
        end_date="2026-06-30",
        candidate_limit=12,
    )

    assert config.start_date == date(2026, 1, 1)
    assert config.end_date == date(2026, 6, 30)
    assert config.candidate_limit == 12


def test_smaller_candidate_override_can_be_used_for_a_partial_run(tmp_path):
    path = write_config(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["collection"]["target_included"] = 300
    path.write_text(json.dumps(raw), encoding="utf-8")

    config = PipelineConfig.from_file(path, candidate_limit=100)

    assert config.candidate_limit == 100
    assert config.target_included == 300


def test_rejects_missing_dates(tmp_path):
    with pytest.raises(ConfigError, match="start_date"):
        PipelineConfig.from_file(write_config(tmp_path, start=None, end=None))


@pytest.mark.parametrize("limit", [0, 10001])
def test_rejects_invalid_candidate_limit(tmp_path, limit):
    with pytest.raises(ConfigError, match="candidate_limit"):
        PipelineConfig.from_file(write_config(tmp_path), candidate_limit=limit)
