from pipeline.git_metadata import GitCommandResult, GitMetadataCollector


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.commands = []

    def __call__(self, command):
        self.commands.append(list(command))
        return GitCommandResult(self.outputs.pop(0), "")


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
            "base-sha\n",
            "",
            "head-sha\n",
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
