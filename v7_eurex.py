"""Official delayed Eurex OI chains. Settlement prices are not live quotes or IV."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import math
from bs4 import BeautifulSoup

PRODUCTS = {
 'DAX': ('ODAX', 'https://www.eurex.com/ex-en/markets/idx/dax/DAX-Options-70044'),
 'SX5E': ('OESX', 'https://www.eurex.com/ex-en/markets/idx/stx/euro-stoxx-50-derivatives/products/EURO-STOXX-50-Index-Options-69660'),
 'SXXP': ('OXXP', 'https://www.eurex.com/ex-en/markets/idx/stx/stoxx-europe-600/products/STOXX-Europe-600-Index-Options-70284'),
 'EXSA': ('EXSA', 'https://www.eurex.com/ex-en/markets/etf-etc/eqt-idx-etfs/iShares-STOXX-Europe-600-UCITS-DE-Options-70302'),
}
DAILY_PRODUCTS = {
 'DAX': ('ODAP', 'https://www.eurex.com/ex-en/markets/idx/dax/DAX-End-of-Day-Options-3734540'),
 'SX5E': ('OEXP', 'https://www.eurex.com/ex-en/markets/idx/stx/euro-stoxx-50-derivatives/products/EURO-STOXX-50-End-of-Day-Index-Options-3657352'),
}

def expiration_time(day, code):
    hour, minute = {'ODAX':(13,0), 'EXSA':(17,30), 'ODAP':(17,30), 'OEXP':(17,30)}.get(code, (12,0))
    return datetime.strptime(day,'%Y%m%d').replace(hour=hour,minute=minute,tzinfo=ZoneInfo('Europe/Berlin')).astimezone(timezone.utc)

def chain_rows(data, expiration):
    rows=[]
    for side,key in [('C','dataRowsCall'),('P','dataRowsPut')]:
        for x in data.get(key,[]):
            strike=x.get('strike'); oi=x.get('openInterest')
            if not isinstance(strike,(int,float)) or not math.isfinite(strike) or strike<=0 or not isinstance(oi,(int,float)) or not math.isfinite(oi) or oi<0:
                continue
            rows.append({'strike':strike,'openInterest':oi,'volume':x.get('volume') or 0,
                         'type':side,'expiration':expiration,'gamma':None,'iv':None,
                         'settlementPrice':x.get('dSettle'),'version':x.get('versionNumber')})
    return rows

def update(feed):
    import market_features as mf
    now=datetime.now(timezone.utc)
    markets=feed.setdefault('options',{}).setdefault('markets',[])
    for ticker,(code,page) in list(PRODUCTS.items()) + list(DAILY_PRODUCTS.items()):
        try:
            soup=BeautifulSoup(mf.get(page).text,'html.parser')
            configs=[json.loads(tag.string or tag.get_text()) for tag in soup.find_all('script',attrs={'data-product':True})]
            config=next(c for c in configs if c.get('productId') and c.get('busDate'))
            url='https://www.eurex.com/api/v1/overallstatistics/'+config['productId']
            date=config['busDate']
            overview=mf.get(url,{'busdate':date,'filtertype':'overview'}).json()
            if overview.get('meta',{}).get('productCode')!=code:raise ValueError('Wrong Eurex product')
            spot=overview['header']['underlyingClosingPrice'];profiles=[];selected=set()
            for expiry in sorted(overview.get('dataRows',[]),key=lambda x:x['date']):
                exp=expiration_time(expiry['date'],code)
                days=(exp.date()-now.date()).days
                if exp<=now or days>90:continue
                bucket='0DTE' if days==0 else 'NEXT' if days<=7 else '7-30D' if days<=30 else '30-90D'
                if bucket in selected:continue
                detail=mf.get(url,{'busdate':date,'filtertype':'detail','productdate':expiry['date'],'contracttype':expiry['contractType']}).json()
                if detail.get('meta',{}).get('productCode')!=code:raise ValueError('Wrong chain product')
                rows=chain_rows(detail,exp)
                if not rows:continue
                p=mf._option_summary(rows,spot,exp)
                # Missing Greeks must not erase observed OI or create zero GEX.
                strikes={}
                for r in rows:
                    z=strikes.setdefault(r['strike'],dict(strike=r['strike'],gex=None,callOi=0,putOi=0,callVolume=0,putVolume=0))
                    side='call' if r['type']=='C' else 'put'
                    z[side+'Oi']+=r['openInterest'];z[side+'Volume']+=r['volume']
                p.update(bucket=bucket,expirationAt=exp.isoformat(),strikeMap=sorted(strikes.values(),key=lambda x:x['strike']),
                         source='Eurex · '+code,sourceUrl=url,sourceWindow='Official OI/volume by strike; settlement prices, no IV/Greeks supplied.',
                         gammaFlip=None,gammaFlipStatus='No IV/Greeks in official statistics',
                         oiCoveragePct=100*len(rows)/max(1,len(detail.get('dataRowsCall',[]))+len(detail.get('dataRowsPut',[]))),
                         observedAt=datetime.strptime(date,'%Y%m%d').date().isoformat(),fetchedAt=now.isoformat(),
                         dataStatus='REAL / DELAYED · Eurex OI and volume',contractCode=code)
                profiles.append(p);selected.add(bucket)
            if not profiles:raise ValueError('No unexpired chains')
            prior=next((m for m in markets if m.get('ticker')==ticker),{})
            profiles = [p for p in prior.get('profiles',[]) if p.get('contractCode') and p['contractCode'] != code] + profiles
            entry={**prior,'ticker':ticker,'name':prior.get('name',ticker),'spot':spot,'referenceOnly':False,
                   'profiles':profiles,'source':'Eurex · '+code,'sourceUrl':page,'asOf':datetime.strptime(date,'%Y%m%d').date().isoformat(),
                   'dataStatus':'REAL / DELAYED · official Eurex chains','method':'Observed OI and volume; Max Pain calculated. GEX unavailable without verified IV/Greeks.'}
            markets[:]=[m for m in markets if m.get('ticker')!=ticker]+[entry]
            feed.setdefault('sourceWarnings',{}).pop('EUREX_'+code,None)
        except Exception as exc:
            feed.setdefault('sourceWarnings',{})['EUREX_'+code]=str(exc)[:180]
