import unittest
from v7_infolib import normalize, update
from unittest.mock import patch, Mock


class InfoLibTests(unittest.TestCase):
    def test_visible_rows_update_counts_and_source_status_idempotently(self):
        rows = [dict(date='2026-11-13 04:08 PM', symbol='AAPL', price=100, size=200, avg_paid=20000)]
        feed = {'darkPoolPrints': {'assets': {'AAPL': {'prints': [], 'printCount': 0,
                    'shareCount': 0, 'notional': 0, 'dataStatus': 'STALE'}}}}
        with patch('market_features.get', return_value=Mock(json=lambda: {'raw': rows})):
            update(feed)
            update(feed)
        section = feed['darkPoolPrints']
        asset = section['assets']['AAPL']
        self.assertEqual(asset['printCount'], 1)
        self.assertEqual(asset['shareCount'], 200)
        self.assertEqual(asset['notional'], 20000)
        self.assertEqual(asset['observedAt'], '2026-11-13')
        self.assertIn('PROVIDER REPORTED', asset['dataStatus'])
        self.assertEqual(section['visiblePrintCount'], 1)
        self.assertEqual(len(section['prints']), 1)
        self.assertEqual(section['infolib']['visibleRows'], 1)
        self.assertIn('InfoLib', section['sources'])

    def test_date_only_without_direction_inference(self):
        row = normalize(dict(date='2026-11-13 04:08 PM', symbol='AAPL', price=100, size=200, avg_paid=20000))
        self.assertEqual(row['timestamp'], '2026-11-13')
        self.assertEqual(row['timestampPrecision'], 'date')
        self.assertEqual(row['side'], 'UNKNOWN')
        self.assertIsNone(row['timezone'])

    def test_reject_inconsistent_or_nonfinite_value(self):
        for value in (50000, float('nan')):
            self.assertIsNone(normalize(dict(date='2026-11-13 04:08 PM', symbol='AAPL', price=100, size=200, avg_paid=value)))
