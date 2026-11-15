import unittest
from unittest.mock import patch
from update_preview import finalize


class ArchiveClasses(unittest.TestCase):
    def test_same_date_contracts_do_not_overwrite(self):
        feed={'economies':{},'options':{'markets':[{'ticker':'DAX','asOf':'2026-11-13','profiles':[
            {'contractCode':'ODAX','expiration':'2026-11-20','callOi':100},
            {'contractCode':'ODAP','expiration':'2026-11-20','callOi':200}]}]}}
        with patch('v7_economy_state.synchronize'):
            finalize(feed)
        archive=feed['options']['dailySnapshots']
        self.assertEqual(archive['DAX:2026-11-20:ODAX'][0]['callOi'],100)
        self.assertEqual(archive['DAX:2026-11-20:ODAP'][0]['callOi'],200)
