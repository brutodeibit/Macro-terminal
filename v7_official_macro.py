"""Small Eurostat queries: reference period and dataset update are distinct dates."""
from datetime import datetime, timezone
import math
from urllib.parse import urlencode

BASE = 'https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'
SERIES = [
    ('hicp', 'prc_hicp_minr', {'unit':'RCH_A'}, {'coicop18':'TOTAL'}, 'INFLACIÓN', 'IPC armonizado general', '% interanual'),
    ('hicp_core', 'prc_hicp_minr', {'unit':'RCH_A'}, {'coicop18':'TOT_X_NRG_FOOD'}, 'INFLACIÓN', 'IPC Subyacente', '% interanual'),
    ('gdp', 'namq_10_gdp', {'unit':'CLV_PCH_PRE','s_adj':'SCA','na_item':'B1GQ'}, {}, 'CRECIMIENTO', 'PIB (Trimestral)', '% trimestral, ajustado'),
    ('unemployment', 'une_rt_m', {'unit':'PC_ACT','s_adj':'SA','sex':'T','age':'TOTAL'}, {}, 'EMPLEO', 'Tasa de Desempleo', '% población activa, ajustado'),
]


def observations(payload, selection):
    ids, sizes = payload.get('id', []), payload.get('size', [])
    if not ids or len(ids) != len(sizes) or 'time' not in ids:
        raise ValueError('Invalid JSON-stat dimensions')
    fixed = {}
    for key, size in zip(ids, sizes):
        category = payload['dimension'][key]['category']['index']
        index = category if isinstance(category, dict) else {v:i for i,v in enumerate(category)}
        if key == 'time':
            times = index
        elif key in selection:
            if selection[key] not in index:
                raise ValueError('Requested series missing: ' + key)
            fixed[key] = index[selection[key]]
        elif size == 1:
            fixed[key] = 0
        else:
            raise ValueError('Ambiguous unfiltered dimension: ' + key)
    values, statuses = payload.get('value') or {}, payload.get('status') or {}
    def cell(container, i):
        return container.get(str(i)) if isinstance(container, dict) else container[i] if i < len(container) else None
    result = []
    for period, pos in sorted(times.items()):
        offset = 0
        for key, size in zip(ids, sizes):
            offset = offset * size + (pos if key == 'time' else fixed[key])
        value = cell(values, offset)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            result.append({'referencePeriod': period, 'value': value, 'status': cell(statuses, offset)})
    if not result:
        raise ValueError('No finite observations in the selected series')
    return result[-3:]


def update(feed, get):
    now = datetime.now(timezone.utc).isoformat()
    cache = {}
    warnings = feed.setdefault('sourceWarnings', {})
    for eid, geo, label in [('eu','EA21','Eurozona'), ('de','DE','Alemania')]:
        economy = feed.get('economies', {}).get(eid)
        if economy is None:
            continue
        for code, dataset, filters, selection, category, title, unit in SERIES:
            key = 'EUROSTAT_' + eid + '_' + code
            params = {'lang':'en', 'geo':geo, 'lastTimePeriod':'3', **filters}
            url = BASE + dataset + '?' + urlencode(params)
            try:
                if url not in cache:
                    cache[url] = get(url).json()
                payload = cache[url]
                if payload.get('error'):
                    raise ValueError('Eurostat returned a dataset error')
                history = observations(payload, {'geo':geo, **filters, **selection})
                name = title + ' ' + label if code in ('hicp','hicp_core') else \
                    'PIB ' + label + ' (Trimestral)' if code == 'gdp' else title
                latest = history[-1]
                row = {'id':'eurostat:'+eid+':'+code, 'name':name, 'cat':category,
                       'actual':str(latest['value'])+'%', 'actualValue':latest['value'],
                       'est':None, 'surprise':None, 'consensusStatus':'unavailable',
                       'previous':history[-2]['value'] if len(history)>1 else None,
                       'referencePeriod':latest['referencePeriod'], 'unit':unit,
                       'date':None, 'publishedAt':None, 'dateBasis':'reference_period_only',
                       'datasetUpdatedAt':payload.get('updated'), 'fetchedAt':now,
                       'source':'Eurostat · '+geo, 'sourceUrl':url, 'dataset':dataset,
                       'geo':geo, 'dataStatus':'OFFICIAL · latest available; no consensus or release timestamp supplied',
                       'observations':history, 'imp':'★★★'}
                indicators = economy.setdefault('indicators', [])
                old = next((i for i in indicators if i.get('id') == row['id'] or i.get('name') == name), None)
                if old:
                    indicators[indicators.index(old)] = row
                else:
                    indicators.append(row)
                warnings.pop(key, None)
            except Exception as exc:
                warnings[key] = str(exc)[:180]
                for row in economy.get('indicators', []):
                    if row.get('id') == 'eurostat:'+eid+':'+code:
                        row['dataStatus'] = 'STALE · last valid official observation retained'
                        row['lastAttemptAt'] = now
