#!/usr/bin/env python3
"""MacroTerminal feed updater: free-first, conservative and non-destructive."""
from __future__ import annotations
import json, os, re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import requests
from bs4 import BeautifulSoup
from market_features import enrich_feed
from data_integrity import bls_observation, transform_monthly

ROOT=Path(__file__).resolve().parent
FEED_PATH=ROOT/'macro-feed.json'
HEADERS={'User-Agent':'MacroTerminal/1.0','Accept-Language':'en-US,en;q=0.9'}
TIMEOUT=10

ECONOMIES={
 'us':{'te':'united states'},'eu':{'te':'euro area'},'de':{'te':'germany'},'uk':{'te':'united kingdom'},
 'ch':{'te':'switzerland'},'jp':{'te':'japan'},'ca':{'te':'canada'},'au':{'te':'australia'},'nz':{'te':'new zealand'}
}

YAHOO={'SP500':'^GSPC','NASDAQ':'^IXIC','VIX':'^VIX','VVIX':'^VVIX','SKEW':'^SKEW','MOVE':'^MOVE','HYG':'HYG','LQD':'LQD','GOLD':'GC=F','COPPER':'HG=F','BRENT':'BZ=F','WTI':'CL=F','DXY':'DX-Y.NYB','AUDJPY':'AUDJPY=X','BTC':'BTC-USD','ETH':'ETH-USD','TLT':'TLT','SPY':'SPY'}
ROLES={'SP500':'Acciones / apetito de riesgo','NASDAQ':'Growth / beta alta','VIX':'Volatilidad bursátil','VVIX':'Volatilidad de la volatilidad','SKEW':'Riesgo de cola','MOVE':'Volatilidad de bonos','HYG':'Crédito high yield','LQD':'Crédito investment grade','GOLD':'Activo defensivo','COPPER':'Cíclico / crecimiento','BRENT':'Energía / inflación','WTI':'Energía / inflación','DXY':'Dólar / liquidez','AUDJPY':'Carry / apetito de riesgo','BTC':'Beta alta / liquidez','ETH':'Beta alta / liquidez','TLT':'Duración / cobertura','SPY':'ETF de acciones'}

BLS={'Nóminas no agrícolas (NFP)':('CES0000000001','EMPLEO',+1,3,'K'),'Tasa de desempleo':('LNS14000000','EMPLEO',-1,3,'%'),'Salarios (AHE YoY)':('CES0500000003','EMPLEO',+1,2,'%'),'JOLTS Vacantes':('JTS000000000000000JOL','EMPLEO',+1,2,'K'),'JOLTS Tasa de abandonos':('JTS000000000000000QUR','EMPLEO',+1,2,'%')}
FRED={'PCE subyacente (Anual)':('PCEPILFE','INFLACIÓN',+1,3,'%'),'PCE (Anual)':('PCEPI','INFLACIÓN',+1,3,'%'),'PIB (Trimestral)':('A191RL1Q225SBEA','CRECIMIENTO',+1,3,'%'),'Initial Jobless Claims':('ICNSA','EMPLEO',-1,2,'K'),'Continuing Claims':('CCNSA','EMPLEO',-1,2,'K'),'HY OAS':('BAMLH0A0HYM2','CONDICIONES FINANCIERAS',-1,2,'%')}

# Fechas de decisión publicadas por los propios bancos centrales. Se usan como
# disparadores de actualización y calendario, nunca como una inferencia de tipos.
CENTRAL_BANK_EVENTS=(
 {'economyId':'au','currency':'AUD','date':'2026-11-03T03:30:00Z','event':'RBA · decisión de política monetaria','country':'Australia','source':'Reserve Bank of Australia','sourceUrl':'https://www.rba.gov.au/coming-up/'},
 {'economyId':'uk','currency':'GBP','date':'2026-11-05T12:00:00Z','event':'BoE · decisión MPC y rueda de prensa','country':'Reino Unido','source':'Bank of England','sourceUrl':'https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates'},
 {'economyId':'au','currency':'AUD','date':'2026-12-08T03:30:00Z','event':'RBA · decisión de política monetaria','country':'Australia','source':'Reserve Bank of Australia','sourceUrl':'https://www.rba.gov.au/coming-up/'},
 {'economyId':'us','currency':'USD','date':'2026-12-09T19:00:00Z','event':'Fed · decisión FOMC y rueda de prensa','country':'Estados Unidos','source':'Federal Reserve','sourceUrl':'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'},
 {'economyId':'ca','currency':'CAD','date':'2026-12-09T14:45:00Z','event':'BoC · decisión de tipos','country':'Canadá','source':'Bank of Canada','sourceUrl':'https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/'},
 {'economyId':'nz','currency':'NZD','date':'2026-12-09T01:00:00Z','event':'RBNZ · OCR y Monetary Policy Statement','country':'Nueva Zelanda','source':'Reserve Bank of New Zealand','sourceUrl':'https://www.rbnz.govt.nz/news-and-events/how-we-release-information/ocr-decision-dates-and-financial-stability-report-dates-to-feb-2028'},
 {'economyId':'ch','currency':'CHF','date':'2026-12-10T08:30:00Z','event':'SNB · evaluación monetaria y rueda de prensa','country':'Suiza','source':'Swiss National Bank','sourceUrl':'https://www.snb.ch/en/services-events/digital-services/event-schedule'},
 {'economyId':'eu','currency':'EUR','date':'2026-12-17T13:15:00Z','event':'BCE · decisión y rueda de prensa','country':'Eurozona','source':'European Central Bank','sourceUrl':'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html'},
 {'economyId':'de','currency':'EUR','date':'2026-12-17T13:15:00Z','event':'BCE · decisión y rueda de prensa','country':'Eurozona','source':'European Central Bank','sourceUrl':'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html'},
 {'economyId':'uk','currency':'GBP','date':'2026-12-17T12:00:00Z','event':'BoE · decisión MPC','country':'Reino Unido','source':'Bank of England','sourceUrl':'https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates'},
 {'economyId':'jp','currency':'JPY','date':'2026-12-18T03:00:00Z','event':'BoJ · decisión de política monetaria','country':'Japón','source':'Bank of Japan','sourceUrl':'https://www.boj.or.jp/en/mopo/mpmsche_minu/'},
)

# Official publication endpoints are deliberately kept separate from the meeting
# calendar.  A calendar date is not a released decision.  The collector only
# promotes an item to the three-meeting history after an official publication
# is actually visible and retains the last valid history on outages.
CENTRAL_BANK_PUBLICATIONS={
 'us':{'bank':'Federal Reserve','feed':'https://www.federalreserve.gov/feeds/press_all.xml','match':r'Federal Reserve issues FOMC statement|FOMC statement|implementation note issued'},
 'eu':{'bank':'European Central Bank','feed':'https://www.ecb.europa.eu/rss/press.html','match':r'monetary policy decisions|monetary policy statement'},
 'uk':{'bank':'Bank of England','feed':'https://www.bankofengland.co.uk/rss/news','match':r'Bank Rate|Monetary Policy Report|Monetary Policy Summary'},
 'ca':{'bank':'Bank of Canada','feed':'https://www.bankofcanada.ca/feed/','match':r'policy interest rate|Monetary Policy Report'},
 'au':{'bank':'Reserve Bank of Australia','feed':'https://www.rba.gov.au/rss/rss-cb.xml','match':r'monetary policy decision|Statement by the Reserve Bank Board'},
 'nz':{'bank':'Reserve Bank of New Zealand','feed':'https://www.rbnz.govt.nz/rss.xml','match':r'Official Cash Rate|Monetary Policy Statement'},
 'ch':{'bank':'Swiss National Bank','feed':'https://www.snb.ch/public/en/rss/news','match':r'monetary policy assessment|SNB maintains|SNB lowers|SNB raises'},
 'jp':{'bank':'Bank of Japan','feed':'https://www.boj.or.jp/en/rss/whatsnew.xml','match':r'Statement on Monetary Policy|Monetary Policy Meeting'},
}

def get(url,params=None,method='get'):
 r=requests.request(method,url,params=params or {},headers=HEADERS,timeout=TIMEOUT); r.raise_for_status(); return r

def num(x):
 if x is None:return None
 try:return float(re.sub(r'[^0-9+\-.]','',str(x).replace(',','')))
 except:return None

def fmt(v,u=''):
 if v is None:return ''
 if u=='%':return f'{v:.2f}%'
 if u=='K':return f'{v:.0f}K'
 return f'{v:.2f}'

def load():
 with FEED_PATH.open(encoding='utf-8') as f:return json.load(f)

def write(feed):
 tmp=FEED_PATH.with_suffix('.tmp')
 tmp.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); tmp.replace(FEED_PATH)

def yahoo_metrics(symbol):
 try:
  u='https://query1.finance.yahoo.com/v8/finance/chart/'+requests.utils.quote(symbol,safe='')
  j=get(u,{'range':'1y','interval':'1d'}).json()['chart']['result'][0]
  rows=[]
  for ts,close in zip(j.get('timestamp') or [],j.get('indicators',{}).get('quote',[{}])[0].get('close',[]) or []):
   if close is not None:rows.append((datetime.fromtimestamp(float(ts),tz=timezone.utc).date(),float(close)))
  if len(rows)<22:return None
  q=[x[1] for x in rows];last=q[-1]
  ytd_rows=[x for x in rows if x[0].year==datetime.now(timezone.utc).year-1]
  base=ytd_rows[-1] if ytd_rows else None
  return {'last':last,'change1d':(last/q[-2]-1)*100,'change3s':(last/q[-4]-1)*100,
          'change5s':(last/q[-6]-1)*100,'change21s':(last/q[-22]-1)*100,
          'changeYtd':(last/base[1]-1)*100 if base and base[1] else None,
          'pointChangeYtd':last-base[1] if base else None,
          'ytdBaseDate':base[0].isoformat() if base else None,
          'observedAt':rows[-1][0].isoformat(),
          'change1w':(last/q[-6]-1)*100,'change1m':(last/q[-22]-1)*100,
          'pointChange1d':last-q[-2],'pointChange3s':last-q[-4],
          'pointChange5s':last-q[-6],'pointChange21s':last-q[-22],
          'pointChange1w':last-q[-6],'pointChange1m':last-q[-22]}
 except Exception as e:
  print('Yahoo',symbol,e);return None

def update_risk(feed):
 data=[]
 for n,sym in YAHOO.items():
  m=yahoo_metrics(sym)
  if not m:continue
  x={'name':n,'symbol':sym,'value':m['last'],
     **m,'role':ROLES.get(n,'Confirmación')}
  w=x.get('change5s')
  data.append(x)
  if w is None:x['marketSignal']='SIN DATO'
  elif n in {'SP500','NASDAQ','HYG','LQD','AUDJPY','COPPER','BTC','ETH','SPY'}:x['marketSignal']='FAVORECE RISK-ON ↑' if w>0.15 else 'TENSIONA RISK-ON ↓' if w<-0.15 else 'NEUTRO →'
  elif n in {'VIX','VVIX','SKEW','MOVE','DXY'}:x['marketSignal']='CALMA / RISK-ON ↑' if w<-0.15 else 'ESTRÉS / RISK-OFF ↑' if w>0.15 else 'NEUTRO →'
  else:x['marketSignal']='CONTEXTO ↑' if w>0.15 else 'CONTEXTO ↓' if w<-0.15 else 'NEUTRO →'
 if not data:return
 by={x['name']:x for x in data};score=50.0;comp=[]
 def add(n,p,w):
  nonlocal score;score+=p;comp.append((p,n,w))
 for n,w in [('SP500',8),('NASDAQ',8)]:
  if n in by:add(n,max(-w,min(w,(by[n]['change5s'] or 0)*w/1.5)),'tendencia 5S')
 if 'VIX' in by:
  v=by['VIX']['value'];add('VIX',8 if v<15 else 4 if v<20 else -4 if v<25 else -8,'nivel de volatilidad')
 if 'VVIX' in by:
  v=by['VVIX']['value'];add('VVIX',4 if v<90 else 1 if v<105 else -2 if v<115 else -4,'volatilidad de volatilidad')
 if 'SKEW' in by:
  v=by['SKEW']['value'];add('SKEW',3 if v<120 else 1 if v<130 else -2 if v<140 else -4,'riesgo de cola')
 if 'MOVE' in by:
  v=by['MOVE']['value'];add('MOVE',3 if v<70 else 1 if v<85 else -2 if v<110 else -5,'volatilidad de bonos')
 for n,w in [('AUDJPY',2),('DXY',-2),('COPPER',1.5),('BTC',.8),('HYG',1.5),('LQD',1)]:
  if n in by:add(n,max(-5,min(5,(by[n]['change5s'] or 0)*w)),'confirmación intermercado')
 if 'GOLD' in by:add('GOLD',max(-3,min(3,-(by['GOLD']['change5s'] or 0)*1.2)),'demanda defensiva')
 if 'BRENT' in by and 'WTI' in by:
  oil=max(by['BRENT']['change5s'] or 0,by['WTI']['change5s'] or 0);add('OIL',-2 if oil>6 else -1 if oil<-6 else 0,'shock energético contextual')
 if 'TLT' in by and 'SPY' in by:add('TLT/SPY',max(-3,min(3,-((by['TLT']['change5s'] or 0)-(by['SPY']['change5s'] or 0))*1.5)),'duración vs acciones')
 score=max(0,min(100,score));label='RISK ON' if score>=65 else 'RISK OFF' if score<=35 else 'NEUTRAL / MIXTO'
 pos=sum(p>.4 for p,_,_ in comp);neg=sum(p<-.4 for p,_,_ in comp)
 conf=round(max(35,min(90,55+min(20,abs(pos-neg)*3)-(10 if pos and neg and abs(pos-neg)<=1 else 0))))
 why={'SP500':'la bolsa amplia acompaña el apetito por riesgo','NASDAQ':'la beta alta acompaña el régimen','VIX':'la volatilidad bursátil está contenida','VVIX':'la volatilidad de la volatilidad no muestra estrés','SKEW':'el riesgo de cola no muestra tensión extrema','MOVE':'la volatilidad de bonos no muestra estrés significativo','HYG':'el crédito high yield acompaña el apetito por riesgo','LQD':'el crédito investment grade se mantiene estable','DXY':'el dólar actúa como refugio/liquidez','AUDJPY':'el carry confirma apetito por riesgo','COPPER':'el cobre acompaña la demanda cíclica','GOLD':'el oro muestra demanda defensiva','BTC':'cripto acompaña la liquidez/alta beta','ETH':'cripto acompaña la liquidez/alta beta','TLT/SPY':'la duración gana terreno relativo a acciones','OIL':'el petróleo aporta señal de crecimiento/inflación'}
 positives=sorted([x for x in comp if x[0]>0],reverse=True)[:5];negatives=sorted([x for x in comp if x[0]<0])[:5]
 feed['riskOnOff']={'updated':datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC'),'score':round(score,1),'label':label,'confidence':conf,
  'method':'Composite intermercado. Ventanas basadas en cierres: 1D, 3S, 5S, 21S y YTD. Un activo positivo no es automáticamente risk-on; se interpreta por su función de mercado.',
  'assets':data,'confirmations':[f'{n}: {why.get(n,w)}.' for _,n,w in positives],
  'tensions':[f'{n}: {why.get(n,w)}.' for _,n,w in negatives],
  'coverage':{'totalAssets':len(data),'windows':['1D','3S','5S','21S','YTD'],'symbols':[x['symbol'] for x in data]}}

def fred_csv(sid):
 try:
  txt=get('https://fred.stlouisfed.org/graph/fredgraph.csv',{'id':sid}).text
  if sid in ('PCEPILFE','PCEPI'):
   values={line.split(',')[0][:7]:float(line.split(',')[1]) for line in txt.splitlines()[1:] if ',' in line and num(line.split(',')[1]) is not None}
   if not values:return None
   period=max(values); value=transform_monthly(values,period,'yoy')
   return (value,period) if value is not None else None
  for line in reversed(txt.splitlines()[1:]):
   if ',' not in line:continue
   d,v=line.split(',',1); n=num(v)
   if n is not None:return n,d
 except Exception as e:print('FRED',sid,e)
 return None

def update_us(feed):
 us=feed.setdefault('economies',{}).setdefault('us',{}); inds=us.setdefault('indicators',[]); by={x.get('name'):x for x in inds}
 # FRED series are fetched individually. BLS series are fetched together below.
 for name,(sid,cat,sign,imp,unit) in FRED.items():
  res=fred_csv(sid)
  if not res:continue
  v,d=res
  if sid in ('ICNSA','CCNSA'):v/=1000
  row=by.get(name) or {'cat':cat,'name':name,'actual':'','est':'','surprise':'','date':'','imp':'★'*imp,'source':'FRED','rateImpact':sign}
  if row.get('date')!=d:row.update(est='',surprise='')
  row.update(actual=fmt(v,unit),date=d,source='Federal Reserve Bank of St. Louis (FRED)',rateImpact=sign)
  if name not in by:inds.append(row)
 # BLS one request for all series
 try:
  ids=[x[0] for x in BLS.values()]
  # The public endpoint requires a JSON body.
  j=requests.post('https://api.bls.gov/publicAPI/v2/timeseries/data/',json={'seriesid':ids,'startyear':str(datetime.now().year-1),'endyear':str(datetime.now().year)},headers={**HEADERS,'Content-Type':'application/json'},timeout=TIMEOUT).json()
  for name,(sid,cat,sign,imp,unit) in BLS.items():
   rows=next((x['data'] for x in j.get('Results',{}).get('series',[]) if x.get('seriesID')==sid),[])
   if not rows:continue
   observation=bls_observation(rows,sid)
   if observation is None:continue
   v,period,transformation=observation
   row=by.get(name) or {'cat':cat,'name':name,'actual':'','est':'','surprise':'','date':'','imp':'★'*imp,'source':'BLS','rateImpact':sign}
   if row.get('date')!=period:row.update(est='',surprise='')
   row.update(actual=fmt(v,unit),date=period,source='U.S. Bureau of Labor Statistics',sourceUrl='https://data.bls.gov/timeseries/'+sid,transformation=transformation,rateImpact=sign)
   if name not in by:inds.append(row)
 except Exception as e:print('BLS',e)

def update_treasury(feed):
 us=feed.get('economies',{}).get('us',{}); y=datetime.now(timezone.utc).year;m=datetime.now(timezone.utc).month
 try:
  html=get('https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView',{'field_tdr_date_value_month':f'{y}{m:02d}','type':'daily_treasury_yield_curve'}).text
  soup=BeautifulSoup(html,'html.parser'); table=soup.find('table'); rows=[]
  for tr in table.find_all('tr') if table else []:
   cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])]
   if cells:rows.append(cells)
  if len(rows)<2:return
  h=rows[0]; latest=rows[-1]; labels={'3 Mo':'3M','1 Yr':'1Y','2 Yr':'2Y','5 Yr':'5Y','10 Yr':'10Y','20 Yr':'20Y','30 Yr':'30Y'}
  vals={}
  for i,x in enumerate(h):
   if x.strip() in labels and i<len(latest):
    v=num(latest[i]);
    if v is not None:vals[labels[x.strip()]]=v
  old={x.get('term'):x for x in us.get('bonds',{}).get('tenors',[])}; us.setdefault('bonds',{})['tenors']=[{'term':t,'yield':f"{vals[t]:.3f}%" if t in vals else old.get(t,{}).get('yield',''),'change':old.get(t,{}).get('change',''),'isKey':t in ('2Y','10Y')} for t in ['3M','1Y','2Y','5Y','10Y','20Y','30Y']]
  us['bonds']['date']=latest[0];us['bonds']['source']='U.S. Department of the Treasury'
 except Exception as e:print('Treasury',e)

def update_te(feed):
 key=os.getenv("TE_API_KEY")
 if not key:
  print("TE calendar: no API key; retaining last valid calendar snapshot")
  return
 now=datetime.now(timezone.utc)
 a=(now-timedelta(days=10)).date().isoformat()
 b=(now+timedelta(days=14)).date().isoformat()
 calendar=[]
 currency_map={"us":"USD","eu":"EUR","de":"EUR","uk":"GBP","ch":"CHF","jp":"JPY","ca":"CAD","au":"AUD","nz":"NZD"}
 relevant=("cpi","ipc","hicp","ipca","inflation","inflación","pce","ppi","índice de precios","unemployment","desempleo","paro","payroll","nóminas","employment","empleo","wage","salario","claims","subsidio de desempleo","gdp","pib","retail","ventas minoristas","industrial production","producción industrial","pmi","ism","core","subyacente","rate decision","decisión de tipos","interest rate","tipo de interés","consumer confidence","confianza del consumidor","business confidence","confianza empresarial","ifo","zew","z ew","tankan")
 meta_map={
  "cpi":("INFLACIÓN",3,1),"ipc":("INFLACIÓN",3,1),"hicp":("INFLACIÓN",3,1),"ipca":("INFLACIÓN",3,1),"inflation":("INFLACIÓN",3,1),"inflación":("INFLACIÓN",3,1),"pce":("INFLACIÓN",3,1),"índice de precios":("INFLACIÓN",3,1),
  "ppi":("INFLACIÓN",2,1),"subyacente":("INFLACIÓN",2,1),"unemployment":("EMPLEO",3,-1),"desempleo":("EMPLEO",3,-1),"paro":("EMPLEO",3,-1),
  "payroll":("EMPLEO",3,1),"nóminas":("EMPLEO",3,1),"employment":("EMPLEO",3,1),"empleo":("EMPLEO",3,1),"wage":("EMPLEO",2,1),"salario":("EMPLEO",2,1),"claims":("EMPLEO",2,-1),"subsidio de desempleo":("EMPLEO",2,-1),
  "gdp":("CRECIMIENTO",3,1),"pib":("CRECIMIENTO",3,1),"retail":("CRECIMIENTO",2,1),"ventas minoristas":("CRECIMIENTO",2,1),
  "industrial production":("CRECIMIENTO",2,1),"producción industrial":("CRECIMIENTO",2,1),"pmi":("CRECIMIENTO",2,1),
  "ism":("CRECIMIENTO",2,1),"rate decision":("BANCO CENTRAL",3,0),"decisión de tipos":("BANCO CENTRAL",3,0),
  "interest rate":("BANCO CENTRAL",3,0),"tipo de interés":("BANCO CENTRAL",3,0),"consumer confidence":("CONFIANZA",2,1),"confianza del consumidor":("CONFIANZA",2,1),
  "business confidence":("CONFIANZA",2,1),"confianza empresarial":("CONFIANZA",2,1),"ifo":("CRECIMIENTO",2,1),
  "zew":("CRECIMIENTO",2,1),"z ew":("CRECIMIENTO",2,1),"tankan":("CRECIMIENTO",2,1)
 }
 for eid,cfg in ECONOMIES.items():
  try:
   url=f"https://api.tradingeconomics.com/calendar/country/{requests.utils.quote(cfg['te'])}/{a}/{b}"
   data=get(url,{'c':key,'f':'json','importance':2,'lang':'es'}).json()
   eco=feed.get('economies',{}).get(eid,{})
   inds=eco.setdefault('indicators',[])
   for ev in data if isinstance(data,list) else []:
    name=ev.get('Event') or ev.get('Category') or 'Evento'
    lname=name.lower()
    if not any(k in lname for k in relevant):continue
    actual=ev.get('Actual')
    forecast=ev.get('Forecast')
    if forecast in (None,'','-'):forecast=ev.get('TEForecast')
    previous=ev.get('Previous')
    raw_date=str(ev.get('Date') or '')
    date=raw_date[:16].replace('T',' ')
    event={"economyId":eid,"currency":currency_map.get(eid),"country":ev.get('Country') or cfg['te'],
           "date":date,"event":name,"actual":str(actual if actual is not None else ''),"forecast":str(forecast if forecast is not None else ''),
           "previous":str(previous if previous is not None else ''),"importance":ev.get('Importance') or 2,
           "source":ev.get('Source') or 'Trading Economics'}
    calendar.append(event)
    # Only published actuals belong in the historical indicator table.
    if actual in (None,'','-','N/A'):continue
    meta=next((v for k,v in meta_map.items() if k in lname),('MACRO',2,0))
    cat,imp,sign=meta
    row=next((x for x in inds if x.get('name')==name),None) or {'cat':cat,'name':name,'actual':'','est':'','surprise':'','date':'','imp':'★'*imp,'source':'Trading Economics','rateImpact':sign}
    row.update(actual=str(actual),est=str(forecast or ''),date=date,source=ev.get('Source') or 'Trading Economics',rateImpact=sign)
    if forecast not in (None,'') and num(actual) is not None and num(forecast) is not None:
     row['surprise']=f"{(num(actual)-num(forecast))*sign:+.2f}"
    if row not in inds:inds.append(row)
  except Exception as e:
   print('TE',eid,type(e).__name__,str(e)[:180])
 if calendar:
  # Deduplicate euro-area/Germany calendar entries without merging distinct releases.
  unique={}
  for ev in calendar:
   key=(ev.get('economyId'),ev.get('date'),ev.get('event'))
   unique[key]=ev
  events=sorted(unique.values(),key=lambda x:(x.get('date') or '',-int(x.get('importance') or 0)))
  feed['economicCalendar']={"updated":datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC'),
   "windowStart":a,"windowEnd":b,"events":events,"source":"Trading Economics calendar",
   "sourceUrl":"https://tradingeconomics.com/calendar","dataStatus":"REAL CALENDAR · forecast and actual values where published"}
 elif not (feed.get('economicCalendar') or {}).get('events'):
  feed['economicCalendar']={"updated":datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC'),
   "events":[],"source":"Trading Economics calendar","dataStatus":"UNAVAILABLE · no verified calendar rows"}

def update_central_bank_calendar(feed):
 now=datetime.now(timezone.utc)
 previous=(feed.get('economicCalendar') or {}).get('events') or []
 official=[dict(x,actual='',forecast='',previous='',importance=3) for x in CENTRAL_BANK_EVENTS if datetime.fromisoformat(x['date'].replace('Z','+00:00')) >= now-timedelta(days=2)]
 # Mantiene las publicaciones macro ya presentes y sustituye sólo el calendario
 # de decisiones con la versión oficial, sin duplicar eventos.
 other=[x for x in previous if 'economyId' in x and not str(x.get('event','')).lower().startswith(('fed ·','bce ·','boe ·','boj ·','snb ·','rba ·','rbnz ·','boc ·'))]
 merged={}
 for event in other+official:
  merged[(event.get('economyId'),event.get('date'),event.get('event'))]=event
 events=sorted(merged.values(),key=lambda x:(str(x.get('date') or ''),-int(x.get('importance') or 0)))
 feed['economicCalendar']={
  'updated':now.strftime('%d/%m/%Y %H:%M UTC'), 'events':events,
  'source':'Calendarios oficiales de bancos centrales + calendario macro cuando está disponible',
  'dataStatus':'CALENDARIO OFICIAL · decisiones y ruedas de prensa con fuente enlazada'}
 for eco in feed.get('economies',{}).values():
  candidates=[x for x in official if x['economyId']==eco.get('id')]
  if candidates:
   event=min(candidates,key=lambda x:x['date'])
   eco.setdefault('rates',{})['nextMeeting']=event['date'][:10]

def _publication_date(item):
 for key in ('published','updated','pubDate','date'):
  raw=item.get(key)
  if not raw: continue
  try:
   if isinstance(raw,datetime): return raw.astimezone(timezone.utc)
   text=str(raw).replace('Z','+00:00')
   return datetime.fromisoformat(text).astimezone(timezone.utc)
  except Exception:
   try:return parsedate_to_datetime(str(raw)).astimezone(timezone.utc)
   except Exception:pass
 return None

def _official_feed_items(url):
 """Small tolerant Atom/RSS reader; intentionally returns no rows on format changes."""
 xml=get(url).text
 soup=BeautifulSoup(xml,'xml')
 entries=soup.find_all(['entry','item'])
 result=[]
 for entry in entries[:30]:
  title=entry.find('title'); title=title.get_text(' ',strip=True) if title else ''
  link=entry.find('link'); href=''
  if link:
   href=link.get('href') or link.get_text(' ',strip=True)
  if not href:
   guid=entry.find('guid'); href=guid.get_text(' ',strip=True) if guid else ''
  summary=entry.find(['summary','description','content'])
  summary=BeautifulSoup(summary.get_text(' ',strip=True) if summary else '','html.parser').get_text(' ',strip=True)
  rawdate=entry.find(['published','updated','pubDate','date'])
  result.append({'title':title,'link':href,'summary':summary,'published':rawdate.get_text(' ',strip=True) if rawdate else ''})
 return result

def update_central_bank_publications(feed):
 economies=feed.get('economies',{})
 now=datetime.now(timezone.utc)
 for eid,cfg in CENTRAL_BANK_PUBLICATIONS.items():
  eco=economies.get(eid)
  if not isinstance(eco,dict):continue
  try:
   candidates=[]
   for item in _official_feed_items(cfg['feed']):
    published=_publication_date(item)
    title=str(item.get('title') or '')
    if not published or published>now+timedelta(hours=6) or not re.search(cfg['match'],title,re.I):continue
    candidates.append((published,item))
   if not candidates:continue
   published,item=max(candidates,key=lambda x:x[0])
   conference=eco.setdefault('conference',{})
   history=list(conference.get('history') or [])
   record={'date':published.strftime('%Y-%m-%d %H:%M UTC'),'title':item['title'],'tone':'Sin clasificación automática',
           'summary':(item.get('summary') or 'Comunicado oficial publicado; requiere lectura del texto original.')[:700],
           'keyPoints':[],'sourceUrl':item.get('link') or cfg['feed'],'source':cfg['bank'],'publicationType':'Comunicado oficial'}
   # Identidad por URL, con fecha+título como respaldo cuando el RSS no incluye URL.
   identity=(record['sourceUrl'],record['date'],record['title'])
   old={(str(x.get('sourceUrl') or ''),str(x.get('date') or ''),str(x.get('title') or '')) for x in history if isinstance(x,dict)}
   if identity not in old:
    history.insert(0,record)
   history=sorted([x for x in history if isinstance(x,dict)],key=lambda x:str(x.get('date') or ''),reverse=True)[:3]
   conference['history']=history
   if history:
    latest=history[0]
    # A newly published official item may replace the headline, but never gets
    # an invented hawkish/dovish label or analyst interpretation.
    conference.update({k:latest.get(k) for k in ('date','title','tone','summary','keyPoints','sourceUrl')})
   conference['lastOfficialCheck']=now.strftime('%d/%m/%Y %H:%M UTC')
   conference['sourceStatus']='OFICIAL · RSS/Atom del banco central'
  except Exception as e:
   # Preserve history and make the failure inspectable without polluting cards.
   eco.setdefault('conference',{})['lastOfficialCheck']=now.strftime('%d/%m/%Y %H:%M UTC')
   eco['conference']['sourceStatus']='Último comunicado válido retenido; fuente oficial no respondió'
   print('CENTRAL BANK PUBLICATION',eid,type(e).__name__,str(e)[:160])

def normalize_central_bank_history(feed):
 for eco in feed.get('economies',{}).values():
  conference=eco.get('conference') or {}
  history=list(conference.get('history') or [])
  current={k:conference.get(k) for k in ('date','title','tone','summary','keyPoints','sourceUrl')}
  if current.get('date') and current.get('title') and not any(x.get('date')==current['date'] for x in history):
   history.insert(0,current)
  if history: conference['history']=history[:3]
  eco['conference']=conference
  rates=eco.setdefault('rates',{})
  # Nunca presentar porcentajes guardados sin proveedor, URL y fecha UTC.
  required=('expectationsUpdated','expectationsSource','expectationsUrl')
  if not all(rates.get(k) for k in required):
   rates.pop('expectations',None)
   rates['expectationsStatus']='UNAVAILABLE · falta proveedor fechado de expectativas de mercado'

def ensure_slots(feed):
 for eco in feed.get('economies',{}).values():
  b=eco.setdefault('bonds',{}); old={x.get('term'):x for x in b.get('tenors',[])}
  b['tenors']=[old.get(t,{'term':t,'yield':'','change':'','isKey':t in ('2Y','10Y'),'note':'No hay benchmark exacto conectado; no se interpola.'}) for t in ['3M','1Y','2Y','5Y','10Y','20Y','30Y']]

def main():
 feed=load();update_us(feed);update_treasury(feed);update_te(feed);update_central_bank_calendar(feed);update_central_bank_publications(feed);normalize_central_bank_history(feed);ensure_slots(feed);update_risk(feed)
 enrich_feed(feed)
 stamp=datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC');feed['version']=6;feed['updated']=stamp;feed['automation']={'updatedAt':stamp,'runner':'GitHub Actions / update_feed.py','intervalMinutes':int(os.getenv('MACRO_INTERVAL_MINUTES','360')),'notes':['Mercado/Risk-On-Off se refresca según la ejecución programada y disponibilidad de Yahoo; todos los activos muestran 1D/5S/21S.','Indicadores macro solo cambian cuando se publica un nuevo dato.','Las curvas usan benchmarks reales disponibles; no se interpolan silenciosamente.','COT es semanal; opciones usan gamma proxy; dark pools/OTC son datos agregados y con retraso.']};write(feed);print('Feed actualizado',stamp)

if __name__=='__main__':main()
