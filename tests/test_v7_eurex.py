import unittest
import json
from unittest.mock import patch, Mock
from datetime import datetime, timezone, timedelta
from v7_eurex import chain_rows, expiration_time
from market_features import _max_pain

class EurexTests(unittest.TestCase):
    def test_selected_expiries_and_contract_coverage_are_recorded(self):
        import v7_eurex
        today=datetime.now(timezone.utc)
        busdate=(today-timedelta(days=2)).strftime('%Y%m%d')
        dates=[(today+timedelta(days=d)).strftime('%Y%m%d') for d in (10,40)]
        def get(url, params=None):
            if params is None:
                cfg=json.dumps({'productId':'test','busDate':busdate})
                return Mock(text='<script data-product="true">'+cfg+'</script>')
            if params['filtertype']=='overview':
                return Mock(json=lambda:{'meta':{'productCode':'OESX'},'header':{'underlyingClosingPrice':100},
                         'dataRows':[{'date':day,'contractType':'M'} for day in dates]})
            return Mock(json=lambda:{'meta':{'productCode':'OESX'},'dataRowsCall':[{'strike':100,'openInterest':10}],
                                     'dataRowsPut':[{'strike':100,'openInterest':20}]})
        feed={'options':{'markets':[]}}
        with patch.object(v7_eurex,'PRODUCTS',{'SX5E':('OESX','https://example.invalid')}), patch.object(v7_eurex,'DAILY_PRODUCTS',{}),patch('market_features.get',side_effect=get):
            v7_eurex.update(feed)
        market=feed['options']['markets'][0]
        self.assertEqual(market['expiryCoverage']['OESX']['availableExpirations'],dates)
        self.assertEqual(len(market['expiryCoverage']['OESX']['selectedExpirations']),2)
        self.assertTrue(all(p['underlyingClose']==100 for p in market['profiles']))
        self.assertTrue(all(p['gammaFlip'] is None for p in market['profiles']))

    def test_contract_cutoffs_and_daylight_saving(self):
        self.assertEqual(expiration_time('20261120','ODAX').hour,12)
        self.assertEqual(expiration_time('20260619','ODAX').hour,11)
        self.assertEqual(expiration_time('20261120','OXXP').hour,11)
        self.assertEqual(expiration_time('20261120','EXSA').isoformat(),'2026-11-20T16:30:00+00:00')

    def test_missing_oi_excluded_and_no_fake_greeks(self):
        expiry=datetime(2027,1,15,tzinfo=timezone.utc)
        rows=chain_rows({'dataRowsCall':[{'strike':100,'openInterest':12,'dSettle':5},
                                       {'strike':110,'openInterest':None}],
                         'dataRowsPut':[{'strike':100,'openInterest':20,'volume':3}]},expiry)
        self.assertEqual(len(rows),2)
        self.assertEqual([r['type'] for r in rows],['C','P'])
        self.assertTrue(all(r['gamma'] is None and r['iv'] is None for r in rows))
        self.assertEqual(_max_pain(rows[:1],rows[1:]),100)

