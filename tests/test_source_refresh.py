import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from scripts.source_refresh_server import RefreshManager
from scripts.source_refresh_server import handler
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class SourceRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.feed = self.root / 'macro-feed-v7.json'
        self.feed.write_text(json.dumps({'economies': {'us': {}}, 'generatedAt': 'original'}))

    def finish(self, manager):
        deadline = time.monotonic() + 5
        while manager.status()['state'] == 'running' and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertNotEqual(manager.status()['state'], 'running')

    def test_single_job_and_atomic_publication(self):
        entered, release = threading.Event(), threading.Event()
        def runner(work, sources, progress):
            (work / self.feed.name).write_text('{partial')
            entered.set()
            release.wait(3)
            (work / self.feed.name).write_text(json.dumps({'economies': {'us': {}}, 'generatedAt': 'new'}))
            progress('OPTIONS processed')
        manager = RefreshManager(self.root, runner)
        code, job = manager.start('options')
        self.assertEqual(code, 202)
        self.assertTrue(entered.wait(2))
        self.assertEqual(json.loads(self.feed.read_text())['generatedAt'], 'original')
        self.assertEqual(manager.start('dark')[1]['id'], job['id'])
        release.set()
        self.finish(manager)
        self.assertEqual(json.loads(self.feed.read_text())['generatedAt'], 'new')
        self.assertEqual(manager.status()['progress'], [{'source': 'OPTIONS', 'status': 'processed'}])
        self.assertEqual(manager.start('options')[0], 429)

    def test_failed_collection_preserves_previous_snapshot(self):
        def runner(work, *_):
            (work / self.feed.name).write_text('{invalid')
            raise RuntimeError('Network unavailable')
        manager = RefreshManager(self.root, runner)
        manager.start('macro')
        self.finish(manager)
        self.assertEqual(manager.status()['state'], 'failed')
        self.assertEqual(json.loads(self.feed.read_text())['generatedAt'], 'original')

    def test_invalid_output_is_not_published(self):
        def runner(work, *_):
            (work / self.feed.name).write_text('{}')
        manager = RefreshManager(self.root, runner)
        manager.start('dark')
        self.finish(manager)
        self.assertEqual(manager.status()['state'], 'failed')
        self.assertEqual(json.loads(self.feed.read_text())['generatedAt'], 'original')
        self.assertEqual(manager.start('unknown')[0], 400)

    def test_http_rejects_untrusted_origin_and_missing_header(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(RefreshManager(self.root), 0))
        server.RequestHandlerClass = handler(RefreshManager(self.root), server.server_port)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/api/refresh'
            with urlopen(url) as response:
                self.assertEqual(json.load(response)['service'], 'macro-source-refresh-v1')
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url, headers={'Origin': 'https://untrusted.example'}))
            self.assertEqual(error.exception.code, 403)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url, data=b'{}', headers={'Content-Type': 'application/json'}))
            self.assertEqual(error.exception.code, 403)
            request = Request(url, data=b'{"group":"unknown"}', headers={
                'Content-Type': 'application/json', 'X-Macro-Refresh': '1',
                'Origin': 'https://brutodeibit.github.io'})
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 400)
            self.assertEqual(error.exception.headers['Access-Control-Allow-Origin'], 'https://brutodeibit.github.io')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
