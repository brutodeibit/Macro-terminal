"""Local source refresh service. No GitHub token or browser credentials required."""
import argparse
import copy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'options': ['SQUAWK', 'OPTIONS', 'EUREX'],
    'dark': ['DARK_POOLS', 'DARK_PRINTS', 'INFOLIB_PRINTS', 'OHLC'],
    'macro': ['MEETINGS', 'MACRO', 'ECONOMIC_CALENDAR', 'RELEASE_CALENDAR',
              'FX', 'RISK', 'TREASURY', 'CURVES', 'CANADA_CURVE', 'ECB_CURVE',
              'CANADA_LONG_CURVE', 'JAPAN_CURVE', 'AUSTRALIA_CURVE',
              'SWISS_CURVE', 'GERMANY_CURVE'],
}
ASSETS = {'index.html', 'claude-preview.html', 'design-preview-v2.html',
          'design-preview-v2.js', 'design-preview-v2.css', 'v7-ui.js',
          'source-refresh.js', 'macro-feed-v7.json', 'macro-feed.json',
          'data/cot-feed.json', 'statistical-monitor.html', 'stats-feed.json'}


def utc():
    return datetime.now(timezone.utc).isoformat()


class RefreshManager:
    def __init__(self, root=ROOT, runner=None, cooldown=900):
        self.root, self.runner, self.cooldown = Path(root), runner, cooldown
        self.lock = threading.Lock()
        self.job = None
        self.last_started = {}

    def status(self):
        with self.lock:
            return copy.deepcopy(self.job)

    def start(self, group):
        if group not in GROUPS:
            return 400, {'error': 'Grupo de fuentes desconocido.'}
        with self.lock:
            if self.job and self.job['state'] == 'running':
                return 202, copy.deepcopy(self.job)
            remaining = self.cooldown - (time.monotonic() - self.last_started.get(group, -1e10))
            if remaining > 0:
                return 429, {'error': 'Espera antes de repetir la consulta de estas fuentes.',
                             'retryAfter': round(remaining) + 1}
            self.last_started[group] = time.monotonic()
            self.job = {'id': uuid.uuid4().hex, 'group': group, 'state': 'running',
                        'startedAt': utc(), 'sources': GROUPS[group], 'progress': []}
            result = copy.deepcopy(self.job)
        threading.Thread(target=self._run, args=(group,), daemon=True).start()
        return 202, result

    def _run(self, group):
        try:
            with tempfile.TemporaryDirectory(prefix='macro-refresh-') as tmp:
                work = Path(tmp)
                for pattern in ('*.py', 'v7-*.json'):
                    for src in self.root.glob(pattern):
                        shutil.copy2(src, work / src.name)
                shutil.copy2(self.root / 'macro-feed-v7.json', work / 'macro-feed-v7.json')
                if self.runner:
                    self.runner(work, GROUPS[group], self._progress)
                else:
                    self._collect(work, GROUPS[group])
                output = work / 'macro-feed-v7.json'
                feed = json.loads(output.read_text(encoding='utf-8'))
                if not isinstance(feed.get('economies'), dict) or not feed['economies']:
                    raise ValueError('La consulta no produjo un feed válido; se conserva la copia anterior.')
                # No partially collected snapshots are exposed while a job is running.
                pending = self.root / 'macro-feed-v7.refresh.tmp'
                shutil.copyfile(output, pending)
                os.replace(pending, self.root / 'macro-feed-v7.json')
                health = {key: feed.get('sourceHealth', {}).get(key, {}) for key in GROUPS[group]}
                with self.lock:
                    self.job.update(state='completed', finishedAt=utc(),
                                    generatedAt=feed.get('generatedAt'), health=health)
        except Exception as exc:
            with self.lock:
                self.job.update(state='failed', finishedAt=utc(),
                                error=str(exc)[:240])

    def _progress(self, line):
        # Updater status lines only, never provider responses, tokens or URLs.
        words = line.strip().split()
        if len(words) == 2 and words[0] in {s for values in GROUPS.values() for s in values}:
            if words[1] in {'processed', 'unchanged_or_unavailable', 'retained'}:
                with self.lock:
                    self.job['progress'].append({'source': words[0], 'status': words[1]})

    def _collect(self, work, sources):
        command = [sys.executable, '-u', str(work / 'update_preview.py'), '--force', '--sources', *sources]
        with subprocess.Popen(command, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding='utf-8', errors='replace') as proc:
            timer = threading.Timer(1800, proc.kill)
            timer.start()
            try:
                for line in proc.stdout:
                    self._progress(line)
                if proc.wait() != 0:
                    raise RuntimeError('La consulta no terminó. Se conserva la copia anterior. Comprueba las dependencias y la conexión.')
            finally:
                timer.cancel()


def handler(manager, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def allowed(self):
            return (self.headers.get('Host') in {f'localhost:{port}', f'127.0.0.1:{port}'}
                    and self.headers.get('Origin') in {None, f'http://localhost:{port}',
                        f'http://127.0.0.1:{port}', 'http://127.0.0.1:8765',
                        'http://localhost:8765', 'https://brutodeibit.github.io'})

        def headers_for(self, code, mime='application/json'):
            self.send_response(code)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            origin = self.headers.get('Origin')
            if origin:
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
            self.end_headers()

        def reply(self, code, body):
            self.headers_for(code)
            self.wfile.write(json.dumps(body, ensure_ascii=False).encode('utf-8'))

        def do_OPTIONS(self):
            if not self.allowed():
                self.send_error(403)
                return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', ''))
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Macro-Refresh')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()

        def do_GET(self):
            if not self.allowed():
                self.send_error(403)
                return
            name = urlsplit(self.path).path
            if name == '/api/refresh':
                self.reply(200, {'service': 'macro-source-refresh-v1', 'job': manager.status()})
                return
            name = name.lstrip('/') or 'index.html'
            if name not in ASSETS:
                self.send_error(404)
                return
            file = manager.root / name
            if not file.is_file():
                self.send_error(404)
                return
            mime = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css'}.get(file.suffix, 'application/json')
            self.headers_for(200, mime)
            self.wfile.write(file.read_bytes())

        def do_POST(self):
            if not self.allowed() or self.headers.get('X-Macro-Refresh') != '1':
                self.send_error(403)
                return
            if urlsplit(self.path).path != '/api/refresh':
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 512:
                    raise ValueError()
                if self.headers.get_content_type() != 'application/json':
                    raise ValueError()
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError()
                code, result = manager.start(body.get('group'))
                self.reply(code, result)
            except (ValueError, TypeError):
                self.reply(400, {'error': 'Solicitud no válida.'})
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(RefreshManager(), args.port))
    print(f'Macro Monitor: http://127.0.0.1:{args.port}/', flush=True)
    server.serve_forever()
