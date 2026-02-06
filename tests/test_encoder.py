import unittest

from liftosaur_garmin.fit.encoder import FitEncoder


class TestFitEncoder(unittest.TestCase):
    def test_encoder_placeholder(self) -> None:
        encoder = FitEncoder()
        with self.assertRaises(NotImplementedError):
            encoder.encode_workout([])


if __name__ == "__main__":
    unittest.main()
