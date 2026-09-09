import csv
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import trial_recorder  # noqa: E402


UTC = timezone.utc


class TrialRecorderTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.state_path = self.data_dir / "active_trial.json"
        self.csv_path = self.data_dir / "trials.csv"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_green_trial_records_elapsed_time_and_success_rate(self):
        trial_recorder.start_trial(
            state_path=self.state_path,
            participant="flavio",
            kata="kata-01",
            treatment="com_ia",
            timebox_minutes=35,
            started_at=datetime(2026, 9, 9, 19, 0, tzinfo=UTC),
        )

        row = trial_recorder.finish_trial(
            state_path=self.state_path,
            csv_path=self.csv_path,
            outcome="green",
            tests_passed=8,
            tests_failed=0,
            notes="",
            finished_at=datetime(2026, 9, 9, 19, 12, 30, tzinfo=UTC),
        )

        self.assertEqual(row["time_to_green_seconds"], "750.000")
        self.assertEqual(row["censored"], "false")
        self.assertEqual(row["success_rate"], "1.0000")
        self.assertFalse(self.state_path.exists())
        with self.csv_path.open(newline="", encoding="utf-8") as output:
            rows = list(csv.DictReader(output))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["treatment"], "com_ia")

    def test_timebox_trial_is_censored_at_the_configured_limit(self):
        trial_recorder.start_trial(
            state_path=self.state_path,
            participant="luidi",
            kata="kata-02",
            treatment="sem_ia",
            timebox_minutes=35,
            started_at=datetime(2026, 9, 9, 19, 0, tzinfo=UTC),
        )

        row = trial_recorder.finish_trial(
            state_path=self.state_path,
            csv_path=self.csv_path,
            outcome="timebox",
            tests_passed=5,
            tests_failed=3,
            notes="tempo encerrado",
            finished_at=datetime(2026, 9, 9, 19, 35, tzinfo=UTC),
        )

        self.assertEqual(row["time_to_green_seconds"], "2100.000")
        self.assertEqual(row["censored"], "true")
        self.assertEqual(row["timebox_reached"], "true")
        self.assertEqual(row["success_rate"], "0.6250")

    def test_cannot_start_a_second_trial_while_one_is_active(self):
        trial_recorder.start_trial(
            state_path=self.state_path,
            participant="flavio",
            kata="kata-01",
            treatment="com_ia",
            timebox_minutes=35,
            started_at=datetime(2026, 9, 9, 19, 0, tzinfo=UTC),
        )

        with self.assertRaises(trial_recorder.TrialError):
            trial_recorder.start_trial(
                state_path=self.state_path,
                participant="luidi",
                kata="kata-02",
                treatment="sem_ia",
                timebox_minutes=35,
                started_at=datetime(2026, 9, 9, 19, 1, tzinfo=UTC),
            )

    def test_cancel_removes_the_active_trial_without_creating_csv(self):
        exit_code = trial_recorder.run(
            [
                "--data-dir",
                str(self.data_dir),
                "start",
                "--participant",
                "flavio",
                "--kata",
                "kata-01",
                "--treatment",
                "com_ia",
                "--started-at",
                "2026-09-09T19:00:00Z",
            ]
        )
        self.assertEqual(exit_code, 0)

        exit_code = trial_recorder.run(["--data-dir", str(self.data_dir), "cancel"])

        self.assertEqual(exit_code, 0)
        self.assertFalse(self.state_path.exists())
        self.assertFalse(self.csv_path.exists())


if __name__ == "__main__":
    unittest.main()
