import unittest
from unittest.mock import patch
from update_preview import finalize, options


class ArchiveClasses(unittest.TestCase):
    def test_options_refresh_keeps_previous_daily_closes(self):
        snapshots = {'SPX:2026-12-18': [{'date':'2026-11-20','callOi':100}]}
        feed = {'options': {'dailySnapshots': snapshots}}
        with patch('market_features.update_options', side_effect=lambda target: target.update(options={'markets':[]})):
            options(feed)
        self.assertEqual(feed['options']['dailySnapshots'], snapshots)

    def test_same_date_contracts_do_not_overwrite(self):
        feed={'economies':{},'options':{'markets':[{'ticker':'DAX','asOf':'2026-11-13','profiles':[
            {'contractCode':'ODAX','expiration':'2026-11-20','callOi':100},
            {'contractCode':'ODAP','expiration':'2026-11-20','callOi':200}]}]}}
        with patch('v7_economy_state.synchronize'):
            finalize(feed)
        archive=feed['options']['dailySnapshots']
        self.assertEqual(archive['DAX:2026-11-20:ODAX'][0]['callOi'],100)
        self.assertEqual(archive['DAX:2026-11-20:ODAP'][0]['callOi'],200)
