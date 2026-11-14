import unittest
from unittest.mock import patch, Mock
import market_features as mf


class BondFallbackTests(unittest.TestCase):
    def test_missing_tenor_is_created_with_observation_date(self):
        feed={'economies':{'uk':{'bonds':{'tenors':[]}}}}
        def response(url, params):
            return Mock(json=lambda:[{'Country':'United Kingdom','Last':4.12,'Date':'2026-01-02T16:00:00','DailyChange':.02}] if params['type']=='2Y' else [])
        with patch.dict('os.environ',{'TE_API_KEY':'test'}), patch.object(mf,'get',side_effect=response):
            mf.update_bond_curves(feed)
        row=feed['economies']['uk']['bonds']['tenors'][0]
        self.assertEqual(row['term'],'2Y')
        self.assertEqual(row['yield'],'4.120%')
        self.assertEqual(row['observedAt'],'2026-01-02')
        self.assertEqual(row['change1dBp'],2)

    def test_undated_response_does_not_replace_existing_value(self):
        row={'term':'2Y','yield':'4.000%','observedAt':'2026-01-01'}
        feed={'economies':{'uk':{'bonds':{'tenors':[row]}}}}
        with patch.dict('os.environ',{'TE_API_KEY':'test'}), patch.object(mf,'get',return_value=Mock(json=lambda:[{'Country':'United Kingdom','Last':99}])):
            mf.update_bond_curves(feed)
        self.assertEqual(row['yield'],'4.000%')
        self.assertEqual(row['observedAt'],'2026-01-01')
