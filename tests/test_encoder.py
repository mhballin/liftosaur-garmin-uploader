import unittest
from pathlib import Path

from liftosaur_garmin.csv_parser import group_workouts, read_csv
from liftosaur_garmin.workout_builder import build_fit_for_workout


class TestFitEncoder(unittest.TestCase):
    def test_build_fit_payload(self) -> None:
        csv_path = Path(__file__).parent / "fixtures" / "liftosaur_2026-02-05.csv"
        rows = read_csv(csv_path)
        workouts = group_workouts(rows)
        workout_sets = next(iter(workouts.values()))

        payload = build_fit_for_workout(workout_sets)
        self.assertGreater(len(payload), 0)
        self.assertIn(b".FIT", payload[:20])


if __name__ == "__main__":
    unittest.main()
