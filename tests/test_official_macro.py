import unittest
from v7_official_macro import observations, update
from unittest.mock import Mock


class OfficialMacroTests(unittest.TestCase):
    def test_sparse_jsonstat_preserves_zero_and_observation_flags(self):
        data={'id':['geo','time'],'size':[1,3],
              'dimension':{'geo':{'category':{'index':{'EA21':0}}},
                           'time':{'category':{'index':{'2026-08':0,'2026-09':1,'2026-10':2}}}},
              'value':{'0':0,'2':2.3},'status':{'2':'p'}}
        result=observations(data,{'geo':'EA21'})
        self.assertEqual([r['value'] for r in result],[0,2.3])
        self.assertEqual(result[-1]['status'],'p')
        self.assertEqual(result[-1]['referencePeriod'],'2026-10')
        with self.assertRaises(ValueError):
            observations(data,{'geo':'EA20'})

    def test_unfiltered_dimension_is_rejected(self):
        data={'id':['geo','time'],'size':[2,1],
              'dimension':{'geo':{'category':{'index':{'DE':0,'FR':1}}},
                           'time':{'category':{'index':{'2026-10':0}}}},'value':[1,2]}
        with self.assertRaises(ValueError):
            observations(data,{})

    def test_network_failure_preserves_official_value_and_date(self):
        row={'id':'eurostat:eu:gdp','actual':'0.2%','referencePeriod':'2026-Q2'}
        feed={'economies':{'eu':{'indicators':[row]}}}
        update(feed,Mock(side_effect=RuntimeError('Unavailable')))
        self.assertEqual(row['actual'],'0.2%')
        self.assertEqual(row['referencePeriod'],'2026-Q2')
        self.assertTrue(row['dataStatus'].startswith('STALE'))
        self.assertNotIn('publishedAt',row)
