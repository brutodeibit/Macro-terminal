import unittest
from datetime import datetime, timezone
from v7_dark import four_hour, candles_from_series

class DarkTests(unittest.TestCase):
    def test_four_hour_never_crosses_session(self):
        rows=[]
        for day in (5,6):
            start=datetime(2026,11,day,14,30,tzinfo=timezone.utc).timestamp()
            rows.extend({'ts':start+i*3600,'open':100+i,'high':102+i,'low':99+i,'close':101+i} for i in range(7))
        result=four_hour(rows,'America/New_York')
        self.assertEqual([r['observations'] for r in result],[4,3,4,3])
        self.assertEqual((result[0]['open'],result[0]['high'],result[0]['low'],result[0]['close']),(100,105,99,104))
    def test_invalid_candles_not_fabricated(self):
        series={'timestamp':[1,2], 'indicators':{'quote':[{'open':[100,None],'high':[102,102],'low':[99,99],'close':[101,101]}]}}
        self.assertEqual(len(candles_from_series(series)),1)
