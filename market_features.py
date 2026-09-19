from __future__ import annotations
import math, os, re, requests
from datetime import datetime, timezone
H={"User-Agent":"MacroTerminal/6.0","Accept-Language":"en-US,en;q=0.9"}; T=25
def get(u,p=None,h=None):
 x=dict(H); x.update(h or {}); r=requests.get(u,params=p or {},headers=x,timeout=T); r.raise_for_status(); return r
def post(u,j,h=None):
 x=dict(H); x.update(h or {}); r=requests.post(u,json=j,headers=x,timeout=T); r.raise_for_status(); return r
def num(v):
 try:return float(re.sub(r"[^0-9+.-]","",str(v).replace(",",""))) if v not in (None,"") else None
 except:return None
def zscore(a,c):
 a=[float(x) for x in a if x is not None]
 if len(a)<8:return None
 m=sum(a)/len(a); sd=(sum((x-m)**2 for x in a)/max(1,len(a)-1))**.5
 return (c-m)/sd if sd else 0
def chart(sym):
 try:return (get("https://query1.finance.yahoo.com/v8/finance/chart/"+requests.utils.quote(sym,safe=""),{"range":"3mo","interval":"1d"}).json().get("chart",{}).get("result") or [None])[0]
 except Exception:return None
def update_fx(feed):
 sy={"EUR":"EURUSD=X","GBP":"GBPUSD=X","JPY":"USDJPY=X","AUD":"AUDUSD=X","NZD":"NZDUSD=X","CAD":"USDCAD=X","CHF":"USDCHF=X"}; out={"USD":{"pair":"—","change1d":0,"change5d":0,"change20d":0}}
 for c,s in sy.items():
  try:
   q=chart(s)["indicators"]["quote"][0]["close"]; q=[float(x) for x in q if x is not None]; last=q[-1]; a=[(last/q[-2]-1)*100,(last/q[-6]-1)*100,(last/q[-21]-1)*100]
   if c in ("JPY","CAD","CHF"): a=[-x for x in a]
   out[c]={"pair":s,"last":last,"change1d":a[0],"change5d":a[1],"change20d":a[2]}
  except Exception:pass
 feed["fx"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"currencies":out,"method":"Fuerza frente a USD normalizada; se combina con política, 2Y, tipo real y tendencia."}
def cot_rows(dataset,where):
 try:
  h={"X-App-Token":os.getenv("CFTC_APP_TOKEN")} if os.getenv("CFTC_APP_TOKEN") else {}
  return get("https://publicreporting.cftc.gov/resource/"+dataset+".json",{"$limit":"60","$order":"report_date_as_yyyy_mm_dd DESC","$where":where},h).json()
 except Exception:return []
def cot_one(rows,label,longs,shorts):
 if not rows:return None
 def p(r,ks):
  for k in ks:
   v=num(r.get(k))
   if v is not None:return v
 lv=p(rows[0],longs);sv=p(rows[0],shorts)
 if lv is None or sv is None:return None
 hist=[p(r,longs)-p(r,shorts) for r in rows if p(r,longs) is not None and p(r,shorts) is not None]; net=lv-sv
 return {"name":label,"reportDate":str(rows[0].get("report_date_as_yyyy_mm_dd",""))[:10],"net":net,"long":lv,"short":sv,"zScore":zscore(hist,net),"netChange":net-(hist[1] if len(hist)>1 else net),"reading":("Largos netos" if net>0 else "Cortos netos")}
def update_cot(feed):
 cfg=[("S&P 500 E-Mini","gpe5-46if","upper(contract_market_name) like '%S&P 500%'"),("Nasdaq-100","gpe5-46if","upper(contract_market_name) like '%NASDAQ%'"),("Oro","8jj7-5vf4","upper(commodity_name) like '%GOLD%'"),("Petróleo WTI","8jj7-5vf4","upper(commodity_name) like '%CRUDE OIL%'")]; out=[]
 for name,ds,w in cfg:
  rows=cot_rows(ds,w)
  # TFF leverage-money fields for indices; legacy noncommercial for commodities.
  if ds=="gpe5-46if": L=("lev_money_positions_long","lev_money_positions_long_all");S=("lev_money_positions_short","lev_money_positions_short_all")
  else:L=("noncomm_positions_long_all","noncomm_positions_long");S=("noncomm_positions_short_all","noncomm_positions_short")
  x=cot_one(rows,name,L,S)
  if x:out.append(x)
 if out:feed["cot"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"source":"CFTC Public Reporting Environment","method":"COT semanal; z-score frente a hasta 52 observaciones.","sourceUrl":"https://publicreporting.cftc.gov/"}
def gamma(calls,puts,spot):
 by={}; now=int(datetime.now(timezone.utc).timestamp())
 for typ,rows in (("call",calls),("put",puts)):
  for r in rows:
   try:
    k=float(r.get("strike") or 0);oi=float(r.get("openInterest") or 0);iv=float(r.get("impliedVolatility") or 0);ex=int(r.get("expiration") or 0)
    if not k or not oi or not iv or ex<=now:continue
    t=max((ex-now)/(365*86400),1/365);d1=(math.log(spot/k)+.5*iv*iv*t)/(iv*t**.5);g=math.exp(-.5*d1*d1)/(2*math.pi)**.5/(spot*iv*t**.5);v=g*oi*100*spot*spot*.01*(1 if typ=="call" else -1);by[k]=by.get(k,0)+v
   except Exception:pass
 pos=[x for x in by.items() if x[1]>0];neg=[x for x in by.items() if x[1]<0];o=sorted(by.items());zg=None
 for (a,x),(b,y) in zip(o,o[1:]):
  if (x<=0<=y) or (y<=0<=x):zg=(a+b)/2;break
 return {"gammaPositive":sum(v for _,v in pos) if pos else None,"gammaNegative":sum(v for _,v in neg) if neg else None,"gammaTotal":sum(by.values()) if by else None,"zeroGamma":zg,"positiveZones":[{"strike":k,"gamma":v} for k,v in sorted(pos,key=lambda x:x[1],reverse=True)[:4]],"negativeZones":[{"strike":k,"gamma":v} for k,v in sorted(neg,key=lambda x:x[1])[:4]]}
def opt(sym):
 try:
  base="https://query2.finance.yahoo.com/v7/finance/options/"+sym;r=get(base).json()["optionChain"]["result"][0];ex=r["expirationDates"][0];r=get(base,{"date":ex}).json()["optionChain"]["result"][0];o=r["options"][0];c=o.get("calls",[]);p=o.get("puts",[]);spot=float(r["quote"]["regularMarketPrice"])
  for x in c+p:x["expiration"]=ex
  co=sum(float(x.get("openInterest") or 0) for x in c);po=sum(float(x.get("openInterest") or 0) for x in p);tc=max(c,key=lambda x:float(x.get("openInterest") or 0),default={});tp=max(p,key=lambda x:float(x.get("openInterest") or 0),default={});g=gamma(c,p,spot)
  return {"name":sym,"ticker":sym,"spot":spot,"expiration":datetime.fromtimestamp(ex,tz=timezone.utc).date().isoformat(),"putCallOi":po/co if co else None,"topCallStrike":tc.get("strike"),"topPutStrike":tp.get("strike"),"maxOiStrike":max(c+p,key=lambda x:float(x.get("openInterest") or 0),default={}).get("strike"),"method":"OI + gamma proxy Black-Scholes; no es GEX propietario.","source":"Yahoo Finance","sourceUrl":"https://finance.yahoo.com/",**g}
 except Exception:return None
def update_options(feed):
 out=[x for s in ("SPY","QQQ","GLD","USO") if (x:=opt(s))]
 if out:feed["options"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"method":"Opciones públicas; gamma estimada, no GEX propietario."}
def finra_access_token():
 client_id=os.getenv("FINRA_API_CLIENT_ID")
 client_secret=os.getenv("FINRA_API_CLIENT_SECRET")
 if client_id and client_secret:
  r=requests.post(
   "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token",
   params={"grant_type":"client_credentials"},
   auth=(client_id,client_secret),
   headers={"User-Agent":"MacroTerminal/6.0","Accept":"application/json"},
   timeout=T
  )
  r.raise_for_status()
  return r.json().get("access_token")
 return os.getenv("FINRA_API_TOKEN")

def update_dark_pools(feed):
 token=finra_access_token()
 if not token:return
 out=[]
 for sym in ("SPY","QQQ","HYG","GLD","USO","AAPL","NVDA"):
  try:
   payload={"limit":500,"fields":["issueSymbolIdentifier","issueName","MPID","marketParticipantName","summaryStartDate","weekStartDate","totalWeeklyTradeCount","totalWeeklyShareQuantity","summaryTypeCode","lastUpdateDate"],"compareFilters":[{"compareType":"equal","fieldName":"issueSymbolIdentifier","fieldValue":sym}]}
   d=post("https://api.finra.org/data/group/OTCMarket/name/weeklySummary",payload,{"Authorization":"Bearer "+token,"Content-Type":"application/json"}).json()
   if not d:continue
   w=max(str(x.get("weekStartDate") or x.get("summaryStartDate") or "") for x in d);cur=[x for x in d if str(x.get("weekStartDate") or x.get("summaryStartDate") or "")==w];ats=sum(float(x.get("totalWeeklyShareQuantity") or 0) for x in cur if str(x.get("summaryTypeCode") or "").upper().startswith("ATS"));otc=sum(float(x.get("totalWeeklyShareQuantity") or 0) for x in cur if not str(x.get("summaryTypeCode") or "").upper().startswith("ATS"));out.append({"symbol":sym,"weekStart":w,"atsShares":ats,"otcShares":otc,"totalOffExchange":ats+otc,"zScore":None,"topVenues":[],"lagLabel":"FINRA · semanal / con retraso","note":"Actividad OTC/ATS agregada; no implica acumulación por precio."})
  except Exception:pass
 if out:feed["darkPools"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"source":"FINRA OTC Transparency","sourceUrl":"https://www.finra.org/filing-reporting/otc-transparency"}
def enrich_feed(feed):
 update_fx(feed);update_cot(feed);update_options(feed);update_dark_pools(feed)
