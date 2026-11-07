import math
import unittest
from v7_quant import gamma_flip
from market_features import _max_pain
from update_preview import dated_rows
from update_preview import bank_due
from datetime import datetime, timezone, timedelta
from v7_curves import store_curve

class V7Tests(unittest.TestCase):
    def test_known_gamma_root_and_sensitivity(self):
        rows = [{'strike':90,'iv':.2,'openInterest':100,'type':'P'},
                {'strike':110,'iv':.2,'openInterest':100,'type':'C'}]
        r = gamma_flip(rows,100,.1,rate=0)
        expected = math.sqrt(90*110)*math.exp(-.5*.2**2*.1)
        self.assertAlmostEqual(r['gammaFlip'],expected,places=5)
        self.assertNotEqual(r['gammaFlipSensitivity']['putWeight80'],r['gammaFlipRoots'])

    def test_no_root_is_not_zero(self):
        rows=[{'strike':100,'iv':.2,'openInterest':200,'type':'C'},
              {'strike':100,'iv':.2,'openInterest':100,'type':'P'}]
        self.assertIsNone(gamma_flip(rows,100,.1)['gammaFlip'])
        self.assertEqual(gamma_flip(rows,100,.1)['gammaFlipRoots'],[])

    def test_missing_iv_and_expiry(self):
        rows=[{'strike':100,'iv':None,'openInterest':100,'type':'P'}]
        self.assertIsNone(gamma_flip(rows,100,.1)['gammaFlip'])
        self.assertIn('Expired',gamma_flip(rows,100,0)['gammaFlipStatus'])

    def test_max_pain_matches_brute_force(self):
        calls=[{'strike':k,'openInterest':oi} for k,oi in [(90,20),(100,100),(110,30)]]
        puts=[{'strike':k,'openInterest':oi} for k,oi in [(90,70),(100,40),(110,10)]]
        payoff=lambda s:sum(x['openInterest']*max(s-x['strike'],0) for x in calls)+sum(x['openInterest']*max(x['strike']-s,0) for x in puts)
        self.assertEqual(_max_pain(calls,puts),min([90,100,110],key=payoff))

    def test_dates_deduplicated_and_sorted(self):
        rows=[{'date':'2026-01-02','v':1},{'date':'2026-01-01','v':2},{'date':'2026-01-02','v':3}]
        self.assertEqual([x['v'] for x in dated_rows(rows)],[2,3])

    def test_bank_event_schedule_and_backoff(self):
        now=datetime(2026,12,9,20,tzinfo=timezone.utc)
        self.assertTrue(bank_due('us',(now-timedelta(hours=3)).isoformat(),now))
        self.assertFalse(bank_due('us',(now-timedelta(minutes=30)).isoformat(),now))
        self.assertFalse(bank_due('jp',(now-timedelta(hours=3)).isoformat(),now))

    def test_curve_bp_and_missing_history(self):
        f={'economies':{'ca':{}}}
        store_curve(f,'ca',[{'date':'2026-01-01','values':{'2Y':3.1}},{'date':'2026-01-02','values':{'2Y':3.12}}],'test','https://example.com','fixture')
        t=f['economies']['ca']['bonds']['tenors'][0]
        self.assertEqual(t['change1dBp'],2)
        self.assertIsNone(t['change5sBp'])
        self.assertIsNone(t['changeYtdBp'])

if __name__=='__main__':unittest.main()
