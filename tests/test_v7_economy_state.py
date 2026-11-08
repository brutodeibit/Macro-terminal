import unittest
from v7_economy_state import synchronize

class EconomyStateTests(unittest.TestCase):
    def test_reviewed_meetings_replace_stale_prose(self):
        f={'economies':{'us':{'conference':{'watchFactors':['FOMC octubre'],'toneDescription':'Antiguo'},'rates':{}}}}
        synchronize(f,'2026-11-08')
        c=f['economies']['us']['conference']
        self.assertEqual(len(c['history']),3)
        self.assertEqual(c['history'][0]['date'],'2026-10-28')
        self.assertEqual(f['economies']['us']['rates']['official'],'3.75–4.00%')
        self.assertNotIn('FOMC octubre',c['watchFactors'])
        self.assertNotEqual(c['toneDescription'],'Antiguo')
        synchronize(f,'2026-11-08')
        self.assertEqual(len(c['history']),3)
    def test_new_meeting_cannot_inherit_previous_interpretation(self):
        f={'economies':{'us':{'conference':{'meetingArchive':[{'date':'2026-12-09','summary':'New'}]}}}}
        synchronize(f,'2026-12-10')
        c=f['economies']['us']['conference']
        self.assertEqual(c['summary'],'New')
        self.assertEqual(c['keyPoints'],[])
        self.assertNotIn('pausa',c['toneDescription'].lower())
