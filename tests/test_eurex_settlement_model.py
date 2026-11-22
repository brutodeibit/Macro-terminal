from datetime import datetime, timezone
import math
import unittest
from v7_eurex_model import black_price, fit_parity, settlement_model


def fixture():
    years = 30/365
    forward, discount = 100*math.exp(.01*years), math.exp(-.03*years)
    rows = []
    for strike in range(85,116,3):
        for side in ('C','P'):
            rows.append(dict(strike=strike, type=side, openInterest=100 if side=='C' else 150,
                             volume=2, version=0,
                             settlementPrice=black_price(forward,strike,.2*math.sqrt(years),discount,side)))
    return rows


class SettlementModelTests(unittest.TestCase):
    def model(self, rows, code='OESX', expiry='2026-12-20'):
        return settlement_model(rows,100,'2026-11-20',datetime.fromisoformat(expiry).replace(tzinfo=timezone.utc),code)

    def test_black_price_matches_known_european_call(self):
        self.assertAlmostEqual(black_price(100*math.exp(.05),100,.2,math.exp(-.05),'C'),10.450583572185565,places=10)

    def test_fit_recovers_known_carry_and_iv_without_provider_greeks(self):
        fit = fit_parity(fixture(),100,30/365,.1)
        self.assertAlmostEqual(fit['rate'],.03,places=9)
        self.assertAlmostEqual(fit['dividendYield'],.02,places=9)
        result = self.model(fixture())
        self.assertEqual(result['settlementModel']['status'],'derived')
        self.assertAlmostEqual(result['ivAtm'],20,places=8)
        self.assertEqual(result['providerGreeksCoveragePct'],0)
        self.assertEqual(result['gammaFlipCoveragePct'],100)
        self.assertLess(result['gammaNet'],0)

    def test_contract_multiplier_changes_exposure_not_root(self):
        a,b = self.model(fixture(),'OESX'), self.model(fixture(),'ODAX')
        self.assertAlmostEqual(a['gammaNet'],2*b['gammaNet'])
        self.assertEqual(a['gammaFlip'],b['gammaFlip'])

    def test_gex_matches_numerical_repricing_of_option_values(self):
        rows=fixture();result=self.model(rows)
        years=30/365;discount=math.exp(-.03*years);carry=math.exp(.01*years)
        step=.01;reference=0
        for row in rows:
            def price(s):
                return black_price(s*carry,row['strike'],.2*math.sqrt(years),discount,row['type'])
            gamma=(price(100+step)-2*price(100)+price(100-step))/step**2
            reference+=(1 if row['type']=='C' else -1)*row['openInterest']*gamma*10*100**2*.01
        self.assertAlmostEqual(result['gammaNet'],reference,delta=abs(reference)*1e-6)

    def test_inconsistent_settlements_do_not_generate_a_level(self):
        rows=fixture(); rows[0]['settlementPrice'] += 5
        result=self.model(rows)
        self.assertIsNone(result['gammaFlip'])
        self.assertEqual(result['settlementModel']['status'],'unavailable')
        self.assertNotIn('gammaNet',result)

    def test_missing_prices_on_high_oi_do_not_become_zero_volatility(self):
        rows=fixture()
        rows[6]['openInterest']=10000
        rows[6]['settlementPrice']=None
        result=self.model(rows)
        self.assertIsNone(result['gammaFlip'])
        self.assertLess(result['gammaFlipCoveragePct'],90)
        self.assertNotIn('gammaNet',result)

    def test_unsupported_style_and_intraday_are_rejected(self):
        for code, expiry in [('EXSA','2026-12-20'),('OESX','2026-11-21')]:
            result=self.model(fixture(),code,expiry)
            self.assertIsNone(result['gammaFlip'])
            self.assertEqual(result['settlementModel']['status'],'unavailable')

    def test_duplicate_versions_are_not_summed(self):
        rows=fixture(); rows.append(dict(rows[0]))
        self.assertEqual(self.model(rows)['settlementModel']['status'],'unavailable')

    def test_no_root_is_explained_instead_of_zero(self):
        result=self.model(fixture())
        self.assertIsNone(result['gammaFlip'])
        self.assertEqual(result['gammaFlipRoots'],[])
        self.assertIn('No sign change',result['gammaFlipStatus'])

    def test_settlement_iv_survives_when_no_open_interest_can_support_gex(self):
        rows = [{**row, 'openInterest': 0} for row in fixture()]
        result = self.model(rows)
        self.assertAlmostEqual(result['ivAtm'], 20, places=8)
        self.assertIsNone(result['gammaFlip'])
        self.assertIsNone(result['gammaFlipCoveragePct'])
        self.assertIn('Sin interés abierto', result['gammaFlipStatus'])
