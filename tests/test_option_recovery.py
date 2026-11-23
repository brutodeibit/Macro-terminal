import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import market_features as mf
from v7_option_retention import retain_chains


class OptionRecovery(unittest.TestCase):
    def test_reference_does_not_erase_chain_or_change_valuation_spot(self):
        old = {'ticker':'SPY','spot':100,'asOf':'2026-11-17',
               'profiles':[{'expiration':'2026-12-18','strikeMap':[{'strike':100,'callOi':12}]}]}
        before = copy.deepcopy(old)
        ref = {'ticker':'SPY','referenceOnly':True,'spot':110,'asOf':'2026-11-23'}
        result = retain_chains([ref], [old])[0]
        self.assertEqual(result['spot'],100)
        self.assertEqual(result['asOf'],'2026-11-17')
        self.assertEqual(result['latestReference']['spot'],110)
        self.assertTrue(result['retainedChain'])
        self.assertFalse(result['referenceOnly'])
        self.assertEqual(old,before)

    def test_new_chain_replaces_retained_and_aggregate_does_not(self):
        old={'ticker':'SPX','retainedChain':True,'profiles':[{'strikeMap':[{'strike':100}]}]}
        new={'ticker':'SPX','profiles':[{'strikeMap':[{'strike':101}]}]}
        self.assertEqual(retain_chains([new],[old]),[new])
        aggregate={'ticker':'SPX','profiles':[{'gammaFlip':103}]}
        self.assertTrue(retain_chains([aggregate],[old])[0]['retainedChain'])

    def test_missing_symbol_is_retained_but_empty_reference_is_not_chain(self):
        old={'ticker':'GLD','profiles':[{'strikeMap':[{'strike':100}]}]}
        self.assertEqual(retain_chains([], [old])[0]['ticker'],'GLD')
        ref={'ticker':'GLD','profiles':[]}
        self.assertEqual(retain_chains([ref], [ref]),[ref])

    def test_yahoo_initializes_cookie_and_does_not_leak_crumb(self):
        session=Mock()
        session.get.side_effect=[Mock(status_code=404),Mock(text='test-crumb'),
                                 Mock(status_code=200,json=lambda:{'optionChain':{'result':[{'expirationDates':[1]}]}})]
        with patch.object(mf,'_YAHOO_OPTIONS_SESSION',None),patch.object(mf,'_YAHOO_OPTIONS_CRUMB',None),patch.object(mf.requests,'Session',return_value=session):
            self.assertEqual(mf._yahoo_option_chain('SPY'),{'expirationDates':[1]})
        self.assertEqual(session.get.call_args_list[0].args[0],'https://fc.yahoo.com')

    def test_nested_yahoo_expiry_rows_are_parsed(self):
        day=(datetime.now(timezone.utc)+timedelta(days=10)).replace(hour=0,minute=0,second=0,microsecond=0)
        expiry=int(day.timestamp())
        calls=[{'strike':k,'openInterest':10,'volume':2,'impliedVolatility':.2,'bid':1,'ask':2} for k in (90,100,110)]
        payload={'quote':{'regularMarketPrice':100},'expirationDates':[expiry],
                 'options':[{'expirationDate':expiry,'calls':calls,'puts':calls}]}
        with patch.object(mf,'_yahoo_option_chain',return_value=payload):
            result=mf.opt('SPY')
        self.assertIsNotNone(result)
        self.assertEqual(result['profiles'][0]['totalOpenInterest'],60)
        self.assertEqual(result['profiles'][0]['oiCoveragePct'],100)
        self.assertIsNone(result['oiObservedAt'])
        self.assertTrue(result['asOf'])

    def test_zero_day_oi_survives_but_unverified_intraday_gamma_does_not(self):
        expiry=int(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
        rows=[{'strike':100,'openInterest':10,'impliedVolatility':.2}]
        payload={'quote':{'regularMarketPrice':100},'expirationDates':[expiry],
                 'options':[{'expirationDate':expiry,'calls':rows,'puts':rows}]}
        with patch.object(mf,'_yahoo_option_chain',return_value=payload):
            result=mf.opt('SPY')
        p=result['profiles'][0]
        self.assertEqual(p['totalOpenInterest'],20)
        self.assertIsNone(p['gammaFlip'])
        self.assertIsNone(p['gammaNet'])
        self.assertTrue(all(x['gex'] is None for x in p['strikeMap']))

    def test_monthly_not_excluded_by_four_weekly_buckets(self):
        start=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
        dates=[start+timedelta(days=n) for n in (0,1,8,32)]
        monthly=next(start+timedelta(days=n) for n in range(1,45)
                     if (start+timedelta(days=n)).weekday()==4 and 15<=(start+timedelta(days=n)).day<=21)
        expiries=sorted({int(d.timestamp()) for d in dates+[monthly]})
        rows=[{'strike':100,'openInterest':0,'impliedVolatility':.2}]
        def chain(sym,expiry=None):
            return {'quote':{'regularMarketPrice':100},'expirationDates':expiries,
                    'options':[{'expirationDate':expiry,'calls':rows,'puts':rows}]}
        with patch.object(mf,'_yahoo_option_chain',side_effect=chain):
            result=mf.opt('SPY')
        self.assertIn(monthly.date().isoformat(),[p['expiration'] for p in result['profiles']])
        self.assertTrue(all(p['gammaNet'] is None for p in result['profiles']))

    def test_actual_collector_keeps_chain_when_only_reference_arrives(self):
        from contextlib import ExitStack
        old={'ticker':'SPY','spot':100,'asOf':'2026-11-17',
             'profiles':[{'expiration':'2026-12-18','strikeMap':[{'strike':100,'callOi':12}]}]}
        feed={'options':{'markets':[old],'history':{'SPY':[]}}}
        with ExitStack() as stack:
            stack.enter_context(patch.object(mf,'OPTION_CATALOG',[{'code':'SPY','yahoo':'SPY','label':'SPY','family':'S&P 500','kind':'etf'}]))
            for fn in ('_massive_option_chain','opt','_barchart_option_overview','_crypto_spot_etf_flows','_deribit_options'):
                stack.enter_context(patch.object(mf,fn,return_value=None))
            stack.enter_context(patch.object(mf,'_option_reference_entry',return_value={'ticker':'SPY','referenceOnly':True,'spot':110}))
            mf.update_options(feed)
        self.assertEqual(feed['options']['markets'][0]['profiles'],old['profiles'])
        self.assertEqual(feed['options']['history']['SPY'],[])
        self.assertEqual(feed['options']['providerStatus']['retainedMarkets'],1)


if __name__=='__main__':
    unittest.main()
