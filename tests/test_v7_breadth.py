import unittest
from datetime import date, timedelta
from v7_breadth import price_metrics, same_session

class BreadthTests(unittest.TestCase):
    def test_stale_members_excluded(self):
        rows=[('A',self.bars(252)),('B',self.bars(253)),('C',self.bars(253))]
        self.assertEqual([r[0] for r in same_session(rows)],['B','C'])
        self.assertEqual(same_session([]),[])

    def bars(self, n):
        return [{'date':date(2025,8,1)+timedelta(days=i), 'close':100+i} for i in range(n)]

    def test_sma_and_missing_history(self):
        r=price_metrics(self.bars(100),2026)
        self.assertEqual(r['sma'][20],189.5)
        self.assertEqual(r['sma'][50],174.5)
        self.assertEqual(r['sma'][100],149.5)
        self.assertIsNone(r['sma'][200])
        self.assertIsNone(r['nearHigh'])

    def test_new_close_is_not_near_high(self):
        bars=self.bars(253)
        r=price_metrics(bars,2026)
        self.assertTrue(r['newClosingHigh'])
        self.assertFalse(r['newClosingLow'])
        bars[-1]['close']=350
        r=price_metrics(bars,2026)
        self.assertTrue(r['nearHigh'])
        self.assertFalse(r['newClosingHigh'])

    def test_ytd_previous_year_last_close(self):
        bars=[{'date':date(2025,12,31),'close':100},
              {'date':date(2026,1,2),'close':110},
              {'date':date(2026,1,5),'close':120}]
        self.assertAlmostEqual(price_metrics(bars,2026)['ytd'],.2)
        self.assertIsNone(price_metrics(bars[1:],2026)['ytd'])
