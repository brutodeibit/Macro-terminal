import unittest
from datetime import datetime, timezone
from v7_eurex import chain_rows, expiration_time
from market_features import _max_pain

class EurexTests(unittest.TestCase):
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

