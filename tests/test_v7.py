import math
import unittest
from v7_quant import gamma_flip
from market_features import _max_pain
from update_preview import dated_rows
from update_preview import bank_due
from datetime import datetime, timezone, timedelta
from v7_curves import store_curve, parse_japan_csv, parse_rba_csv, parse_snb_csv, parse_bundesbank_csv

class V7Tests(unittest.TestCase):
    def test_snb_does_not_mix_euro_or_corporate_curves(self):
        text='"CubeId";"rendeiduebd"\n"Date";"D0";"D1";"Value"\n"2026-10-30";"CHF";"2J";"-0.1"\n"2026-10-30";"EUR";"2J";"3.0"\n"2026-10-30";"KTA";"2J";"1.0"'
        self.assertEqual(parse_snb_csv(text), [{'date':'2026-10-30','values':{'2Y':-0.1}}])

    def test_bundesbank_excludes_non_trading_days(self):
        text='last update,2026-11-13\n2026-11-12,3.09,\n2026-11-13,3.13,\n2026-11-14,.,No value available'
        rows=parse_bundesbank_csv(text,'2Y')
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[-1]['values']['2Y'],3.13)

    def test_rba_excludes_indexed_bond_and_blank_observations(self):
        rows, published = parse_rba_csv('Publication date,13-Nov-2026\nSeries ID,FCMYGBAG2D,FCMYGBAG10D,FCMYGBAGID\n12-Nov-2026,4.0,,2.5\n')
        self.assertEqual(published, '2026-11-13')
        self.assertEqual(rows[0]['values'], {'2Y':4.0,'10Y':None})

    def test_japan_csv_dates_missing_and_negative_yields(self):
        rows = parse_japan_csv('Interest Rate,,,,\r\r\nDate,1Y,2Y,20Y,30Y\r\r\n2026/1/2,-0.1,0.2,-,1.5\r\r\nFootnote,,,,')
        self.assertEqual(rows, [{'date':'2026-01-02','values':{'1Y':-0.1,'2Y':0.2,'20Y':None,'30Y':1.5}}])

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
