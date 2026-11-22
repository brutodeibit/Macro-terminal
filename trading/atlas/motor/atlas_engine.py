#!/usr/bin/env python3
"""Estrategia Atlas: offline OHLCV event study & objective pattern observations.
No claims of executable P&L, orderflow, Volume Profile or fitted HMM.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, io, json, math, re, statistics
from collections import Counter, defaultdict
from bisect import bisect_left
from pathlib import Path

SCHEMA='estrategia-atlas-study-v1'
PERIODS=(1,5,20,63,126)

def num(raw):
    s=str(raw if raw is not None else '').strip().replace(',','.')
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',s):
        raise ValueError('Número inválido o separador ambiguo')
    return float(s)

def date_parse(raw):
    s=str(raw or '').strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',s):
        raise ValueError('Fecha de sesión diaria ISO AAAA-MM-DD requerida')
    return dt.date.fromisoformat(s)

def read_prices(path,instrument=None,*,source_bytes=None):
    raw=Path(path).read_bytes() if source_bytes is None else source_bytes
    contents=raw.decode('utf-8-sig')
    try:
        dialect=csv.Sniffer().sniff(contents.splitlines()[0],delimiters=',;\t')
    except (IndexError,csv.Error) as ex:
        raise ValueError('Cabecera CSV inválida') from ex
    reader=csv.DictReader(io.StringIO(contents,newline=''),dialect=dialect,strict=True)
    if not reader.fieldnames: raise ValueError('CSV sin cabecera')
    mapping={x.strip().lower():x for x in reader.fieldnames}
    if len(mapping)!=len(reader.fieldnames):raise ValueError('Cabeceras duplicadas')
    def key(*names):
        matches=[mapping[k] for k in names if k in mapping]
        if len(matches)>1:raise ValueError('Columnas ambiguas: '+', '.join(matches))
        return next(iter(matches),None)
    dk=key('date','time','datetime','timestamp'); ck=key('close','c')
    ok=key('open','o');hk=key('high','h');lk=key('low','l');vk=key('volume','vol','v')
    if not all((dk,ck,ok,hk,lk)):
        raise ValueError('Se requieren date/time, open, high, low, close; volumen opcional')
    rows=[]
    symbol_key=key('symbol','ticker','instrument','asset')
    contract_key=key('contract','contrato')
    symbols=set()
    contracts=set()
    for line,r in enumerate(reader,2):
        if None in r or any(v is None for v in r.values()):
            raise ValueError(f'Fila {line}: cantidad de columnas incompatible')
        for field,seen in ((symbol_key,symbols),(contract_key,contracts)):
            if field:
                value=r[field].strip().upper()
                if not value:raise ValueError(f'Fila {line}: identificador vacío')
                seen.add(value)
        try:
            d=date_parse(r[dk]);o=num(r[ok]);h=num(r[hk]);l=num(r[lk]);c=num(r[ck]);v=num(r[vk]) if vk and str(r[vk]).strip() else None
        except Exception as ex: raise ValueError(f'Fila {line}: fecha o número inválido: {ex}') from ex
        if not all(map(math.isfinite,(o,h,l,c))) or min(o,h,l,c)<=0 or h<max(o,l,c) or l>min(o,h,c):
            raise ValueError(f'Fila {line}: OHLC incoherentes')
        if v is not None and (not math.isfinite(v) or v<0):raise ValueError(f'Fila {line}: volumen negativo/inválido')
        rows.append(dict(date=d.isoformat(),open=o,high=h,low=l,close=c,volume=v))
    if len(symbols)>1 or len(contracts)>1:raise ValueError('CSV mezcla instrumentos o contratos')
    if symbols and instrument and instrument.strip().upper() not in symbols:
        raise ValueError('El ticker del CSV no coincide con --instrument')
    rows.sort(key=lambda r:r['date'])
    if len(rows)<35: raise ValueError('Se requieren 35 velas diarias como mínimo')
    if len({r['date'] for r in rows})!=len(rows):raise ValueError('Fechas duplicadas: una sola vela por sesión/día')
    gaps=[(rows[i-1]['date'],rows[i]['date'],(dt.date.fromisoformat(rows[i]['date'])-dt.date.fromisoformat(rows[i-1]['date'])).days) for i in range(1,len(rows))]
    wide=[x for x in gaps if x[2]>4]
    return rows,{'rows':len(rows),'first':rows[0]['date'],'last':rows[-1]['date'],'gaps_gt_4days':len(wide),'largest_gap_days':max((x[2] for x in gaps),default=0),'gap_examples':wide[:10],'volume_coverage':sum(x['volume'] is not None for x in rows)/len(rows)}

def stats(vals):
    a=[v for v in vals if v is not None and math.isfinite(v)]
    if not a:return {'n':0,'mean':None,'median':None,'positive':None,'min':None,'max':None,'stdev':None}
    return {'n':len(a),'mean':statistics.mean(a),'median':statistics.median(a),'positive':sum(v>0 for v in a)/len(a),'min':min(a),'max':max(a),'stdev':statistics.stdev(a) if len(a)>1 else None}

def outcome(rows,i,h,direction=1):
    if i+h>=len(rows):return None
    start=rows[i]['close']; ss=rows[i+1:i+h+1]
    closes=[r['close'] for r in ss]
    highs=[r['high'] for r in ss]; lows=[r['low'] for r in ss]
    signed=lambda p:direction*(p/start-1)*100
    # MAE/MFE from intraday high-low; no execution costs, no intra-bar path claim.
    path=[1+signed(p)/100 for p in [start,*closes]]
    peak=1
    drawdown=0
    for level in path:
        peak=max(peak,level)
        drawdown=max(drawdown,100*(1-level/peak))
    return {'return_pct':signed(closes[-1]),'mae_pct':min(0,signed(min(lows)),signed(max(highs))),
            'mfe_pct':max(0,signed(min(lows)),signed(max(highs))),
            'max_close_drawdown_pct':drawdown}

def seasonal(rows):
    per_month=defaultdict(list); per_week=defaultdict(list)
    month_end={}
    for r in rows:month_end[r['date'][:7]]=r
    keys=sorted(month_end)
    heatmap=[]
    for a,b in zip(keys,keys[1:]):
        # The final observed month can end mid-month. Still only candidates without an exchange calendar.
        if b==keys[-1] or any(int(month_end[k]['date'][8:])<25 for k in (a,b)):continue
        # A monthly return needs two adjacent calendar months, not merely consecutive observed months.
        yy,mm=map(int,a.split('-'))
        nextmonth=f'{yy+1}-01' if mm==12 else f'{yy}-{mm+1:02d}'
        if b!=nextmonth:continue
        rr=100*(month_end[b]['close']/month_end[a]['close']-1)
        item={'month':b,'anchor':month_end[a]['date'],'end':month_end[b]['date'],
              'calendar_verified':False,'return_pct':rr}
        heatmap.append(item);per_month[int(b[5:])].append(rr)
    for prev,cur in zip(rows,rows[1:]):
        gap=(dt.date.fromisoformat(cur['date'])-dt.date.fromisoformat(prev['date'])).days
        if gap>4:continue
        per_week[dt.date.fromisoformat(cur['date']).weekday()].append(100*(cur['close']/prev['close']-1))
    return {'heatmap':heatmap,'by_month':{str(k):stats(v) for k,v in sorted(per_month.items())},
            'by_weekday':{str(k):stats(v) for k,v in sorted(per_week.items())}}

def nth_weekday(y,m,weekday,n):
    start=dt.date(y,m,1)
    return start+dt.timedelta(days=(weekday-start.weekday())%7+7*(n-1))


def calendar_seasonality(rows, calendar_path, cut_date):
    """Study full calendar windows anchored at the previous scheduled close."""
    raw = Path(calendar_path).read_bytes()
    calendar = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(calendar, dict) or not {'source', 'first', 'last', 'sessions'} <= calendar.keys():
        raise ValueError('Calendario incompleto: requiere source, first, last y sessions')
    if not isinstance(calendar['sessions'], list):
        raise ValueError('sessions debe ser una lista de fechas ISO')
    source = calendar['source']
    if not isinstance(source, str) or not source.strip():
        raise ValueError('El calendario requiere una fuente identificable')
    first, last = (date_parse(calendar[k]) for k in ('first', 'last'))
    sessions = [date_parse(d) for d in calendar['sessions']]
    if not sessions or sessions != sorted(set(sessions)) or not first <= sessions[0] <= sessions[-1] <= last:
        raise ValueError('Calendario desordenado, duplicado, vacío o fuera de cobertura')
    prices = {date_parse(row['date']): row for row in rows}
    first_price, last_price = min(prices), max(prices)
    if first_price < first or last_price > last or prices.keys() - set(sessions):
        raise ValueError('Las fechas del histórico deben pertenecer al calendario declarado')
    cut = date_parse(cut_date)
    if not first_price < cut <= last_price:
        raise ValueError('El corte estacional debe dejar precios anteriores y posteriores')

    windows = []
    for year in range(first.year, last.year + 1):
        for month in range(1, 13):
            start = dt.date(year, month, 1)
            end = dt.date(year + (month == 12), month % 12 + 1, 1)
            windows.extend((kind, start + dt.timedelta(days=offset), stop)
                           for kind, offset, stop in (
                               ('monthly', 0, end),
                               ('days_1_7', 0, start + dt.timedelta(days=7)),
                               ('days_1_15', 0, start + dt.timedelta(days=15)),
                               ('days_16_end', 15, end)))
    monday = first - dt.timedelta(days=first.weekday())
    while monday <= last:
        end = monday + dt.timedelta(days=7)
        windows.append(('weekly', monday, end))
        monday = end
    for start in sessions:
        windows.append(('rolling_15_days', start, start + dt.timedelta(days=15)))

    observations = []
    excluded = Counter()
    for kind, start, end in sorted(windows, key=lambda w: (w[1], w[0])):
        if start < first or end - dt.timedelta(days=1) > last:
            continue
        i, j = bisect_left(sessions, start), bisect_left(sessions, end)
        if i == 0 or i == j or sessions[i-1] < first_price or sessions[j-1] > last_price:
            excluded['no_anchor_or_outside_prices'] += 1
            continue
        expected = sessions[i-1:j]
        if any(day not in prices for day in expected):
            excluded['missing_session'] += 1
            continue
        if sessions[i-1] < cut <= sessions[j-1]:
            excluded['crosses_cut'] += 1
            continue
        span = [prices[day] for day in expected]
        metrics = outcome(span, 0, len(span)-1)
        path = [row['close'] for row in span]
        peak = 0
        worst_peak = worst_trough = None
        worst = 0
        for offset, close in enumerate(path):
            if close > path[peak]:
                peak = offset
            drawdown = 1 - close / path[peak]
            if drawdown > worst:
                worst, worst_peak, worst_trough = drawdown, peak, offset
        recovered = next((k for k in range(worst_trough+1, len(path))
                          if path[k] >= path[worst_peak]), None) if worst_trough is not None else None
        high = max(range(1, len(span)), key=lambda k: span[k]['high'])
        low = min(range(1, len(span)), key=lambda k: span[k]['low'])
        context_days = sessions[max(0, i-21):i]
        trend = volatility = 'unknown'
        if len(context_days) == 21 and all(day in prices for day in context_days):
            prior = [prices[day]['close'] for day in context_days]
            change = prior[-1] / prior[0] - 1
            trend = 'up' if change > .02 else 'down' if change < -.02 else 'flat'
            vol = statistics.stdev(math.log(b) - math.log(a) for a,b in zip(prior, prior[1:])) * math.sqrt(252)
            volatility = 'high' if vol >= .20 else 'low'
        observations.append(dict(metrics, kind=kind, start=start.isoformat(),
                                 anchor=expected[0].isoformat(), end=expected[-1].isoformat(),
                                 split='reference' if expected[-1] < cut else 'out_of_sample',
                                 midterm=start.year % 4 == 2, trend=trend, volatility=volatility,
                                 sessions=j-i, high_session=high, low_session=low,
                                 drawdown_peak_session=worst_peak, drawdown_trough_session=worst_trough,
                                 recovery_session=recovered))

    groups = defaultdict(list)
    for item in observations:
        for dimension in ('all', 'month', 'midterm', 'month_midterm', 'trend', 'volatility'):
            value = item['start'][5:7] if dimension == 'month' else item.get(dimension, 'all')
            if dimension == 'month_midterm':
                value = item['start'][5:7] + ('/midterm' if item['midterm'] else '/other')
            groups[item['kind'], item['split'], dimension, value].append(item)
    fields = ('return_pct', 'mae_pct', 'mfe_pct', 'max_close_drawdown_pct', 'sessions',
              'high_session', 'low_session', 'drawdown_peak_session', 'drawdown_trough_session',
              'recovery_session')
    def summarize(items, field):
        values = [item[field] for item in items if item[field] is not None]
        result = stats(values)
        result['decil_10'], result['decil_90'] = (
            statistics.quantiles(values, n=10, method='inclusive')[::8]
            if len(values) > 1 else (values[0], values[0]) if values else (None, None))
        return result

    return dict(protocol='atlas-calendar-seasonality-v1', cutoff=cut.isoformat(),
                calendar_source=source, calendar_sha256=hashlib.sha256(raw).hexdigest(),
                excluded=dict(excluded), observations=observations,
                summaries=[dict(kind=kind, split=split, dimension=axis, value=value,
                                metrics={field:summarize(items, field) for field in fields})
                           for (kind,split,axis,value),items in groups.items()])

def event_date(y,typ):
    if typ=='columbus':return nth_weekday(y,10,0,2)
    if typ=='veterans':return dt.date(y,11,11) # Actual date, not banking observed date for an exchange-open test
    if typ=='thanksgiving':return nth_weekday(y,11,3,4)
    if typ in ('midterms','presidential') and y%4==(2 if typ=='midterms' else 0):
        return nth_weekday(y,11,0,1)+dt.timedelta(days=1)
    return None

def event_study(rows,market):
    out={}; dates=[x['date'] for x in rows]
    for typ in ('columbus','veterans','thanksgiving','midterms','presidential'):
        obs=[]
        for y in range(int(dates[0][:4]),int(dates[-1][:4])+1):
            ed=event_date(y,typ)
            if ed is None:continue
            event=ed.isoformat()
            if not dates[0]<=event<=dates[-1]:continue
            # Explicit exchange caveat: for NYSE, thanksgiving is closed and other 2 holidays are open.
            if market=='us_equity':
                if typ=='veterans' and ed.weekday()>=5:continue
                expected_open=typ!='thanksgiving'
                exact=event in dates
                if expected_open and not exact:continue
                if not expected_open and exact:continue
            idx=next((i for i,d in enumerate(dates) if d>event),len(dates))-1
            if idx<20 or idx>=len(rows):continue
            gap=(ed-dt.date.fromisoformat(dates[idx])).days
            if gap>4:continue
            r={'event':typ,'date':event,'anchor':dates[idx], 'pre5_pct':(rows[idx]['close']/rows[idx-5]['close']-1)*100,
               'pre20_pct':(rows[idx]['close']/rows[idx-20]['close']-1)*100}
            for h in PERIODS:r[f'plus{h}']=outcome(rows,idx,h)
            obs.append(r)
        out[typ]={'observations':obs,'summary':{str(h):stats([(x[f'plus{h}'] or {}).get('return_pct') for x in obs]) for h in PERIODS}}
    return out

def indicators(rows,i,lookback=20):
    if i<lookback:return None
    hist=rows[i-lookback:i]
    lo=min(v['low'] for v in hist); hi=max(v['high'] for v in hist)
    r=rows[i];close=r['close'];width=hi-lo
    # These are *mechanical proxies*, not discretionary Wyckoff/VP verification.
    return {
      'spring_proxy':r['low']<lo and close>lo and close<=hi,
      'upthrust_proxy':r['high']>hi and close<hi and close>=lo,
      'breakout_up':close>hi,
      'breakout_down':close<lo,
      'range_20':width>0 and (width/rows[i-lookback]['close'])<.06,
      'ath_rolling_252':i>=252 and close>max(z['high'] for z in rows[i-252:i]),
      'new_20_low':r['low']<lo,
    }

def pattern_study(rows,lookback=20):
    types=('spring_proxy','upthrust_proxy','breakout_up','breakout_down','range_20','ath_rolling_252','new_20_low')
    dirs={'spring_proxy':1,'upthrust_proxy':-1,'breakout_up':1,'breakout_down':-1,'range_20':1,'ath_rolling_252':1,'new_20_low':-1}
    signals=[]
    for i in range(lookback,len(rows)):
        flags=indicators(rows,i,lookback)
        for typ in types:
            if not flags[typ]:continue
            rec={'signal_id':f'{typ}:{rows[i]["date"]}','date':rows[i]['date'],'pattern':typ,'direction':dirs[typ],
                 'observation_only':True,'context_range20':flags['range_20']}
            for h in (5,20):rec[f'plus{h}']=outcome(rows,i,h,dirs[typ])
            signals.append(rec)
    aggregate={}
    for typ in types:
        matching=[s for s in signals if s['pattern']==typ]
        aggregate[typ]={'signals':len(matching),'forward5':stats([(s['plus5'] or {}).get('return_pct') for s in matching]),
                        'forward20':stats([(s['plus20'] or {}).get('return_pct') for s in matching]),
                        'mae20':stats([(s['plus20'] or {}).get('mae_pct') for s in matching]),
                        'mfe20':stats([(s['plus20'] or {}).get('mfe_pct') for s in matching])}
    # baseline unconditional all bars for 5 and 20 day forward returns, same sample start.
    baseline={str(h):stats([(outcome(rows,i,h) or {}).get('return_pct') for i in range(lookback,len(rows))]) for h in (5,20)}
    return {'definitions':{'spring_proxy':'Bar low below previous 20 lows, close back above boundary and below range high',
                            'upthrust_proxy':'Bar high above previous 20 highs, close back below boundary and above range low',
                            'breakout_up':'Close above prior 20-bar high', 'breakout_down':'Close below prior 20-bar low',
                            'range_20':'Previous 20-bar high-low width <6% of first prior close, no forward signal',
                            'ath_rolling_252':'Close above prior 252-bar high; 52-week proxy, not all-time high',
                            'new_20_low':'Intrabar low below previous 20 lows; not necessarily a short signal'},
            'summary':aggregate,'baseline_long':baseline,'signals':signals}

def backtest(rows, test_from, cost_bps):
    """Fixed 20-bar breakout, one position, no parameter selection."""
    cut=date_parse(test_from).isoformat()
    if not math.isfinite(cost_bps) or not 0<=cost_bps<10000:
        raise ValueError('Coste total en puntos básicos fuera de rango')
    split=next((i for i,r in enumerate(rows) if r['date']>=cut),len(rows))
    if split<26 or len(rows)-split<6:
        raise ValueError('Corte requiere 26 velas anteriores y 6 desde el corte')

    def run(start,end,baseline=False):
        trades=[]
        skipped_gaps=0
        i=max(20,start)
        while i+5<end:
            flags=indicators(rows,i)
            direction=1 if baseline or flags['breakout_up'] else -1 if flags['breakout_down'] else 0
            if not direction:
                i+=1
                continue
            dates=[date_parse(r['date']) for r in rows[i-20:i+6]]
            if any((b-a).days>4 for a,b in zip(dates,dates[1:])):
                skipped_gaps+=1
                i+=1
                continue
            entry=rows[i+1]['open']
            exit_price=rows[i+5]['close']
            net_pct=direction*(exit_price/entry-1)*100-cost_bps/100
            trades.append(dict(signal_date=rows[i]['date'],entry_date=rows[i+1]['date'],
                               exit_date=rows[i+5]['date'],entry=entry,exit=exit_price,
                               direction=direction,net_pct=net_pct))
            i+=5  # Today's close can produce a signal for tomorrow's open.
        return dict(summary=stats([t['net_pct'] for t in trades]),trades=trades,
                    skipped_gap_signals=skipped_gaps)

    return {'protocol':'breakout20-next-open-hold5-v1','test_from':cut,'round_trip_bps':cost_bps,
            'reference':{'strategy':run(0,split),'baseline_long':run(0,split,True)},
            'out_of_sample':{'strategy':run(split,len(rows)),'baseline_long':run(split,len(rows),True)}}

def analyze(csv_path,market,instrument,*,test_from=None,cost_bps=None,synthetic=False,
            session_calendar=None, seasonality_test_from=None):
    raw=Path(csv_path).read_bytes()
    rows,quality=read_prices(csv_path,instrument,source_bytes=raw)
    sha=hashlib.sha256(raw).hexdigest()
    warnings=['Datos suministrados por el usuario; sin verificación externa de mercado, ajuste, rollovers, horario ni splits.',
              'Resultados de patrones son movimientos posteriores al cierre de señal, no trades ejecutables. Sin spreads, slippage ni comisiones.',
              'HMM existente: diagnóstico aproximado, NO modelo entrenado/validado aquí. Volume Profile/footprint no inferibles de OHLCV diario.']
    if quality['gaps_gt_4days']:warnings.append('Existen discontinuidades; comprobar suspensiones/cierres y ventanas de estudio.')
    if market!='us_equity':warnings.append('Fechas de eventos EEUU referenciales; calendario de negociación del instrumento NO verificado.')
    report={'schema':SCHEMA,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'provenance':{'instrument':instrument,
             'market':market,'source_file':Path(csv_path).name,'source_sha256':sha,'frequency':'1D','adjustments':'unknown','currency':'unknown',
             'data_class':'synthetic' if synthetic or 'SINTETIC' in Path(csv_path).name.upper() else 'user_supplied_unverified',
             'engine_revision':'1.3.1',
             'price_unit':'source','time_zone':'unknown','asof':quality['last']},'quality':quality,'warnings':warnings,
            'seasonality':seasonal(rows),'events':event_study(rows,market),'patterns':pattern_study(rows)}
    if (test_from is None)!=(cost_bps is None):
        raise ValueError('Indica conjuntamente fecha de corte y coste total')
    if test_from is not None:
        report['backtest']=backtest(rows,test_from,cost_bps)
    if bool(session_calendar) != bool(seasonality_test_from):
        raise ValueError('Indica conjuntamente calendario y corte estacional')
    if session_calendar:
        report['calendar_seasonality'] = calendar_seasonality(rows, session_calendar, seasonality_test_from)
    return report

def make_contract(journal_path):
    path=Path(journal_path)
    raw=path.read_bytes()
    data=json.loads(raw.decode('utf-8-sig'))
    if isinstance(data,dict) and data.get('version') in (1,2) and 'trades' in data:
        from journal_exchange import from_journal
        return dict(from_journal(data), provenance={'source_file':path.name,
                                                   'source_sha256':hashlib.sha256(raw).hexdigest()})
    if data.get('schema')!='trading-atlas-journal-v1' or not isinstance(data.get('records'),list):
        raise ValueError('Solo copias journal v1 JSON; no se importa automáticamente un CSV de broker')
    result=[];seen=set()
    for rec in data['records']:
        tid=rec['id']
        if not isinstance(tid,str) or not tid.strip():raise ValueError('ID de Atlas inválido')
        if tid in seen:raise ValueError('trade_id duplicado')
        seen.add(tid)
        legs=[]
        for j,l in enumerate(rec.get('legs') or []):
            legs.append({'leg_id':f'{tid}:leg:{j+1}','kind':'entry' if j==0 else 'reentry','executed_at':l.get('date'),
                         'entry':l.get('entry'),'stop_initial':l.get('stop'),'exit':l.get('exit'),
                         'quantity':l.get('qty'),'cost_allocated':None})
        result.append({'trade_id':tid,'signal_id':rec.get('signal_id') or tid,'strategy_id':rec.get('strategy') or 'UNASSIGNED',
           'setup_id':rec.get('setup') or 'UNASSIGNED','asset':rec.get('asset'), 'source':rec.get('source'),
           'direction':rec.get('direction'),'status':rec.get('status'),'state':rec.get('state'),
           'market':None,'instrument':rec.get('asset'),'session_timezone':None,'currency':rec.get('currency'),
           'multiplier':rec.get('mult'),'parent_total_cost':rec.get('costs',0),
           'provenance':{'origin':'EstrategiaAtlas_local_import','asof':rec.get('updatedAt'),'execution_type':'manual_or_simulated'},
           'legs':legs})
    return {'schema':'atlas-journal-exchange-v1','records':result,'limitations':[
       'No confirmation of actual broker executions; status=operada is self-reported.',
       'One exit price per leg. Partial exits and actual order fills not supported.',
       'Costs are held at parent level ONLY to avoid double-counting.',
       'Do not merge by date/ticker: use trade_id and leg_id for deduplication.',
       'Market, timezone and provenance missing are explicitly null.']}


def management_report(prices, instrument, case_path, calendar_path, synthetic=False):
    from management_study import simulate_management

    raw = Path(prices).read_bytes()
    rows, _ = read_prices(prices, instrument, source_bytes=raw)
    case_raw = Path(case_path).read_bytes()
    case = json.loads(case_raw.decode('utf-8-sig'))
    calendar_raw = Path(calendar_path).read_bytes()
    calendar = json.loads(calendar_raw.decode('utf-8-sig'))
    start, end = (date_parse(case[k]).isoformat() for k in ('start','end'))
    first, last = (date_parse(calendar[k]).isoformat() for k in ('first','last'))
    sessions = [date_parse(d).isoformat() for d in calendar['sessions']]
    if (not isinstance(calendar['source'], str) or not calendar['source'].strip()
            or not first <= start <= end <= last or sessions != sorted(set(sessions))):
        raise ValueError('Calendario inválido o fuera de cobertura')
    bars = [r for r in rows if start <= r['date'] <= end]
    expected = [d for d in sessions if start <= d <= end]
    if not bars or end > rows[-1]['date'] or bars[0]['date'] != start or [r['date'] for r in bars] != expected:
        raise ValueError('Faltan sesiones o la entrada no coincide con la apertura de una sesión')
    costs = case.get('cost_bps')
    if costs is not None:
        if not isinstance(costs, dict) or costs.keys() != {'commissions','spread','slippage'}:
            raise ValueError('Desglosa comisiones, spread y deslizamiento en puntos básicos')
        if any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or v<0
               for v in costs.values()):
            raise ValueError('Componente de costes inválido')
    result = simulate_management(bars, case['direction'], float(case['stop']), float(case['target']),
                                 sum(costs.values()) if costs is not None else None)
    return dict(schema='atlas-management-simulation-v1', instrument=instrument,
                origin='synthetic' if synthetic else 'user_supplied_daily',
                prices_sha256=hashlib.sha256(raw).hexdigest(), case_sha256=hashlib.sha256(case_raw).hexdigest(),
                calendar_sha256=hashlib.sha256(calendar_raw).hexdigest(), calendar_source=calendar['source'],
                cost_components_bps=costs, simulation=result)

def main(argv=None):
    ap=argparse.ArgumentParser(description='Estrategia Atlas offline engine')
    ap.add_argument('--prices',help='CSV daily OHLCV')
    ap.add_argument('--market',choices=('us_equity','other'),default='other')
    ap.add_argument('--instrument',help='Symbol of ONLY one market instrument')
    ap.add_argument('--journal',help='Copia JSON de Trading Journal o del registro Atlas')
    ap.add_argument('--test-from',help='Fecha de inicio fuera de muestra (ISO)')
    ap.add_argument('--cost-bps',type=float,help='Coste total ida y vuelta en puntos básicos, explícito')
    ap.add_argument('--synthetic',action='store_true',help='Identifica datos sintéticos')
    ap.add_argument('--session-calendar',help='JSON con fuente y calendario de sesiones del instrumento')
    ap.add_argument('--management-case',help='JSON con fechas, dirección, stop y objetivo del caso simulado')
    ap.add_argument('--seasonality-test-from',help='Corte ISO para el estudio estacional')
    ap.add_argument('--output',required=True,help='JSON result path')
    a=ap.parse_args(argv)
    if bool(a.prices)==bool(a.journal):ap.error('Elige --prices o --journal')
    if a.prices and not a.instrument:ap.error('--instrument requerido para CSV')
    if a.journal and (a.test_from is not None or a.cost_bps is not None or a.synthetic
                      or a.session_calendar or a.seasonality_test_from or a.management_case):
        ap.error('Las opciones de backtest requieren --prices')
    if Path(a.output).resolve()==Path(a.prices or a.journal).resolve():
        ap.error('La salida debe ser distinta del archivo de entrada')
    if a.session_calendar and Path(a.output).resolve()==Path(a.session_calendar).resolve():
        ap.error('La salida debe ser distinta del calendario')
    if a.management_case:
        if not a.session_calendar or a.seasonality_test_from or a.test_from or a.cost_bps is not None:
            ap.error('El caso de gestión usa calendario y sus propios costes, sin opciones de otros estudios')
        if Path(a.output).resolve()==Path(a.management_case).resolve():
            ap.error('La salida debe ser distinta del caso de gestión')
        obj=management_report(a.prices,a.instrument,a.management_case,a.session_calendar,synthetic=a.synthetic)
    else:
        obj=analyze(a.prices,a.market,a.instrument,test_from=a.test_from,cost_bps=a.cost_bps,
                synthetic=a.synthetic,session_calendar=a.session_calendar,
                seasonality_test_from=a.seasonality_test_from) if a.prices else make_contract(a.journal)
    Path(a.output).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'schema':obj['schema'],'saved':str(a.output),'observations':obj.get('quality',{}).get('rows'),'records':len(obj.get('records',[]))},ensure_ascii=False))
if __name__=='__main__':main()
