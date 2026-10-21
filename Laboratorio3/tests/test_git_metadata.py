import hashlib

from pipeline.git_metadata import (
    GitCollectionError,
    GitCommandResult,
    GitMetadataCollector,
)


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.commands = []

    def __call__(self, command):
        self.commands.append(list(command))
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return GitCommandResult(output, "")


def test_lists_lightweight_and_annotated_tags_without_clone(tmp_path):
    runner = FakeRunner(
        [
            (
                "aaa\trefs/tags/v1.0.0\n"
                "bbb\trefs/tags/v2.0.0\n"
                "ccc\trefs/tags/v2.0.0^{}\n"
            )
        ]
    )
    collector = GitMetadataCollector(tmp_path, runner=runner)

    assert collector.collect_tags("org/project") == [
        {"name": "v1.0.0", "commit": {"sha": "aaa"}},
        {"name": "v2.0.0", "commit": {"sha": "ccc"}},
    ]
    assert runner.commands == [
        ["git", "ls-remote", "--tags", "https://github.com/org/project.git"]
    ]


def test_fetches_only_release_tags_and_parses_commit_metadata(tmp_path):
    runner = FakeRunner(
        [
            "",
            "",
            "",
            "",
            "",
            (
                "abc\x002025-02-01T00:00:00+00:00\x00feat: one\x00\x1e"
                "def\x002025-02-02T00:00:00+00:00\x00fix: two\nbody\x00\x1e"
            ),
        ]
    )
    collector = GitMetadataCollector(tmp_path, runner=runner)

    commits = collector.commits_between("org/project", "v1", "v2")

    assert commits == [
        {
            "sha": "abc",
            "author_date": "2025-02-01T00:00:00+00:00",
            "message": "feat: one",
        },
        {
            "sha": "def",
            "author_date": "2025-02-02T00:00:00+00:00",
            "message": "fix: two\nbody",
        },
    ]
    fetches = [command for command in runner.commands if "fetch" in command]
    assert len(fetches) == 2
    assert all("--filter=blob:none" in command for command in fetches)
    assert all("--no-tags" in command for command in fetches)
    assert all("--no-write-fetch-head" in command for command in fetches)


def test_prepare_tags_reuses_existing_refs_and_fetches_missing_in_one_batch(tmp_path):
    existing_ref = _local_ref("v1")
    runner = FakeRunner(
        [
            "",
            "",
            f"{existing_ref}\n",
            "",
            "abc\x002025-02-01T00:00:00+00:00\x00feat: one\x00\x1e",
        ]
    )
    collector = GitMetadataCollector(tmp_path, runner=runner)

    collector.prepare_tags("org/project", ["v1", "v2", "v2"])
    commits = collector.commits_between("org/project", "v1", "v2")

    fetches = [command for command in runner.commands if "fetch" in command]
    assert len(fetches) == 1
    assert not any("refs/tags/v1:" in argument for argument in fetches[0])
    assert any("refs/tags/v2:" in argument for argument in fetches[0])
    assert commits[0]["sha"] == "abc"


def test_prepare_tags_splits_large_sets_into_bounded_batches(tmp_path):
    runner = FakeRunner(["", "", "", "", ""])
    collector = GitMetadataCollector(tmp_path, runner=runner)

    collector.prepare_tags("org/project", [f"v{number}" for number in range(51)])

    fetches = [command for command in runner.commands if "fetch" in command]
    assert len(fetches) == 2
    assert sum(argument.startswith("refs/tags/") for argument in fetches[0]) == 50
    assert sum(argument.startswith("refs/tags/") for argument in fetches[1]) == 1


def test_prepare_tags_isolates_a_failed_batch(tmp_path):
    runner = FakeRunner(
        [
            "",
            "",
            "",
            GitCollectionError("uma tag invalida"),
            "",
            "",
            "",
        ]
    )
    collector = GitMetadataCollector(tmp_path, runner=runner)

    collector.prepare_tags("org/project", ["v1", "v2"])

    fetches = [command for command in runner.commands if "fetch" in command]
    assert len(fetches) == 3


def _local_ref(tag_name):
    digest = hashlib.sha256(tag_name.encode("utf-8")).hexdigest()
    return f"refs/lab03/{digest}"
