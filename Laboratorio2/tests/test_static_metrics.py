import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import static_metrics  # noqa: E402


class StaticMetricsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_python_files_excludes_tests_hidden_and_cache(self):
        (self.root / "solution.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_solution.py").write_text("", encoding="utf-8")
        (self.root / ".private").mkdir()
        (self.root / ".private" / "secret.py").write_text("", encoding="utf-8")

        self.assertEqual(static_metrics.python_files(self.root), [self.root / "solution.py"])

    def test_complexity_values_uses_functions_and_nested_methods_not_classes(self):
        blocks = [
            {
                "type": "function",
                "complexity": 3,
                "closures": [{"type": "function", "complexity": 1}],
            },
            {
                "type": "C",
                "complexity": 9,
                "methods": [{"type": "M", "complexity": 2}],
            },
        ]
        self.assertEqual(static_metrics.complexity_values(blocks), [3.0, 1.0, 2.0])

    def test_duplication_from_current_jscpd_report(self):
        report = {"statistics": {"total": {"lines": {"percentage": 12.5}}}}
        self.assertEqual(static_metrics.duplication_from_report(report), 12.5)

    def test_duplication_metric_uses_portable_relative_path(self):
        solution = self.root / "trial-workspaces" / "solution"
        solution.mkdir(parents=True)
        (solution / "answer.py").write_text("x = 1\n", encoding="utf-8")

        def fake_run(command, **kwargs):
            self.assertEqual(command[-1], "trial-workspaces/solution")
            self.assertEqual(kwargs["cwd"], self.root)
            report_name = command[command.index("--output") + 1]
            report_path = self.root / report_name / "jscpd-report.json"
            report_path.write_text(
                '{"statistics":{"total":{"percentage":3.25}}}', encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            patch.object(static_metrics, "BASE_DIR", self.root),
            patch.object(static_metrics, "jscpd_command", return_value=["jscpd"]),
            patch.object(static_metrics.subprocess, "run", side_effect=fake_run),
        ):
            self.assertEqual(static_metrics.duplication_metric(solution), 3.25)

    def test_collect_metrics_appends_csv_with_header_only_once(self):
        (self.root / "solution.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        output = self.root / "data" / "static_metrics.csv"

        with (
            patch.object(static_metrics, "radon_metrics", return_value=(2, 1.5, 88.25)),
            patch.object(static_metrics, "duplication_metric", return_value=4.75),
        ):
            first = static_metrics.collect_metrics(
                solution_dir=self.root,
                participant=" luidi ",
                kata="kata_01",
                treatment="com_ia",
                output=output,
            )
            static_metrics.collect_metrics(
                solution_dir=self.root,
                participant="flavio",
                kata="kata_02",
                treatment="sem_ia",
                output=output,
            )

        self.assertEqual(first["avg_cyclomatic_complexity"], "1.500")
        with output.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["participant"], "luidi")
        self.assertEqual(rows[0]["duplication_percentage"], "4.750")

    def test_collect_metrics_rejects_directory_without_python_solution(self):
        with self.assertRaisesRegex(static_metrics.MetricsError, "Nenhum arquivo Python"):
            static_metrics.collect_metrics(
                solution_dir=self.root,
                participant="luidi",
                kata="kata_01",
                treatment="com_ia",
                output=self.root / "metrics.csv",
            )

    def test_run_reports_missing_radon_without_writing_csv(self):
        (self.root / "solution.py").write_text("x = 1\n", encoding="utf-8")
        output = self.root / "metrics.csv"
        with patch.object(
            static_metrics,
            "radon_metrics",
            side_effect=static_metrics.MetricsError(
                "Radon não encontrado. Execute: python3 -m pip install -r requirements.txt"
            ),
        ):
            exit_code = static_metrics.run(
                [
                    str(self.root),
                    "--participant",
                    "luidi",
                    "--kata",
                    "kata_01",
                    "--treatment",
                    "sem_ia",
                    "--output",
                    str(output),
                ]
            )
        self.assertEqual(exit_code, 2)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
