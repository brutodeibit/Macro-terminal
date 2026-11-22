"""Bounded public-source inspection; writes samples locally, never the live feed."""
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bs4 import BeautifulSoup
import requests
from v7_eurex import PRODUCTS

out = Path('.test-tmp/europe-sources')
out.mkdir(parents=True, exist_ok=True)
session = requests.Session()
session.headers['User-Agent'] = 'MacroMonitor personal source validation'
page = PRODUCTS['SX5E'][1]
response = session.get(page, timeout=25)
response.raise_for_status()
soup = BeautifulSoup(response.text, 'html.parser')
config = next(json.loads(tag.string or tag.get_text()) for tag in soup.find_all('script', attrs={'data-product': True})
              if json.loads(tag.string or tag.get_text()).get('busDate'))
url = 'https://www.eurex.com/api/v1/overallstatistics/' + config['productId']
overview = session.get(url, params={'busdate': config['busDate'], 'filtertype': 'overview'}, timeout=25).json()
expiry = next(row for row in overview['dataRows'] if row['date'] > config['busDate'])
detail = session.get(url, params={'busdate': config['busDate'], 'filtertype': 'detail',
                    'productdate': expiry['date'], 'contracttype': expiry['contractType']}, timeout=25).json()
(out/'oesx.json').write_text(json.dumps({'config': config, 'overview': overview, 'expiry': expiry, 'detail': detail}, ensure_ascii=False), encoding='utf-8')
print('EUREX', json.dumps({'date': config['busDate'], 'expiry': expiry, 'meta': detail.get('meta'),
                        'header': detail.get('header'), 'call': detail.get('dataRowsCall', [])[:2],
                        'put': detail.get('dataRowsPut', [])[:2]}, ensure_ascii=True))
apa = 'https://www.cboe.com/europe/equities/trade_data/'
response = session.get(apa, timeout=25)
print('APA INDEX', response.status_code)
if response.ok:
    soup = BeautifulSoup(response.text, 'html.parser')
    links = sorted({urljoin(apa, a['href']) for a in soup.find_all('a', href=True)
                    if re.search(r'apa_\d{4}-\d{2}-\d{2}_\d{4}\.csv$', a['href'])}, reverse=True)
    if links:
        with session.get(links[0], timeout=25, stream=True) as data:
            sample = data.raw.read(1024*1024, decode_content=True)
            (out/'apa-sample.csv').write_bytes(sample)
            print('APA CSV', data.status_code, links[0], 'sampleBytes', len(sample),
                  'lines', sample.decode('utf-8-sig', errors='replace').splitlines()[:3])
    else:
        print('APA no minute links', [a['href'] for a in soup.find_all('a', href=True) if '.csv' in a['href']][:3])
try:
    response = session.post('https://api.finra.org/partitions/group/otcMarket/name/weeklySummary', json={}, timeout=20)
    print('FINRA WITHOUT TOKEN', response.status_code)
except requests.RequestException as exc:
    print('FINRA', type(exc).__name__)
