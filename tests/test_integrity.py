import unittest
from data_integrity import bls_observation, transform_monthly
from market_features import _option_gex

class IntegrityTests(unittest.TestCase):
    def test_month_gap_is_not_previous_month(self):
        self.assertIsNone(transform_monthly({'2026-01':100,'2026-03':110},'2026-03','change'))
    def test_payroll_is_change_in_thousands(self):
        rows=[{'year':'2026','period':'M02','value':'159100'},{'year':'2026','period':'M01','value':'159000'}]
        self.assertEqual(bls_observation(rows,'CES0000000001'),(100,'2026-02','change'))
    def test_wages_are_annual_growth(self):
        rows=[{'year':'2026','period':'M02','value':'39'},{'year':'2025','period':'M02','value':'37.5'}]
        self.assertAlmostEqual(bls_observation(rows,'CES0500000003')[0],4)
    def test_price_index_is_not_inflation(self):
        self.assertAlmostEqual(transform_monthly({'2026-02':103,'2025-02':100},'2026-02','yoy'),3)
    def test_cumulative_crossing_is_not_gamma_flip(self):
        result=_option_gex([{'strike':110,'gamma':.02,'openInterest':200}],[{'strike':90,'gamma':.01,'openInterest':100}],100)
        self.assertIsNone(result['gammaFlip'])
        self.assertIsNotNone(result['cumulativeStrikeCrossing'])

if __name__=='__main__': unittest.main()
