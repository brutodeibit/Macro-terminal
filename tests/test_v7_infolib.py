import unittest
from v7_infolib import normalize


class InfoLibTests(unittest.TestCase):
    def test_date_only_without_direction_inference(self):
        row = normalize(dict(date='2026-11-13 04:08 PM', symbol='AAPL', price=100, size=200, avg_paid=20000))
        self.assertEqual(row['timestamp'], '2026-11-13')
        self.assertEqual(row['timestampPrecision'], 'date')
        self.assertEqual(row['side'], 'UNKNOWN')
        self.assertIsNone(row['timezone'])

    def test_reject_inconsistent_or_nonfinite_value(self):
        for value in (50000, float('nan')):
            self.assertIsNone(normalize(dict(date='2026-11-13 04:08 PM', symbol='AAPL', price=100, size=200, avg_paid=value)))
