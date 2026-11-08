import unittest
from v7_calendar import parse, update, bls_events

class CalendarTests(unittest.TestCase):
    def test_bls_eastern_time(self):
        r=bls_events('BEGIN:VEVENT\nDTSTART;TZID=US-Eastern:20261110T083000\nSUMMARY:Consumer Price Index\nEND:VEVENT')
        self.assertEqual(r[0]['date'],'2026-11-10T13:30:00+00:00')
        self.assertEqual(r[0]['source'],'BLS · calendario oficial')
    def test_timezone_and_missing_consensus(self):
        rows=parse([{'country':'USD','title':'CPI','date':'2026-11-10T08:30:00-05:00','impact':'High'}],'https://example.test')
        self.assertEqual(rows[0]['date'],'2026-11-10T13:30:00+00:00')
        self.assertEqual(rows[0]['forecast'],'')
        self.assertEqual(rows[0]['importance'],3)
    def test_unknown_timezone_is_not_guessed(self):
        self.assertEqual(parse([{'country':'GBP','date':'2026-11-10T08:30:00'}],'x'),[])
    def test_outage_retains_prior_events(self):
        feed={'economicCalendar':{'events':[{'id':'x','date':'2026-11-10','source':'Forex Factory'}]}}
        def fail(url):raise ValueError('Outage')
        update(feed,fail)
        self.assertEqual(len(feed['economicCalendar']['events']),1)
        self.assertEqual(feed['economicCalendar']['releaseCalendarStatus'],'partial')
