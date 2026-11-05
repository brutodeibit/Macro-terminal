"""Offline regression tests for Farside daily US spot ETF flows."""
import unittest
from unittest.mock import patch
import market_features

class Resp:
 def __init__(self, html):
  self.text=html

def fixture(asset):
 name="IBIT" if asset=="BTC" else "ETHA"
 return (
  '<html><table><tr><th>Date</th><th>'+name+'</th><th>Total</th></tr>'
  '<tr><td>02 Nov 2026</td><td>12.0</td><td>12.0</td></tr>'
  '<tr><td>03 Nov 2026</td><td>(8.5)</td><td>(8.5)</td></tr>'
  '<tr><td>04 Nov 2026</td><td>0.0</td><td>0.0</td></tr>'
  '</table></html>'
 )

class TestFarsideFlows(unittest.TestCase):
 def test_btc_dates_sign_and_zero(self):
  with patch.object(market_features,"get",return_value=Resp(fixture("BTC"))):
   d=market_features._crypto_spot_etf_flows("BTC")
  self.assertIsNotNone(d)
  self.assertEqual(d["asOf"],"2026-11-04")
  self.assertEqual([x["netFlowUsdM"] for x in d["history"]],[12.0,-8.5,0.0])
  self.assertAlmostEqual(d["netFlow5d"],3.5)
 def test_eth_header_and_dates(self):
  with patch.object(market_features,"get",return_value=Resp(fixture("ETH"))):
   d=market_features._crypto_spot_etf_flows("ETH")
  self.assertIsNotNone(d)
  self.assertEqual(d["history"][0]["date"],"2026-11-02")
  self.assertEqual(d["provider"],"Farside Investors")
 def test_missing_table_is_unavailable_not_zero(self):
  with patch.object(market_features,"get",return_value=Resp("<html><div>blocked</div></html>")):
   self.assertIsNone(market_features._crypto_spot_etf_flows("BTC"))

if __name__=="__main__":
 unittest.main()
