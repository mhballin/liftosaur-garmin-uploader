import unittest

from liftosaur_garmin.csv_parser import parse_csv_rows


class TestCsvParser(unittest.TestCase):
    def test_parse_csv_rows_returns_list(self) -> None:
        rows = [{"exercise": "Bench Press", "reps": "5"}]
        parsed = parse_csv_rows(rows)
        self.assertEqual(parsed, rows)


if __name__ == "__main__":
    unittest.main()
