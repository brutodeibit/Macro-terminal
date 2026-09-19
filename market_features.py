from __future__ import annotations
import math, os, re, requests
from datetime import datetime, timezone

def gamma(calls, puts, spot):
 vals=[]
 for x in calls:
  oi=x.get("openInterest",0) or 0; g=x.get("gamma",0) or 0
  vals.append((x.get("strike",0), oi*g))
 for x in puts:
  oi=x.get("openInterest",0) or 0; g=x.get("gamma",0) or 0
  vals.append((x.get("strike",0), -oi*g))
 net=sum(v for _,v in vals)
 pos=sum(v for _,v in vals if v>0)
 neg=sum(v for _,v in vals if v<0)
 zero=min((k for k,_ in vals), key=lambda k:abs(k-spot)) if vals else None
 return {"gammaPositive":pos,"gammaNegative":neg,"gammaNet":net,"zeroGamma":zero}

def opt(sym):
 try:
  r=get("https://cdn.cboe.com/api/global/delayed_quotes/options/"+sym+".json",h={"User-Agent":"Mozilla/5.0","Accept":"application/json"}).json()
  d=r.get("data",r); spot=float(d.get("current_price") or 0); rows=d.get("options",[])
  if not rows or not spot:return None
  now=datetime.now(timezone.utc)
  calls=[];puts=[]; expiries=[]
  for x in rows:
   t=str(x.get("option") or "")
   m=re.search(r"([0-9]{6})([CP])([0-9]{8})$",t)
   if not m:continue
   try:
    ex=datetime.strptime("20"+m.group(1),"%Y%m%d").replace(tzinfo=timezone.utc)
    if ex<=now:continue
    strike=int(m.group(3))/1000.0; typ=m.group(2); oi=float(x.get("open_interest") or 0); iv=float(x.get("iv") or 0); gam=float(x.get("gamma") or 0)
    row={"strike":strike,"openInterest":oi,"impliedVolatility":iv,"gamma":gam,"expiration":int(ex.timestamp())}
    (calls if typ=="C" else puts).append(row); expiries.append(ex)
   except Exception:pass
  if not calls and not puts:return None
  nearest=min(expiries) if expiries else now
  calls=[x for x in calls if x["expiration"]==int(nearest.timestamp())]
  puts=[x for x in puts if x["expiration"]==int(nearest.timestamp())]
  co=sum(x["openInterest"] for x in calls);po=sum(x["openInterest"] for x in puts)
  tc=max(calls,key=lambda x:x["openInterest"],default={});tp=max(puts,key=lambda x:x["openInterest"],default={})
  g=gamma(calls,puts,spot)
  return {"name":sym,"ticker":sym,"spot":spot,"expiration":nearest.date().isoformat(),"putCallOi":po/co if co else None,
   "topCallStrike":tc.get("strike"),"topPutStrike":tp.get("strike"),"maxOiStrike":max(calls+puts,key=lambda x:x["openInterest"],default={}).get("strike"),
   "method":"CBOE delayed options chain · OI + quoted gamma; 15 min delayed. Gamma exposure is a modeling proxy, not dealer-position data.",
   "source":"Cboe Global Markets","sourceUrl":"https://www.cboe.com/delayed_quotes/","gammaNote":"Calls positive / puts negative; dealer side is assumed for the proxy.",**g}

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
 cfg=[
  ("S&P 500 E-Mini","gpe5-46if","upper(contract_market_name) like '%E-MINI S&P 500%'",
   ("lev_money_positions_long","lev_money_positions_long_all"),("lev_money_positions_short","lev_money_positions_short_all"),"Leveraged Money"),
  ("Nasdaq-100","gpe5-46if","upper(contract_market_name) like '%NASDAQ-100%'",
   ("lev_money_positions_long","lev_money_positions_long_all"),("lev_money_positions_short","lev_money_positions_short_all"),"Leveraged Money"),
  ("DXY · USD Index","gpe5-46if","upper(contract_market_name) like '%U.S. DOLLAR INDEX%'",
   ("lev_money_positions_long","lev_money_positions_long_all"),("lev_money_positions_short","lev_money_positions_short_all"),"Leveraged Money"),
  ("Euro FX","gpe5-46if","upper(contract_market_name) like '%EURO FX%'",
   ("lev_money_positions_long","lev_money_positions_long_all"),("lev_money_positions_short","lev_money_positions_short_all"),"Leveraged Money"),
  ("Oro","72hh-3qpy","upper(contract_market_name) like '%GOLD%' and upper(contract_market_name) not like '%MINI%'",
   ("m_money_positions_long_all","m_money_positions_long"),("m_money_positions_short_all","m_money_positions_short"),"Managed Money"),
  ("Plata","72hh-3qpy","upper(contract_market_name) like '%SILVER%' and upper(contract_market_name) not like '%MINI%'",
   ("m_money_positions_long_all","m_money_positions_long"),("m_money_positions_short_all","m_money_positions_short"),"Managed Money"),
  ("Petróleo WTI","72hh-3qpy","upper(contract_market_name) like '%WTI%' and upper(contract_market_name) like '%CRUDE%'",
   ("m_money_positions_long_all","m_money_positions_long"),("m_money_positions_short_all","m_money_positions_short"),"Managed Money"),
  ("Brent","72hh-3qpy","upper(contract_market_name) like '%BRENT%'",
   ("m_money_positions_long_all","m_money_positions_long"),("m_money_positions_short_all","m_money_positions_short"),"Managed Money")
 ]
 out=[]; errors=[]
 for name,ds,w,L,S,group in cfg:
  rows=cot_rows(ds,w)
  if not rows:
   errors.append(name)
   continue
  x=cot_one(rows,name,L,S)
  if x:
   x["traderGroup"]=group
   x["contract"]=str(rows[0].get("contract_market_name") or rows[0].get("commodity_name") or "")
   x["openInterest"]=num(rows[0].get("open_interest_all"))
   out.append(x)
  else: errors.append(name)
 if out:
  feed["cot"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,
   "source":"CFTC Public Reporting Environment","method":"COT semanal; Managed Money para commodities y Leveraged Money para índices/divisas; z-score frente a hasta 52 observaciones.",
   "sourceUrl":"https://publicreporting.cftc.gov/","errors":errors}
def finra_access_token():
 try:
  client_id=os.getenv("FINRA_API_CLIENT_ID")
  client_secret=os.getenv("FINRA_API_CLIENT_SECRET")
  if client_id and client_secret:
   r=requests.post("https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token",params={"grant_type":"client_credentials"},auth=(client_id,client_secret),headers={"User-Agent":"MacroTerminal/6.0","Accept":"application/json"},timeout=T)
   r.raise_for_status()
   return r.json().get("access_token")
  return os.getenv("FINRA_API_TOKEN")
 except Exception as e:
  print("FINRA AUTH",type(e).__name__,str(e)[:180])
  return None

def update_dark_pools(feed):
 token=finra_access_token()
 if not token:return
 out=[]
 for sym in ("SPY","QQQ","HYG","GLD","USO","AAPL","NVDA"):
  try:
   payload={"limit":500,"fields":["issueSymbolIdentifier","issueName","MPID","marketParticipantName","summaryStartDate","weekStartDate","totalWeeklyTradeCount","totalWeeklyShareQuantity","summaryTypeCode","lastUpdateDate"],"compareFilters":[{"compareType":"equal","fieldName":"issueSymbolIdentifier","fieldValue":sym}]}
   d=post("https://api.finra.org/data/group/OTCMarket/name/weeklySummary",payload,{"Authorization":"Bearer "+token,"Content-Type":"application/json","Accept":"application/json","Data-API-Version":"1"}).json()
   if not d:continue
   w=max(str(x.get("weekStartDate") or x.get("summaryStartDate") or "") for x in d);cur=[x for x in d if str(x.get("weekStartDate") or x.get("summaryStartDate") or "")==w];ats=sum(float(x.get("totalWeeklyShareQuantity") or 0) for x in cur if str(x.get("summaryTypeCode") or "").upper().startswith("ATS"));otc=sum(float(x.get("totalWeeklyShareQuantity") or 0) for x in cur if not str(x.get("summaryTypeCode") or "").upper().startswith("ATS"));out.append({"symbol":sym,"weekStart":w,"atsShares":ats,"otcShares":otc,"totalOffExchange":ats+otc,"zScore":None,"topVenues":[],"lagLabel":"FINRA · semanal / con retraso","note":"Actividad OTC/ATS agregada; no implica acumulación por precio."})
  except Exception:pass
 if out:feed["darkPools"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"source":"FINRA OTC Transparency","sourceUrl":"https://www.finra.org/filing-reporting/otc-transparency"}
def enrich_feed(feed):
 for name,fn in (("FX",update_fx),("COT",update_cot),("OPTIONS",update_options),("DARK_POOLS",update_dark_pools)):
  try:
   fn(feed)
  except Exception as e:
   print(name,type(e).__name__,str(e)[:180])

