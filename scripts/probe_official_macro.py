"""Inspect small official API responses; no feed writes."""
import json
from pathlib import Path
import requests
out = Path('.test-tmp/europe-sources')
out.mkdir(parents=True, exist_ok=True)
queries = {
    'hicp': ('prc_hicp_minr', {'geo':'EA21','unit':'RCH_A','lastTimePeriod':'3'}),
    'gdp': ('namq_10_gdp', {'geo':'EA21','unit':'CLV_PCH_PRE','s_adj':'SCA','na_item':'B1GQ','lastTimePeriod':'3'}),
    'unemployment': ('une_rt_m', {'geo':'EA21','unit':'PC_ACT','s_adj':'SA','sex':'T','lastTimePeriod':'3'}),
}
for name, (dataset, params) in queries.items():
    try:
        r = requests.get('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'+dataset,
                         params={'lang':'en', **params}, timeout=25)
        r.raise_for_status()
        data = r.json()
        (out/(name+'.json')).write_text(json.dumps(data), encoding='utf-8')
        print(name, json.dumps({k:data.get(k) for k in ('updated','id','size','error')}))
        for key, dim in data.get('dimension', {}).items():
            labels = dim['category'].get('label', {})
            print(key, {k:v for k,v in labels.items() if len(labels)<10 or 'excl' in v.lower() or 'all-items' in v.lower()})
    except Exception as exc:
        print(name, type(exc).__name__, str(exc)[:160])
try:
    r = requests.get('https://mfs.deutsche-boerse.com/app.js', timeout=20)
    r.raise_for_status()
    (out/'db-app.js').write_text(r.text, encoding='utf-8')
    print('DB app bytes',len(r.content))
except Exception as exc:
    print('DB app',type(exc).__name__)
