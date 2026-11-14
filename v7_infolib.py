"""Provider-reported off-exchange rows; date precision only until timezone verified."""
from datetime import datetime, timezone
import math

URL='https://infolib.org/market-dashboard/get-darkpools-raw'

def normalize(row):
    try:
        stamp=datetime.strptime(row['date'],'%Y-%m-%d %I:%M %p')
        price=float(row['price']);size=float(row['size']);value=float(row['avg_paid'])
        if not all(math.isfinite(x) and x>0 for x in (price,size,value)):return None
        if abs(price*size-value)>max(1,price*size*.001):return None
        return dict(ticker=row['symbol'],timestamp=stamp.date().isoformat(),reportedTime=row['date'],
                    timestampPrecision='date',timezone=None,price=price,size=size,notional=price*size,
                    side='UNKNOWN',realPrint=True,source='InfoLib · provider-reported print',sourceUrl=URL,
                    sourceMode='PROVIDER_REPORTED',sideBasis='Direction and institution not disclosed',
                    priceBasis='Provider reported price; execution venue not disclosed')
    except (ValueError,KeyError,TypeError):return None

def update(feed):
    import market_features as mf
    rows=mf.get(URL,{'limit':500}).json().get('raw',[])
    normalized=[p for row in rows if (p:=normalize(row))]
    if not normalized:raise ValueError('No valid provider rows')
    section=feed.setdefault('darkPoolPrints',{});assets=section.setdefault('assets',{})
    for symbol,asset in assets.items():
        incoming=[p for p in normalized if p['ticker']==symbol]
        existing=asset.get('prints',[])
        keyed={(p.get('source'),p.get('reportedTime') or p.get('timestamp'),p.get('price'),p.get('size')):p for p in existing+incoming}
        asset['prints']=sorted(keyed.values(),key=lambda p:str(p.get('timestamp','')))[-300:]
    section['infolib']={'fetchedAt':datetime.now(timezone.utc).isoformat(),'rows':len(normalized),'sourceUrl':URL,
                       'note':'Provider-reported rows. Timezone not supplied: plotted by date only on daily charts; no BUY/SELL or institution inference.'}
