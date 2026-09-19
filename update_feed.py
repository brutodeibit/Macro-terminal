#!/usr/bin/env python3
"""MacroTerminal feed updater: free-first, conservative and non-destructive."""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import requests
from bs4 import BeautifulSoup
from market_features import enrich_feed

ROOT=Path(__file__).resolve().parent
FEED_PATH=ROOT/'macro-feed.json'
HEADERS={'User-Agent':'MacroTerminal/1.0','Accept-Language':'en-US,en;q=0.9'}
TIMEOUT=25

ECONOMIES={
 'us':{'te':'united states'},'eu':{'te':'euro area'},'de':{'te':'germany'},'uk':{'te':'united kingdom'},
 'ch':{'te':'switzerland'},'jp':{'te':'japan'},'ca':{'te':'canada'},'au':{'te':'australia'},'nz':{'te':'new zealand'}
}

YAHOO={'SP500':'^GSPC','NASDAQ':'^IXIC','VIX':'^VIX','VVIX':'^VVIX','SKEW':'^SKEW','MOVE':'^MOVE','HYG':'HYG','LQD':'LQD','GOLD':'GC=F','COPPER':'HG=F','BRENT':'BZ=F','WTI':'CL=F','DXY':'DX-Y.NYB','AUDJPY':'AUDJPY=X','BTC':'BTC-USD','ETH':'ETH-USD','TLT':'TLT','SPY':'SPY'}
ROLES={'SP500':'Acciones / apetito de riesgo','NASDAQ':'Growth / beta alta','VIX':'Volatilidad bursátil','VVIX':'Volatilidad de la volatilidad','SKEW':'Riesgo de cola','MOVE':'Volatilidad de bonos','HYG':'Crédito high yield','LQD':'Crédito investment grade','GOLD':'Activo defensivo','COPPER':'Cíclico / crecimiento','BRENT':'Energía / inflación','WTI':'Energía / inflación','DXY':'Dólar / liquidez','AUDJPY':'Carry / apetito de riesgo','BTC':'Beta alta / liquidez','ETH':'Beta alta / liquidez','TLT':'Duración / cobertura','SPY':'ETF de acciones'}

BLS={'Nóminas no agrícolas (NFP)':('CES0000000001','EMPLEO',+1,3,'K'),'Tasa de desempleo':('LNS14000000','EMPLEO',-1,3,'%'),'Salarios (AHE YoY)':('CES0500000003','EMPLEO',+1,2,'%'),'JOLTS Vacantes':('JTS000000000000000JOL','EMPLEO',+1,2,'K'),'JOLTS Tasa de abandonos':('JTS000000000000000QUR','EMPLEO',+1,2,'%')}
FRED={'PCE subyacente (Anual)':('PCEPILFE','INFLACIÓN',+1,3,'%'),'PCE (Anual)':('PCEPI','INFLACIÓN',+1,3,'%'),'PIB (Trimestral)':('A191RL1Q225SBEA','CRECIMIENTO',+1,3,'%'),'Initial Jobless Claims':('ICNSA','EMPLEO',-1,2,'K'),'Continuing Claims':('CCNSA','EMPLEO',-1,2,'K'),'HY OAS':('BAMLH0A0HYM2','CONDICIONES FINANCIERAS',-1,2,'%')}

def get(url,params=None,method='get'):
 r=requests.request(method,url,params=params or {},headers=HEADERS,timeout=TIMEOUT); r.raise_for_status(); return r

def num(x):
 if x is None:return None
 try:return float(re.sub(r'[^0-9+\-.]','',str(x).replace(',','')))
 except:return None

def fmt(v,u=''):
 if v is None:return ''
 if u=='%':return f'{v:.2f}%'
 if u=='K':return f'{v/1000:.0f}K' if abs(v)>10000 else f'{v:.0f}K'
 return f'{v:.2f}'

def load():
 with FEED_PATH.open(encoding='utf-8') as f:return json.load(f)

def write(feed):
 tmp=FEED_PATH.with_suffix('.tmp')
 tmp.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); tmp.replace(FEED_PATH)

def yahoo(symbol):
 try:
  u='https://query1.finance.yahoo.com/v8/finance/chart/'+requests.utils.quote(symbol,safe='')
  j=get(u,{'range':'1mo','interval':'1d'}).json()['chart']['result'][0]
  c=[x for x in j['indicators']['quote'][0].get('close',[]) if x is not None]
  if not c:return None
  last=float(c[-1]); prev=float(c[-2]) if len(c)>1 else last; p5=float(c[-6]) if len(c)>5 else float(c[0])
  return last,(last/prev-1)*100,(last/p5-1)*100
 except Exception as e: print('Yahoo',symbol,e); return None

def update_risk(feed):
 data=[]
 for n,s in YAHOO.items():
  m=yahoo(s)
  if not m:continue
  v,c1,c5=m; data.append({'name':n,'symbol':s,'value':v,'change1d':c1,'change5d':c5,'role':ROLES.get(n,'Confirmación')})
 if not data:return
 by={x['name']:x for x in data}; score=50.0; comp=[]
 def add(n,p,w):
  nonlocal score; score+=p; comp.append((p,n,w))
 for n,w in [('SP500',8),('NASDAQ',8)]:
  if n in by:add(n,max(-w,min(w,by[n]['change5d']*w/1.5)),'tendencia 5D')
 if 'VIX' in by:
  v=by['VIX']['value'];add('VIX',8 if v<15 else 4 if v<20 else -4 if v<25 else -8,'nivel de volatilidad')
 if 'VVIX' in by:
  v=by['VVIX']['value'];add('VVIX',4 if v<90 else 1 if v<105 else -2 if v<115 else -4,'volatilidad de volatilidad')
 if 'SKEW' in by:
  v=by['SKEW']['value'];add('SKEW',3 if v<120 else 1 if v<130 else -2 if v<140 else -4,'riesgo de cola')
 if 'MOVE' in by:
  v=by['MOVE']['value'];add('MOVE',3 if v<70 else 1 if v<85 else -2 if v<110 else -5,'volatilidad de bonos')
 for n,w in [('AUDJPY',2),('DXY',-2),('COPPER',1.5),('BTC',.8),('ETH',.8),('HYG',1.5),('LQD',1)]:
  if n in by:add(n,max(-5,min(5,by[n]['change5d']*w)),'confirmación intermercado')
 if 'GOLD' in by:add('GOLD',max(-3,min(3,-by['GOLD']['change5d']*1.2)),'demanda defensiva')
 if 'BRENT' in by and 'WTI' in by:
  oil=max(by['BRENT']['change5d'],by['WTI']['change5d']); add('OIL',-2 if oil>6 else -1 if oil<-6 else 0,'shock energético contextual')
 if 'TLT' in by and 'SPY' in by:add('TLT/SPY',max(-3,min(3,-(by['TLT']['change5d']-by['SPY']['change5d'])*1.5)),'duración vs acciones')
 score=max(0,min(100,score)); label='RISK ON' if score>=65 else 'RISK OFF' if score<=35 else 'NEUTRAL / MIXTO'
 pos=sum(p>.4 for p,_,_ in comp);neg=sum(p<-.4 for p,_,_ in comp); conf=round(max(35,min(90,55+min(20,abs(pos-neg)*3)-(10 if pos and neg and abs(pos-neg)<=1 else 0))))
 why={'SP500':'la bolsa amplia acompaña el apetito por riesgo','NASDAQ':'la beta alta acompaña el régimen','VIX':'la volatilidad bursátil está contenida','VVIX':'la volatilidad de la volatilidad no muestra estrés','SKEW':'el riesgo de cola no muestra tensión extrema','MOVE':'la volatilidad de bonos no muestra estrés significativo','HYG':'el crédito high yield acompaña el apetito por riesgo','LQD':'el crédito investment grade se mantiene estable','DXY':'el dólar actúa como refugio/liquidez','AUDJPY':'el carry confirma apetito por riesgo','COPPER':'el cobre acompaña la demanda cíclica','GOLD':'el oro muestra demanda defensiva','BTC':'cripto acompaña la liquidez/alta beta','ETH':'cripto acompaña la liquidez/alta beta','TLT/SPY':'la duración gana terreno relativo a acciones','OIL':'el petróleo aporta señal de crecimiento/inflación'}
 positives=sorted([x for x in comp if x[0]>0],reverse=True)[:5]; negatives=sorted([x for x in comp if x[0]<0])[:5]
 feed['riskOnOff']={'updated':datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC'),'score':round(score,1),'label':label,'confidence':conf,'method':'Composite intermercado: acciones, VIX/VVIX/SKEW, MOVE, crédito HYG/LQD, dólar, carry, materias primas, duración y cripto. El petróleo se trata como señal contextual de inflación/crecimiento.','assets':data,'confirmations':[f'{n}: {why.get(n,w)}.' for _,n,w in positives],'tensions':[f'{n}: {why.get(n,w)}.' for _,n,w in negatives], 'coverage':feed.get('riskOnOff',{}).get('coverage',{})}

def fred_csv(sid):
 try:
  txt=get('https://fred.stlouisfed.org/graph/fredgraph.csv',{'id':sid}).text
  for line in reversed(txt.splitlines()[1:]):
   if ',' not in line:continue
   d,v=line.split(',',1); n=num(v)
   if n is not None:return n,d
 except Exception as e:print('FRED',sid,e)
 return None

def update_us(feed):
 us=feed.setdefault('economies',{}).setdefault('us',{}); inds=us.setdefault('indicators',[]); by={x.get('name'):x for x in inds}
 for name,(sid,cat,sign,imp,unit) in {**BLS,**FRED}.items():
  if sid in [x[0] for x in BLS.values()]:
   try:
    now=datetime.now(timezone.utc); j=get('https://api.bls.gov/publicAPI/v2/timeseries/data/',method='post').json()
   except: continue
   # BLS is handled below with its own payload.
  res=fred_csv(sid)
  if not res:continue
  v,d=res; row=by.get(name) or {'cat':cat,'name':name,'actual':'','est':'','surprise':'','date':'','imp':'★'*imp,'source':'FRED','rateImpact':sign}
  row.update(actual=fmt(v,unit),date=d,source='Federal Reserve Bank of St. Louis (FRED)',rateImpact=sign)
  if name not in by:inds.append(row)
 # BLS one request for all series
 try:
  ids=[v[0] for v in BLS.values()]; j=get('https://api.bls.gov/publicAPI/v2/timeseries/data/',method='post')
  # The public endpoint requires JSON body, so retry correctly.
  j=requests.post('https://api.bls.gov/publicAPI/v2/timeseries/data/',json={'seriesid':ids,'startyear':str(datetime.now().year-1),'endyear':str(datetime.now().year)},headers={**HEADERS,'Content-Type':'application/json'},timeout=TIMEOUT).json()
  for name,(sid,cat,sign,imp,unit) in BLS.items():
   rows=next((x['data'] for x in j.get('Results',{}).get('series',[]) if x.get('seriesID')==sid),[])
   if not rows:continue
   r=rows[0]; v=num(r.get('value')); 
   if v is None:continue
   row=by.get(name) or {'cat':cat,'name':name,'actual':'','est':'','surprise':'','date':'','imp':'★'*imp,'source':'BLS','rateImpact':sign}
   row.update(actual=fmt(v,unit),date=f"{r.get('year','')}-{r.get('periodName','')[:3]}",source='U.S. Bureau of Labor Statistics',rateImpact=sign)
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
 key=os.getenv('TE_API_KEY');
 if not key:return
 now=datetime.now(timezone.utc); a=(now-timedelta(days=14)).date().isoformat();b=(now+timedelta(days=21)).date().isoformat()
 for eid,cfg in ECONOMIES.items():
  try:
   url=f"https://api.tradingeconomics.com/calendar/country/{requests.utils.quote(cfg['te'])}/{a}/{b}"
   data=get(url,{'c':key,'f':'json','importance':2,'lang':'es'}).json()
   eco=feed.get('economies',{}).get(eid,{}); inds=eco.setdefault('indicators',[])
   for ev in data if isinstance(data,list) else []:
    actual=ev.get('Actual');forecast=ev.get('Forecast') or ev.get('TEForecast')
    if actual in (None,'','-','N/A'):continue
    name=ev.get('Event') or ev.get('Category') or 'Evento'; lname=name.lower()
    if not any(k in lname for k in ('cpi','inflation','pce','ppi','unemployment','payroll','employment','wage','claims','gdp','retail','industrial production','pmi','ism','core')):continue
    meta=next((v for k,v in {'cpi':('INFLACIÓN',3,1),'pce':('INFLACIÓN',3,1),'ppi':('INFLACIÓN',2,1),'unemployment':('EMPLEO',3,-1),'payroll':('EMPLEO',3,1),'employment':('EMPLEO',3,1),'wage':('EMPLEO',2,1),'claims':('EMPLEO',2,-1),'gdp':('CRECIMIENTO',3,1),'retail':('CRECIMIENTO',2,1),'industrial production':('CRECIMIENTO',2,1),'pmi':('CRECIMIENTO',2,1),'ism':('CRECIMIENTO',2,1)}.items() if k in lname),('MACRO',2,0))
    cat,imp,sign=meta; row=next((x for x in inds if x.get('name')==name),None) or {'cat':cat,'name':name,'actual':'','est':'','surprise':'','date':'','imp':'★'*imp,'source':'Trading Economics','rateImpact':sign}
    row.update(actual=str(actual),est=str(forecast or ''),date=str(ev.get('Date') or '')[:16].replace('T',' '),source=ev.get('Source') or 'Trading Economics',rateImpact=sign)
    if forecast not in (None,'') and num(actual) is not None and num(forecast) is not None:row['surprise']=f"{(num(actual)-num(forecast))*sign:+.2f}"
    if row not in inds:inds.append(row)
  except Exception as e:print('TE',eid,e)

def ensure_slots(feed):
 for eco in feed.get('economies',{}).values():
  b=eco.setdefault('bonds',{}); old={x.get('term'):x for x in b.get('tenors',[])}
  b['tenors']=[old.get(t,{'term':t,'yield':'','change':'','isKey':t in ('2Y','10Y'),'note':'No hay benchmark exacto conectado; no se interpola.'}) for t in ['3M','1Y','2Y','5Y','10Y','20Y','30Y']]

def main():
 feed=load();update_us(feed);update_treasury(feed);update_te(feed);ensure_slots(feed);update_risk(feed)
 enrich_feed(feed)
 stamp=datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC');feed['version']=6;feed['updated']=stamp;feed['automation']={'updatedAt':stamp,'runner':'GitHub Actions / update_feed.py','intervalMinutes':15,'notes:['Mercado/Risk-On-Off se refresca cada 15 min cuando Yahoo responde.','Indicadores macro solo cambian cuando se publica un nuevo dato.','Las curvas usan benchmarks reales disponibles; no se interpolan silenciosamente.','COT es semanal; opciones usan gamma proxy; dark pools/OTC son datos agregados y con retraso.']};write(feed);print('Feed actualizado',stamp)

if __name__=='__main__':main()
