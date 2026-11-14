import unittest
from unittest.mock import patch
import update_preview as preview


class PreservationTests(unittest.TestCase):
    def test_cached_eurex_survives_general_options_refresh(self):
        old = dict(ticker='DAX', source='Eurex · ODAX', profiles=[{'maxPain':100}])
        feed = {'options':{'markets':[old]}}
        def refresh(f):
            f['options'] = {'markets':[{'ticker':'DAX'}, {'ticker':'SPY'}]}
        with patch.object(preview.mf, 'update_options', side_effect=refresh):
            preview.options(feed)
        self.assertIn(old, feed['options']['markets'])
        self.assertEqual(len(feed['options']['markets']), 2)

    def test_cached_prints_survive_other_provider(self):
        row = {'sourceMode':'PROVIDER_REPORTED', 'price':100}
        feed = {'darkPoolPrints':{'assets':{'AAPL':{'prints':[row]}}, 'infolib':{'rows':1}}}
        def refresh(f):
            f['darkPoolPrints'] = {'assets':{'AAPL':{'prints':[]}}}
        with patch.object(preview.mf, 'update_dark_pool_prints', side_effect=refresh):
            preview.dark_prints(feed)
        self.assertEqual(feed['darkPoolPrints']['assets']['AAPL']['prints'], [row])
        self.assertEqual(feed['darkPoolPrints']['infolib']['rows'], 1)
