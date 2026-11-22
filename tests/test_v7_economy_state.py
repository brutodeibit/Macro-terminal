import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, timezone
from v7_economy_state import synchronize

class EconomyStateTests(unittest.TestCase):
    def test_boj_opinions_do_not_become_a_new_meeting(self):
        from v7_meetings import is_decision_publication
        title = 'Summary of Opinions at the Monetary Policy Meeting on October 29 and 30, 2026'
        url = 'https://www.boj.or.jp/en/mopo/mpmsche_minu/opinion_2026/opi261030.pdf'
        self.assertFalse(is_decision_publication('jp', title, url))
        self.assertTrue(is_decision_publication('uk', 'Monetary Policy Summary and Minutes'))
        feed = {'economies': {'jp': {'conference': {'meetingArchive': [
            {'date': '2026-11-09', 'title': title, 'sourceUrl': url, 'publicationType': 'decision'}]}}}}
        synchronize(feed, '2026-11-22')
        conference = feed['economies']['jp']['conference']
        self.assertEqual(conference['history'][0]['date'], '2026-10-30')
        self.assertEqual(len(conference['documents']), 1)
        self.assertEqual(conference['documents'][0]['publicationType'], 'supporting_document')
        self.assertNotIn('meetingDate', conference['documents'][0])

    def test_reviewed_updates_apply_when_network_jobs_are_cached(self):
        import update_preview as p
        job=Mock()
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'feed.json'
            target.write_text(json.dumps({'economies':{'au':{'conference':{},'rates':{}}},
                'sourceHealth':{'CACHED':{'checkedAt':datetime.now(timezone.utc).isoformat()}}}),encoding='utf-8')
            with patch.object(p,'TARGET',target),patch.object(p,'JOBS',{'CACHED':(job,24)}):
                p.run()
            job.assert_not_called()
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['economies']['au']['rates']['official'],'4.85%')
    def test_latest_reviewed_decision_for_all_banks(self):
        keys=['us','eu','uk','jp','au','nz','ca','ch']
        f={'economies':{k:{'conference':{},'rates':{}} for k in keys}}
        synchronize(f,'2026-11-08')
        for k in keys:
            c=f['economies'][k]['conference']
            self.assertTrue(c['keyPoints'],k)
            self.assertNotIn('Pendiente',c['tone'],k)
            self.assertTrue(c['history'][0]['sourceUrl'].startswith('https://'))
        self.assertEqual(f['economies']['jp']['rates']['official'],'1.25%')
        self.assertEqual(f['economies']['au']['rates']['official'],'4.85%')
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
