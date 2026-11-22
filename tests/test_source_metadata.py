from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import Mock, patch
import market_features as mf


class SourceMetadataTests(unittest.TestCase):
    def test_modeled_greeks_are_not_counted_as_provider_greeks(self):
        expiry = (datetime.now(timezone.utc) + timedelta(days=10)).strftime('%y%m%d')
        rows = [{'option': 'SPY' + expiry + side + '00100000', 'open_interest': 100,
                 'volume': 1, 'iv': .25, 'bid': 1, 'ask': 2} for side in ('C', 'P')]
        payload = {'timestamp': datetime.now(timezone.utc).isoformat(),
                   'data': {'current_price': 100, 'options': rows}}
        with patch.object(mf, 'get', return_value=Mock(json=lambda: payload)), patch.object(mf, 'chart', return_value=None):
            market = mf._cboe_option_chain('SPY')
        self.assertIsNotNone(market)
        self.assertEqual(market['profiles'][0]['providerGreeksCoveragePct'], 0)
        self.assertEqual(market['profiles'][0]['providerIvCoveragePct'], 100)

    def test_finra_uses_available_partition_week(self):
        week = '2026-09-07'
        responses = []
        def post(url, payload, *_):
            if '/partitions/' in url:
                body = {'availablePartitions': [{'partitions': [week]}]}
            else:
                selected = next(f['fieldValue'] for f in payload['compareFilters'] if f['fieldName'] == 'weekStartDate')
                responses.append(selected)
                body = [{'totalWeeklyShareQuantity': 100, 'totalWeeklyTradeCount': 2}]
            return Mock(json=lambda: body)
        feed = {}
        with patch.object(mf, 'finra_access_token', return_value='test'), patch.object(mf, 'post', side_effect=post):
            mf._update_dark_pools_finra(feed)
        self.assertTrue(responses)
        self.assertEqual(set(responses), {week})
        self.assertTrue(all(m['weekStart'] == week for m in feed['darkPools']['markets']))


if __name__ == '__main__':
    unittest.main()
