"""OHLC timeframes; 4h bars aggregate observations within exchange sessions."""
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def candles_from_series(series):
    q=(series.get('indicators',{}).get('quote') or [{}])[0]
    out=[]
    for i,ts in enumerate(series.get('timestamp',[])):
        values={k:q.get(k,[])[i] if i<len(q.get(k,[])) else None for k in ('open','high','low','close')}
        if all(isinstance(v,(int,float)) and math.isfinite(v) for v in values.values()):
            if values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']:
                out.append({'ts':ts,**values})
    return sorted(out,key=lambda x:x['ts'])

def four_hour(candles, exchange_zone):
    zone=ZoneInfo(exchange_zone);sessions={}
    for c in candles:
        day=datetime.fromtimestamp(c['ts'],zone).date()
        sessions.setdefault(day,[]).append(c)
    result=[]
    for day,rows in sorted(sessions.items()):
        anchor=rows[0]['ts'];groups={}
        for c in rows:groups.setdefault(int((c['ts']-anchor)//14400),[]).append(c)
        for _,group in sorted(groups.items()):
            result.append({'ts':group[0]['ts'],'open':group[0]['open'],
                'high':max(c['high'] for c in group),'low':min(c['low'] for c in group),
                'close':group[-1]['close'],'observations':len(group)})
    return result

def update(feed,get):
    for symbol,asset in feed.get('darkPoolPrints',{}).get('assets',{}).items():
        frames=asset.setdefault('ohlcTimeframes',{})
        for frame,period in [('1d','1y'),('1h','60d')]:
            try:
                payload=get('https://query1.finance.yahoo.com/v8/finance/chart/'+symbol,
                            {'range':period,'interval':frame,'includePrePost':'false'}).json()
                series=(payload.get('chart',{}).get('result') or [{}])[0]
                candles=candles_from_series(series)
                if not candles:raise ValueError('No valid OHLC')
                zone=series.get('meta',{}).get('exchangeTimezoneName','America/New_York')
                meta={'source':'Yahoo Finance','observedAt':datetime.fromtimestamp(candles[-1]['ts'],timezone.utc).isoformat(),
                      'fetchedAt':datetime.now(timezone.utc).isoformat(),'timezone':zone,'status':'delayed'}
                frames[frame]={**meta,'candles':candles}
                if frame=='1h':
                    frames['4h']={**meta,'status':'calculated','candles':four_hour(candles,zone),
                                  'method':'1h OHLC aggregated from session start; final session bar may be shorter than 4h.'}
                else:
                    asset.update(ohlc=candles,ohlcSource='Yahoo Finance · daily OHLC',ohlcObservedAt=meta['observedAt'],
                                 priceSeries=[{'ts':c['ts'],'price':c['close']} for c in candles])
            except Exception as exc:
                asset.setdefault('ohlcErrors',{})[frame]=str(exc)[:160]
                continue
            asset.setdefault('ohlcErrors',{}).pop(frame,None)
