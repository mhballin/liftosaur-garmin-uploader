import unittest
from pathlib import Path

from liftosaur_garmin.csv_parser import group_workouts, read_csv


class TestCsvParser(unittest.TestCase):
    def test_read_csv_and_group(self) -> None:
        csv_path = Path(__file__).parent / "fixtures" / "liftosaur_2026-02-05.csv"
        rows = read_csv(csv_path)
        self.assertGreater(len(rows), 0)

        workouts = group_workouts(rows)
        self.assertEqual(len(workouts), 1)


if __name__ == "__main__":
    unittest.main()
