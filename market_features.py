from __future__ import annotations
import json, math, os, re, requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

def _norm_pdf(x):
 try:return math.exp(-0.5*x*x)/math.sqrt(2*math.pi)
 except Exception:return None

def _vanna_proxy(spot,strike,iv,t):
 """Black-Scholes vanna proxy: dDelta/dVol. Not dealer positioning."""
 try:
  if not spot or not strike or not iv or not t:return None
  sig=float(iv); 
  if sig>3:sig/=100.0
  if sig<=0:return None
  sq=math.sqrt(max(t,1e-9))
  d1=(math.log(spot/strike)+0.5*sig*sig*t)/(sig*sq)
  d2=d1-sig*sq
  return _norm_pdf(d1)*(-d2/sig)
 except Exception:return None

def _option_gex(calls,puts,spot):
 scale=float(spot or 0)**2*0.01*100.0
 vals=[]; posZones=[]; negZones=[]; callWall=None; putWall=None
 for x in calls:
  v=float(x.get("openInterest",0) or 0)*float(x.get("gamma",0) or 0)*scale
  vals.append((float(x.get("strike") or 0),v)); posZones.append({"strike":x.get("strike"),"gamma":v})
  if callWall is None or v>callWall["gamma"]: callWall={"strike":x.get("strike"),"gamma":v}
 for x in puts:
  v=-float(x.get("openInterest",0) or 0)*float(x.get("gamma",0) or 0)*scale
  vals.append((float(x.get("strike") or 0),v)); negZones.append({"strike":x.get("strike"),"gamma":v})
  if putWall is None or abs(v)>abs(putWall["gamma"]): putWall={"strike":x.get("strike"),"gamma":v}
 net=sum(v for _,v in vals); pos=sum(v for _,v in vals if v>0); neg=sum(v for _,v in vals if v<0)
 agg=sorted(vals,key=lambda z:z[0]); cum=0.0; prev_k=None; prev_cum=0.0; flip=None
 for k,v in agg:
  nxt=cum+v
  if cum*nxt<0 and prev_k is not None:
   den=nxt-cum
   flip=prev_k+((0-cum)/den)*(k-prev_k) if den else k
   break
  prev_k,prev_cum=k,cum
  cum=nxt
 regime="NEGATIVE · potencial amplificación" if net<0 else "POSITIVE · potencial estabilización" if net>0 else "NEUTRAL"
 effect="Los hedges modelados pueden reforzar el movimiento" if net<0 else "Los hedges modelados pueden amortiguar el movimiento" if net>0 else "Sin sesgo de gamma agregado"
 return {
  "gammaPositive":pos,"gammaNegative":neg,"gammaNet":net,"gammaTotal":net,
  "gammaRegime":regime,"gammaEffect":effect,"zeroGamma":flip,
  "callWall":callWall.get("strike") if callWall else None,
  "putWall":putWall.get("strike") if putWall else None,
  "positiveZones":sorted(posZones,key=lambda x:x["gamma"],reverse=True)[:8],
  "negativeZones":sorted(negZones,key=lambda x:abs(x["gamma"]),reverse=True)[:8]
 }

def _option_summary(rows,spot,expiration,oi_prev=None):
 calls=[x for x in rows if x.get("type")=="C"]; puts=[x for x in rows if x.get("type")=="P"]
 ex=max(0,(expiration-datetime.now(timezone.utc)).total_seconds()/86400.0)
 co=sum(float(x.get("openInterest",0) or 0) for x in calls); po=sum(float(x.get("openInterest",0) or 0) for x in puts)
 cv=sum(float(x.get("volume",0) or 0) for x in calls); pv=sum(float(x.get("volume",0) or 0) for x in puts)
 gp=_option_gex(calls,puts,spot)
 atm_calls=sorted(calls,key=lambda x:abs(float(x.get("strike") or 0)-spot))[:3]
 atm_puts=sorted(puts,key=lambda x:abs(float(x.get("strike") or 0)-spot))[:3]
 ivs=[float(x.get("iv") or 0) for x in (atm_calls[:1]+atm_puts[:1]) if float(x.get("iv") or 0)>0]
 iv_atm=sum(ivs)/len(ivs) if ivs else None
 if iv_atm and iv_atm>3:iv_atm/=100.0
 expected=spot*iv_atm*math.sqrt(max(ex,0)/365.0) if iv_atm else None
 dex=None;vanna=None;charm_vals=[];total_oi=co+po;gex_by=[]
 for x in rows:
  oi=float(x.get("openInterest",0) or 0); delta=x.get("delta"); gamma=float(x.get("gamma",0) or 0)
  if delta is not None:dex=(dex or 0)+oi*float(delta)*spot*100.0
  iv=float(x.get("iv") or 0); k=float(x.get("strike") or 0)
  if x.get("vanna") is not None:
   vanna=(vanna or 0)+oi*float(x["vanna"])*100.0
  else:
   vp=_vanna_proxy(spot,k,iv,max(ex,0)/365.0)
   if vp is not None:vanna=(vanna or 0)+oi*vp*100.0
  if x.get("charm") is not None:charm_vals.append(oi*float(x["charm"])*100.0)
  sign=1 if x.get("type")=="C" else -1
  gex_by.append({"strike":x.get("strike"),"gex":sign*oi*gamma*(spot**2)*0.01*100.0})
 oi_delta=None;largest_oi_change=None
 if oi_prev:
  oi_delta=sum(float(x.get("openInterest",0) or 0)-float(oi_prev.get(x.get("key"),0) or 0) for x in rows)
  changes=[]
  for x in rows:
   k=x.get("key")
   if k in oi_prev:
    d=float(x.get("openInterest",0) or 0)-float(oi_prev.get(k,0) or 0)
    changes.append({"strike":x.get("strike"),"type":x.get("type"),"change":d})
  if changes:largest_oi_change=max(changes,key=lambda z:abs(z["change"]))
 charm=sum(charm_vals) if charm_vals else None
 return {
  "expiration":expiration.date().isoformat(),"daysToExpiry":round(ex,2),
  "callOi":co,"putOi":po,"putCallOi":po/co if co else None,
  "callVolume":cv,"putVolume":pv,"putCallVolume":pv/cv if cv else None,
  "totalVolume":cv+pv,"totalOpenInterest":total_oi,
  "ivAtm":iv_atm*100 if iv_atm else None,"expectedMove":expected,
  "dexProxy":dex,"vannaProxy":vanna,"charm":charm,
  "oiChange":oi_delta,"largestOiChange":largest_oi_change,
  **gp,
  "topGexStrikes":sorted(gex_by,key=lambda z:abs(z["gex"]),reverse=True)[:10]
 }

def _norm_pdf(x): return math.exp(-0.5*x*x)/math.sqrt(2*math.pi)
def _norm_cdf(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def _bs_greeks(S,K,T,sigma,r,typ):
 if not S or not K or T<=0 or not sigma or sigma<=0:return (None,None,None,None)
 try:
  d1=(math.log(S/K)+(r+0.5*sigma*sigma)*T)/(sigma*math.sqrt(T)); d2=d1-sigma*math.sqrt(T)
  delta=_norm_cdf(d1) if typ=="C" else _norm_cdf(d1)-1
  gamma=_norm_pdf(d1)/(S*sigma*math.sqrt(T))
  # Approximate vanna/charm proxies; useful as directional exposure estimates, not dealer-book observations.
  vanna=-math.exp(-r*T)*_norm_pdf(d1)*d2/sigma
  charm=-(math.exp(-r*T)*_norm_pdf(d1)*(2*r*T-d2*sigma*math.sqrt(T))/(2*T*sigma*math.sqrt(T)))
  if typ=="P": charm=-charm
  return delta,gamma,vanna,charm
 except Exception:return (None,None,None,None)

def _yahoo_option_chain(sym,expiration=None):
 u="https://query1.finance.yahoo.com/v7/finance/options/"+requests.utils.quote(sym,safe="")
 params={"date":str(int(expiration))} if expiration else {}
 j=get(u,params).json().get("optionChain",{}).get("result",[])
 return j[0] if j else None

def opt(sym):
 try:
  base=_yahoo_option_chain(sym)
  if not base:return None
  spot=num(base.get("quote",{}).get("regularMarketPrice") or base.get("quote",{}).get("postMarketPrice"))
  expirations=[int(x) for x in (base.get("expirationDates") or [])]
  now=datetime.now(timezone.utc)
  expirations=[x for x in expirations if datetime.fromtimestamp(x,tz=timezone.utc)>now]
  if not spot or not expirations:return None
  monthly=[]
  for ex in expirations:
   d=datetime.fromtimestamp(ex,tz=timezone.utc)
   if d.weekday()==4 and 15<=d.day<=21:monthly.append(ex)
  selected=[expirations[0]]
  if monthly and monthly[0] not in selected:selected.append(monthly[0])
  profiles=[]
  all_raw=[]
  for ex in selected:
   chain=_yahoo_option_chain(sym,ex)
   if not chain:continue
   rows=[]
   for typ,key in (("C","calls"),("P","puts")):
    for x in chain.get(key,[]) or []:
     K=num(x.get("strike"));oi=num(x.get("openInterest")) or 0;vol=num(x.get("volume")) or 0;iv=num(x.get("impliedVolatility")) or 0
     if not K or iv<=0:continue
     T=max((ex-datetime.now(timezone.utc).timestamp())/(365*86400),1/3650)
     delta,gamma,vanna,charm=_bs_greeks(spot,K,T,iv,0.04,typ)
     rows.append({"strike":K,"openInterest":oi,"volume":vol,"iv":iv,"gamma":gamma,"delta":delta,"vanna":vanna,"charm":charm,"type":typ,"expiration":ex})
   if rows:
    profiles.append(_option_summary(rows,spot,datetime.fromtimestamp(ex,tz=timezone.utc)))
    all_raw.extend(rows)
  if not profiles:return None
  # Add actual call/put OI and volume ratios to the nearest profile.
  for p in profiles:
   ex=int(datetime.fromisoformat(p["expiration"]).replace(tzinfo=timezone.utc).timestamp())
   rr=[x for x in all_raw if x["expiration"]==ex]
   coi=sum(x["openInterest"] for x in rr if x["type"]=="C");poi=sum(x["openInterest"] for x in rr if x["type"]=="P")
   cv=sum(x["volume"] for x in rr if x["type"]=="C");pv=sum(x["volume"] for x in rr if x["type"]=="P")
   p["putCallOi"]=poi/coi if coi else None;p["putCallVol"]=pv/cv if cv else None
   p["totalVolume"]=cv+pv
  monthly_exp=monthly[0] if monthly else selected[-1]
  return {"name":("USO · ETF proxy WTI" if sym=="USO" else sym),"ticker":sym,"spot":spot,
    "expiration":datetime.fromtimestamp(selected[0],tz=timezone.utc).date().isoformat(),
    "monthlyExpiration":datetime.fromtimestamp(monthly_exp,tz=timezone.utc).date().isoformat(),
    "profiles":profiles,"method":"Yahoo Finance option chain · OI/volume + Black-Scholes Greeks; GEX/DEX/Vanna/Charm are modelled proxies, not observed dealer positioning.",
    "source":"Yahoo Finance public option chain","sourceUrl":"https://finance.yahoo.com/quote/"+sym+"/options/",
    "gammaNote":"Gamma/DEX/Vanna/Charm are calculated from public OI, IV and model Greeks. Dealer side is not directly observable."}
 except Exception as e:
  print("OPTIONS_CHAIN",sym,type(e).__name__,str(e)[:180]); return None


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
 sy={"EUR":"EURUSD=X","GBP":"GBPUSD=X","JPY":"USDJPY=X","AUD":"AUDUSD=X","NZD":"NZDUSD=X","CAD":"USDCAD=X","CHF":"USDCHF=X"}
 out={"USD":{"pair":"—","change1d":0,"change1w":0,"change15d":0,"change1m":0}}
 for c,sym in sy.items():
  try:
   r=chart(sym); q=[float(x) for x in (r or {}).get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
   if len(q)<22:continue
   last=q[-1]; a1=(last/q[-2]-1)*100; w=(last/q[-6]-1)*100; d15=(last/q[-16]-1)*100; m=(last/q[-22]-1)*100
   if c in ("JPY","CAD","CHF"):a1,w,d15,m=[-x for x in (a1,w,d15,m)]
   out[c]={"pair":sym,"last":last,"change1d":a1,"change1w":w,"change15d":d15,"change1m":m}
  except Exception as e:print("FX",c,type(e).__name__,str(e)[:120])
 feed["fx"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"currencies":out,
   "method":"Fuerza frente a USD normalizada. Variaciones: 1D, 1S (~5 sesiones), 15D (~3 semanas de mercado) y 1M (~21 sesiones). Se combina con política, 2Y, tipo real y tendencia."}


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
  ("S&P 500 E-Mini","gpe5-46if","13874A",("lev_money_positions_long_all","lev_money_positions_long"),("lev_money_positions_short_all","lev_money_positions_short"),"Leveraged Funds","TFF"),
  ("Nasdaq-100","gpe5-46if","209742",("lev_money_positions_long_all","lev_money_positions_long"),("lev_money_positions_short_all","lev_money_positions_short"),"Leveraged Funds","TFF"),
  ("Dow Jones","gpe5-46if","124603",("lev_money_positions_long_all","lev_money_positions_long"),("lev_money_positions_short_all","lev_money_positions_short"),"Leveraged Funds","TFF"),
  ("DXY · USD Index","gpe5-46if","098662",("lev_money_positions_long_all","lev_money_positions_long"),("lev_money_positions_short_all","lev_money_positions_short"),"Leveraged Funds","TFF"),
  ("Euro FX","gpe5-46if","099741",("lev_money_positions_long_all","lev_money_positions_long"),("lev_money_positions_short_all","lev_money_positions_short"),"Leveraged Funds","TFF"),
  ("Oro","72hh-3qpy","088691",("m_money_positions_long_all","m_money_positions_long"),("m_money_positions_short_all","m_money_positions_short"),"Managed Money","Disaggregated"),
  ("Plata","72hh-3qpy","084691",("m_money_positions_long_all","m_money_positions_long"),("m_money_positions_short_all","m_money_positions_short"),"Managed Money","Disaggregated"),
  ("WTI","72hh-3qpy","067651",("m_money_positions_long_all","m_money_positions_long"),("m_money_positions_short_all","m_money_positions_short"),"Managed Money","Disaggregated"),
  ("Brent","72hh-3qpy","06765T",("m_money_positions_long_all","m_money_positions_long"),("m_money_positions_short_all","m_money_positions_short"),"Managed Money","Disaggregated")
 ]
 out=[];errors=[]
 for name,ds,code,L,S,group,fam in cfg:
  rows=cot_rows(ds,"cftc_contract_market_code='"+code+"'")
  x=cot_one(rows,name,L,S) if rows else None
  if x:
   x.update(traderGroup=group,reportFamily=fam,contractCode=code,contract=str(rows[0].get("contract_market_name") or rows[0].get("market_and_exchange_names") or ""),openInterest=num(rows[0].get("open_interest_all")))
   out.append(x)
  else: errors.append(name)
 if out:feed["cot"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"source":"CFTC Public Reporting Environment","method":"COT semanal; Leveraged Funds para índices/divisas TFF y Managed Money para commodities Disaggregated; filtrado por código CFTC.","sourceUrl":"https://publicreporting.cftc.gov/","errors":errors}

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

def update_options(feed):
 out=[]
 previous=feed.get("options",{}).get("markets",[]) if isinstance(feed.get("options"),dict) else []
 prev_map={}
 for m in previous:
  for p in (m.get("profiles") or []):
   for zone in (p.get("topGexStrikes") or []):
    pass
 for sym in ("SPY","QQQ","DIA","GLD","SLV","USO","BNO","UUP","FXE","AAPL","NVDA","IWM"):
  try:
   x=opt(sym)
   if x:out.append(x)
  except Exception as e:print("OPTIONS",sym,type(e).__name__,str(e)[:180])
 if out:
  hist=dict(feed.get("options",{}).get("history") or {}) if isinstance(feed.get("options"),dict) else {}
  stamp=datetime.now(timezone.utc).isoformat()
  for m in out:
   arr=hist.get(m["ticker"],[])
   snap={"asOf":stamp,"expiration":m.get("expiration"),"spot":m.get("spot"),
         "gammaNet":(m.get("profiles") or [{}])[0].get("gammaNet"),
         "zeroGamma":(m.get("profiles") or [{}])[0].get("zeroGamma"),
         "callWall":(m.get("profiles") or [{}])[0].get("callWall"),
         "putWall":(m.get("profiles") or [{}])[0].get("putWall"),
         "ivAtm":(m.get("profiles") or [{}])[0].get("ivAtm"),
         "expectedMove":(m.get("profiles") or [{}])[0].get("expectedMove")}
   arr=[h for h in arr if not (h.get("expiration")==snap.get("expiration") and h.get("asOf","")[:10]==stamp[:10] and abs(float(h.get("spot") or 0)-float(snap.get("spot") or 0))<0.0001)]
   arr.append(snap);hist[m["ticker"]]=arr[-64:]
  feed["options"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"history":hist,"source":"Cboe Global Markets","sourceUrl":"https://www.cboe.com/delayed_quotes/","note":"Cadena retrasada; GEX/DEX/Vanna/Charm son proxies basados en datos públicos y supuestos de posicionamiento. Se conserva historial intradía."}

def update_dark_pools(feed):
 token=finra_access_token()
 if not token:return
 out=[]; old=feed.get("darkPools",{}) if isinstance(feed.get("darkPools"),dict) else {}
 old_hist=dict(old.get("history") or {})
 for sym in ("SPY","QQQ","GLD","USO","AAPL","NVDA","HYG"):
  ats=otc=at=ot=0.0; last=""; week=None; ok=False
  for typ in ("ATS_W_SMBL","OTC_W_SMBL"):
   try:
    payload={"limit":60,"fields":["issueSymbolIdentifier","issueName","weekStartDate","summaryStartDate","totalWeeklyTradeCount","totalWeeklyShareQuantity","lastUpdateDate","tierIdentifier","summaryTypeCode"],"compareFilters":[
      {"compareType":"equal","fieldName":"tierIdentifier","fieldValue":"T1"},
      {"compareType":"equal","fieldName":"summaryTypeCode","fieldValue":typ},
      {"compareType":"equal","fieldName":"issueSymbolIdentifier","fieldValue":sym}]}
    d=post("https://api.finra.org/data/group/OTCMarket/name/weeklySummary",payload,{"Authorization":"Bearer "+token,"Content-Type":"application/json","Accept":"application/json","Data-API-Version":"1"}).json()
    rows=[x for x in (d if isinstance(d,list) else []) if x.get("weekStartDate")]
    rows=sorted(rows,key=lambda x:str(x.get("weekStartDate")),reverse=True)
    if not rows:continue
    if week is None:week=rows[0].get("weekStartDate")
    target=[x for x in rows if x.get("weekStartDate")==week]
    qty=sum(float(row.get("totalWeeklyShareQuantity") or 0) for row in target)
    tr=sum(float(row.get("totalWeeklyTradeCount") or 0) for row in target)
    lu=max(str(row.get("lastUpdateDate") or "") for row in target)
    ok=True
    if typ=="ATS_W_SMBL":ats+=qty;at+=tr
    else:otc+=qty;ot+=tr
    last=max(last,lu)
   except Exception as e:print("FINRA",sym,typ,type(e).__name__,str(e)[:160])
  if ok and week and (ats or otc):
   found={"symbol":sym,"weekStart":str(week)[:10],"lastUpdateDate":last,"atsShares":ats,"otcShares":otc,"totalOffExchange":ats+otc,
          "atsTrades":at,"otcTrades":ot,"avgSharesPerTrade":(ats+otc)/(at+ot) if (at+ot) else None,
          "zScore":None,"topVenues":[],"lagLabel":"FINRA · semanal / retrasado",
          "note":"FINRA ATS/OTC agregado por ticker. No publica aquí la dirección compradora/vendedora ni una secuencia de prints por precio."}
   arr=old_hist.get(sym,[])
   # Evitar referencia circular: un snapshot no puede contener su propio history.
   clean_hist=[]
   for h in arr:
    if not isinstance(h,dict): continue
    clean_hist.append({k:v for k,v in h.items() if k not in ("history","zScore")})
   snapshot={k:v for k,v in found.items() if k not in ("history","zScore")}
   clean_hist=[h for h in clean_hist if h.get("weekStart")!=found["weekStart"]]
   clean_hist.append(snapshot)
   clean_hist=sorted(clean_hist,key=lambda x:x.get("weekStart",""))[-12:]
   hist_vals=[x.get("totalOffExchange") for x in clean_hist]
   found["zScore"]=zscore(hist_vals,found["totalOffExchange"])
   found["history"]=clean_hist
   old_hist[sym]=clean_hist
   out.append(found)
 if out:
  feed["darkPools"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"history":old_hist,
    "source":"FINRA OTC Transparency","sourceUrl":"https://www.finra.org/filing-reporting/otc-transparency",
    "method":"Weekly Summary production dataset · última semana disponible por ticker; historial rodante de 12 semanas.",
    "coverage":"Rolling 12 months in FINRA weeklySummary."}

def update_dark_flow_radar(feed):
 try:
  html=get("https://squawkflow.com/dark-pool-flow").text
  soup=BeautifulSoup(html,"html.parser")
  text=" ".join(soup.stripped_strings)
  def rx(pattern):
   m=re.search(pattern,text,re.I|re.S);return m.group(1).strip() if m else None
  tracked=rx(r"TRACKED NOTIONAL\s+\$([0-9.,]+[KMB]?)")
  largest=rx(r"LARGEST MODELED\s+\$([0-9.,]+[KMB]?)")
  buy=rx(r"BUY-SIDE ESTIMATE\s+([0-9]+(?:\.[0-9]+)?)%")
  dix=rx(r"DIX\s+([0-9]+(?:\.[0-9]+)?)%")
  dix_date=None
  m=re.search(r"DIX\s+(?:BULLISH|BEARISH|NEUTRAL).*?([0-9]+(?:\.[0-9]+)?)%\s*\((\d{4}-\d{2}-\d{2})\)",text,re.I|re.S)
  if m:dix=m.group(1);dix_date=m.group(2)
  signals=[]
  for tr in soup.select("table tr"):
   cells=[c.get_text(" ",strip=True) for c in tr.find_all(["th","td"])]
   if len(cells)>=4 and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,6}",cells[0] or ""):
    if cells[1].startswith("$") and "$" in cells[3]:
     signals.append({"symbol":cells[0],"price":cells[1],"shares":cells[2],"notional":cells[3]})
  feed["darkFlowRadar"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
    "source":"SquawkFlow","sourceUrl":"https://squawkflow.com/dark-pool-flow","dataStatus":"MODELED · NOT PRINTS",
    "trackedNotional":"$"+(tracked or "—"),"buySideEstimate":float(buy) if buy else None,
    "largestModeled":"$"+(largest or "—"),"dix":float(dix) if dix else None,"dixDate":dix_date,
    "signals":signals[:15],
    "note":"Buy/sell and block rows are modelados por SquawkFlow a partir de precios/mercado; no son ejecuciones FINRA observadas. DIX es una serie separada."}
 except Exception as e:
  print("SQUAWK DARK FLOW",type(e).__name__,str(e)[:180])

def update_squawkflow(feed):
 out={}
 headers={"Accept":"application/json","User-Agent":"MacroTerminal/6.0"}
 for key,path,params in (
   ("spxGex","/api/v1/gex/spx",None),
   ("vixTerm","/api/public/vix-term-structure",None),
   ("unusualOptions","/api/v1/options/flow/unusual",{"limit":"12"})
 ):
  try:
   r=get("https://api.squawkflow.com"+path,params,headers).json()
   if r.get("success") is not False:out[key]={"data":r.get("data"),"meta":r.get("meta"),"source":"SquawkFlow","sourceUrl":"https://squawkflow.com/docs/endpoints"}
  except Exception as e:print("SQUAWKFLOW",key,type(e).__name__,str(e)[:160])
 if out:
  feed["squawkFlow"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),**out,
    "note":"GEX SPX/VIX curve/flow from SquawkFlow public delayed data. Unusual options direction is inferred from quote location and aggregate chain activity; not confirmed trade intent."}


def _norm_dark_print(row, ticker, source):
 def pick(keys, default=None):
  for k in keys:
   if isinstance(row,dict) and row.get(k) not in (None,""): return row.get(k)
  return default
 ts=pick(["timestamp","executed_at","execution_timestamp","time","ts","t","participant_timestamp","sip_timestamp","trf_timestamp"])
 if isinstance(ts,(int,float)):
  # normalize ns/ms/s epochs
  if ts>1e17: ts=ts/1e9
  elif ts>1e14: ts=ts/1e6
  elif ts>1e11: ts=ts/1e3
  try: ts=datetime.fromtimestamp(ts,tz=timezone.utc).isoformat()
  except Exception: ts=str(ts)
 price=num(pick(["price","execution_price","trade_price"]))
 size=num(pick(["size","shares","quantity","trade_size"]))
 notional=num(pick(["notional","notional_value","premium","dollar_value"]))
 if notional is None and price is not None and size is not None:notional=price*size
 side=str(pick(["direction","side","aggressor","flow_side","nbbo_location_proxy","nbbo_side"],"UNKNOWN")).upper()
 if side in ("BUY","B","ASK","AT_ASK","AT-ASK","ABOVE_ASK"):side="BUY"
 elif side in ("SELL","S","BID","AT_BID","AT-BID","BELOW_BID"):side="SELL"
 else:side="UNKNOWN"
 conf=pick(["direction_confidence","confidence","side_confidence"])
 return {
  "ticker":ticker,"timestamp":ts,"price":price,"size":size,"notional":notional,
  "side":side,"directionConfidence":num(conf),"venue":pick(["venue","market_center","market","trf_name","trf","reported_venue"]),
  "trfId":pick(["trf_id","trfi","trfId"]),"conditions":pick(["conditions","condition_codes","trade_conditions"],[]),
  "source":source,"realPrint":True,
  "sideBasis":"NBBO-location proxy" if side!="UNKNOWN" else "Not reported / not inferred"
 }



def _parse_money_token(x):
 if x is None:return None
 s=str(x).strip().replace("$","").replace(",","")
 mult=1
 if s.upper().endswith("K"):mult=1e3;s=s[:-1]
 elif s.upper().endswith("M"):mult=1e6;s=s[:-1]
 elif s.upper().endswith("B"):mult=1e9;s=s[:-1]
 try:return float(s)*mult
 except Exception:return None

def _parse_share_token(x):
 if x is None:return None
 s=str(x).strip().replace(",","")
 mult=1
 if s.lower().endswith("k"):mult=1e3;s=s[:-1]
 elif s.lower().endswith("m"):mult=1e6;s=s[:-1]
 elif s.lower().endswith("b"):mult=1e9;s=s[:-1]
 try:return float(s)*mult
 except Exception:return None

def _parse_capitol_print_line(line):
 # Example from the public cockpit: 9:35COIN231kUBSS+0.22%
 m=re.match(r'^(\d{1,2}:\d{2}(?::\d{2})?)([A-Z][A-Z0-9.\-]{0,7})(\d+(?:[.,]\d+)?[KMB]?)([A-Z0-9\-]+)([+\-]\d+(?:\.\d+)?)%$',line.strip())
 if not m:return None
 return {"time":m.group(1),"ticker":m.group(2),"size":_parse_share_token(m.group(3)),
         "venue":m.group(4),"sessionMovePct":float(m.group(5))}

def yahoo_intraday(sym, interval="5m", range_="1d"):
 try:
  u="https://query1.finance.yahoo.com/v8/finance/chart/"+requests.utils.quote(sym,safe="")
  j=get(u,{"range":range_,"interval":interval}).json().get("chart",{}).get("result",[])
  if not j:return None
  r=j[0];ts=r.get("timestamp") or [];q=r.get("indicators",{}).get("quote",[{}])[0]
  out=[]
  for i,t in enumerate(ts):
   p=q.get("close",[None]*len(ts))[i] if i<len(q.get("close",[])) else None
   if p is not None:out.append({"ts":int(t),"price":float(p)})
  return out
 except Exception as e:
  print("YAHOO INTRADAY",sym,type(e).__name__,str(e)[:120]);return None

def chart_exchange_offexchange(sym):
 path_map={
  "SPY":"nyse-spy","QQQ":"nasdaq-qqq","AAPL":"nasdaq-aapl","NVDA":"nasdaq-nvda",
  "GLD":"nyse-gld","USO":"nyse-uso","IWM":"nyse-iwm","DIA":"nyse-dia",
  "MSFT":"nasdaq-msft","META":"nasdaq-meta","AMD":"nasdaq-amd","AMZN":"nasdaq-amzn",
  "TSLA":"nasdaq-tsla","JPM":"nyse-jpm","COIN":"nasdaq-coin","HYG":"nyse-hyg"
 }
 slug=path_map.get(sym)
 if not slug:return None
 try:
  html=get("https://chartexchange.com/symbol/"+slug+"/exchange-volume/dark-pool-prints/").text
  m=re.search(r"Today's Off Exchange & Dark Pool volume is\s+([0-9,]+),\s+which is\s+([0-9.]+)%",html,re.I)
  m30=re.search(r"average Off Exchange & Dark Pool volume has been\s+([0-9.]+)%",html,re.I)
  total=re.search(r"Today's Lit volume is\s+([0-9,]+)",html,re.I)
  if not m:return None
  return {"offExchangeShares":int(m.group(1).replace(",","")),"offExchangePct":float(m.group(2)),
          "offExchange30dPct":float(m30.group(1)) if m30 else None,
          "litShares":int(total.group(1).replace(",","")) if total else None,
          "source":"ChartExchange public exchange-volume page",
          "sourceUrl":"https://chartexchange.com/"}
 except Exception as e:
  print("CHARTEXCHANGE DP",sym,type(e).__name__,str(e)[:140]);return None

def update_dark_pool_prints(feed):
 prints=[]; sources=[]; assets={}
 universe={
  "SPY":{"label":"SPY","proxyFor":"S&P 500 E-Mini"},
  "QQQ":{"label":"QQQ","proxyFor":"Nasdaq-100"},
  "DIA":{"label":"DIA","proxyFor":"Dow Jones"},
  "UUP":{"label":"UUP","proxyFor":"DXY / USD Index"},
  "FXE":{"label":"FXE","proxyFor":"Euro FX"},
  "GLD":{"label":"GLD","proxyFor":"Gold"},
  "SLV":{"label":"SLV","proxyFor":"Silver"},
  "USO":{"label":"USO","proxyFor":"WTI"},
  "BNO":{"label":"BNO","proxyFor":"Brent"},
  "AAPL":{"label":"AAPL","proxyFor":"Equity"},
  "NVDA":{"label":"NVDA","proxyFor":"Equity"},
  "IWM":{"label":"IWM","proxyFor":"Small Caps"}
 }

 try:
  html=get("https://capitolwhale.com/dark-pool-prints").text
  soup=BeautifulSoup(html,"html.parser")
  text=" ".join(soup.stripped_strings)
  def money(pattern):
   m=re.search(pattern,text,re.I);return _parse_money_token(m.group(1)) if m else None
  def pct(pattern):
   m=re.search(pattern,text,re.I);return float(m.group(1)) if m else None
  def integer(pattern):
   m=re.search(pattern,text,re.I);return int(m.group(1).replace(",","")) if m else None
  print_count=integer(r'\bPrints\s+([\d,]+)')
  total_premium=money(r'Total premium\s+\$?([\d.,]+[KMB]?)')
  bullish=pct(r'Bullish\s+([\d.]+)%')
  largest=money(r'Largest\s+\$?([\d.,]+[KMB]?)')
  mb=re.search(r'Aggressor imbalance\s+Buy\s+([\d.]+)%\s*Sell\s+([\d.]+)%',text,re.I)
  buy_pct=float(mb.group(1)) if mb else None;sell_pct=float(mb.group(2)) if mb else None
  top=[]
  tm=re.search(r'Top tickers by premium(.*?)Aggressor imbalance',text,re.I|re.S)
  if tm:
   for mm in re.finditer(r'\b([A-Z][A-Z0-9.\-]{0,6})\s+\$([\d.,]+[KMB]?)',tm.group(1)):
    top.append({"ticker":mm.group(1),"premium":_parse_money_token(mm.group(2))})
  for raw in soup.stripped_strings:
   p=_parse_capitol_print_line(raw)
   if not p:continue
   p.update({"timestamp":p.pop("time"),"price":None,"priceApprox":None,"notional":None,
             "side":"UNKNOWN","directionConfidence":None,
             "sideBasis":"Not published per print on free cockpit",
             "source":"Capitol Whale · free public view","realPrint":True})
   prints.append(p)
  prints=prints[:100]
  if prints:sources.append("Capitol Whale")
 except Exception as e:
  print("CAPITOL DARK PRINTS",type(e).__name__,str(e)[:180])
  print_count=total_premium=bullish=largest=buy_pct=sell_pct=None;top=[]

 # Keep every selected asset visible even when the public print list did not contain it.
 for t,meta in universe.items():
  try:
   series=yahoo_intraday(t,"5m","1d") or []
   spot=series[-1]["price"] if series else None
   cs=chart_exchange_offexchange(t) or {}
   arr=[x for x in prints if x["ticker"]==t]
   # ChartExchange supplies authoritative daily off-exchange volume share; it does not
   # identify institutions or side per print.
   venue_map={}
   for p in arr:
    venue=str(p.get("venue") or "TRF")
    z=venue_map.setdefault(venue,{"venue":venue,"prints":0,"shares":0,"notional":0})
    z["prints"]+=1;z["shares"]+=float(p.get("size") or 0);z["notional"]+=float(p.get("notional") or 0)
   assets[t]={"ticker":t,"label":meta.get("label",t),"proxyFor":meta.get("proxyFor"),"lastPrice":spot,"priceSeries":series[-90:],"prints":arr,
     "printCount":len(arr),"shareCount":sum(float(x.get("size") or 0) for x in arr),
     "notional":sum(float(x.get("notional") or 0) for x in arr),
     "dailyOffExchange":cs,"venueClusters":sorted(venue_map.values(),key=lambda x:x["shares"],reverse=True)[:8],
     "source":"Yahoo Finance + Capitol Whale free print feed + ChartExchange public stats",
     "note":"El print público identifica tamaño/venue, pero no la cartera o institución final. El precio individual puede no estar expuesto por la vista gratuita."}
  except Exception as e:
   print("DARK ASSET",t,type(e).__name__,str(e)[:140])

 feed["darkPoolPrints"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
   "prints":prints,"assets":assets,"sources":sources,
   "printCount":print_count,"totalPremium":total_premium,"bullishPct":bullish,"largestPrintPremium":largest,
   "buyPct":buy_pct,"sellPct":sell_pct,"topTickers":top[:12],
   "dataStatus":"REAL TRF PRINTS · VENUE/MPID VISIBLE; PARTICIPANT NOT IDENTIFIED",
   "free":True,"documentedDelay":"Intraday public view; exact timing depends on source.",
   "note":"Los prints son ejecuciones off-exchange reportadas al TRF. El verde/rojo agregado es una clasificación de flujo; un print individual no permite saber qué cartera lo originó. Venue/MPID se muestra para agrupar actividad, no como identidad de fondo."}


def update_traditional_sentiment(feed):
 result={"bullishPct":28.8,"neutralPct":17.9,"bearishPct":53.3,"previousBullishPct":38.0,"previousNeutralPct":22.7,"previousBearishPct":39.3,"week":"2026-09-16","source":"AAII Investor Sentiment Survey","sourceUrl":"https://www.aaii.com/sentimentsurvey","bullBearSpread":-24.5}
 try:
  html=get("https://www.aaii.com/sentimentsurvey").text
  vals=re.findall(r'Bullish.*?([0-9]+\.[0-9]+)%.*?Neutral.*?([0-9]+\.[0-9]+)%.*?Bearish.*?([0-9]+\.[0-9]+)%',html,re.I|re.S)
  if vals:
   b,n,br=map(float,vals[0]);result.update(bullishPct=b,neutralPct=n,bearishPct=br,bullBearSpread=round(b-br,1))
 except Exception as e:print("AAII",type(e).__name__,str(e)[:180])
 feed["traditionalSentiment"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),**result}

def update_options_market_stats(feed):
 try:
  html=get("https://www.cboe.com/us/options/market_statistics/daily/").text
  m1=re.search(r'TOTAL PUT/CALL RATIO\D+([0-9.]+)',html,re.I);m2=re.search(r'INDEX PUT/CALL RATIO\D+([0-9.]+)',html,re.I)
  feed["optionsStats"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"totalPutCall":float(m1.group(1)) if m1 else None,"indexPutCall":float(m2.group(1)) if m2 else None,"source":"Cboe Daily Market Statistics","sourceUrl":"https://www.cboe.com/us/options/market_statistics/daily/"}
 except Exception as e:print("CBOE STATS",type(e).__name__,str(e)[:180])

def update_bond_curves(feed):
 key=os.getenv("TE_API_KEY")
 if not key:return
 country_map={"us":"United States","eu":"Euro Area","de":"Germany","uk":"United Kingdom","jp":"Japan","ca":"Canada","au":"Australia","nz":"New Zealand","ch":"Switzerland"}
 term_map={"3M":"3M","1Y":"52W","2Y":"2Y","5Y":"5Y","10Y":"10Y","20Y":"20Y","30Y":"30Y"}
 buckets={}
 for typ in sorted(set(term_map.values())):
  try:
   u="https://api.tradingeconomics.com/markets/bond"
   arr=get(u,{"c":key,"type":typ}).json()
   for row in arr if isinstance(arr,list) else []:
    country=str(row.get("Country") or "").strip()
    ticker=str(row.get("Ticker") or row.get("Symbol") or "").upper()
    name=str(row.get("Name") or "")
    key_country=next((eid for eid,nm in country_map.items() if nm.lower()==country.lower()),None)
    if not key_country and "EURO AREA" in (country.upper()+" "+name.upper()+" "+ticker):
     key_country="eu"
    if not key_country:continue
    buckets[(key_country,typ)]=row
  except Exception as e:print("BONDS TE",typ,type(e).__name__,str(e)[:160])
 for eid,country in country_map.items():
  eco=feed.get("economies",{}).get(eid)
  if not eco:continue
  tenors=eco.setdefault("bonds",{}).setdefault("tenors",[])
  for t in tenors:
   te_typ=term_map.get(t.get("term"))
   row=buckets.get((eid,te_typ)) if te_typ else None
   if not row:continue
   last=row.get("Last"); 
   if last not in (None,""): t["yield"]=f"{float(last):.3f}%"
   t["change1d"]=row.get("DailyPercentualChange")
   t["change1w"]=row.get("WeeklyPercentualChange")
   t["change1m"]=row.get("MonthlyPercentualChange")
   t["change1dBp"]=row.get("DailyChange")
   t["change1wBp"]=row.get("WeeklyChange")
   t["change1mBp"]=row.get("MonthlyChange")
   t["source"]="Trading Economics / government bond market"
 feed["bondCurvesUpdated"]=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

def update_markets_rotation(feed):
 sector_cfg=[
  ("Tecnología","XLK"),("Energía","XLE"),("Financieras","XLF"),("Industriales","XLI"),("Salud","XLV"),
  ("Consumo discrecional","XLY"),("Consumo básico","XLP"),("Utilities","XLU"),("Materiales","XLB"),
  ("Comunicación","XLC"),("REITs","XLRE")
 ]
 style_cfg=[("Growth vs Value","VUG","VTV"),("Cíclicos vs Defensivos","XLY","XLP"),("Small vs Large","IWM","SPY"),("High Beta vs Low Vol","SPHB","SPLV"),("Nasdaq vs S&P","QQQ","SPY")]
 def series(sym):
  r=chart(sym)
  if not r:return None
  q=[float(x) for x in r.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
  if len(q)<22:return None
  return {"last":q[-1],"d1":(q[-1]/q[-2]-1)*100,"w1":(q[-1]/q[-6]-1)*100,"m1":(q[-1]/q[-22]-1)*100}
 def rel(a,b,key):
  x=series(a);y=series(b)
  if not x or not y:return None
  return x[key]-y[key]
 sectors=[]
 for name,sym in sector_cfg:
  x=series(sym)
  if x:
   sectors.append({"name":name,"symbol":sym,"change1d":x["d1"],"change1w":x["w1"],"change1m":x["m1"],"vsSpy1d":rel(sym,"SPY","d1"),"vsSpy1w":rel(sym,"SPY","w1"),"vsSpy1m":rel(sym,"SPY","m1")})
 styles=[]
 for name,a,b in style_cfg:
  styles.append({"name":name,"long":a,"short":b,"change1d":rel(a,b,"d1"),"change1w":rel(a,b,"w1"),"change1m":rel(a,b,"m1")})
 up=sum(x["change1w"]>0 for x in sectors); down=sum(x["change1w"]<0 for x in sectors); neutral=len(sectors)-up-down
 sentiment={"bullishPct":round(up*100/len(sectors),1) if sectors else 0,"neutralPct":round(neutral*100/len(sectors),1) if sectors else 0,"bearishPct":round(down*100/len(sectors),1) if sectors else 0}
 feed["rotation"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"sectors":sectors,"styles":styles,"sentimentTraditional":sentiment,"method":"ETF sectorial: cambios 1D/1S/1M y fuerza relativa frente a SPY. Sentimiento tradicional = amplitud sectorial semanal; es un proxy de mercado, no una encuesta."}

def update_crypto_sentiment(feed):
 try:
  fg=get("https://api.alternative.me/fng/",{"limit":"2","format":"json"}).json().get("data",[])
  fg_now=fg[0] if fg else {}
  fg_prev=fg[1] if len(fg)>1 else {}
 except Exception as e:
  print("CRYPTO FNG",type(e).__name__,str(e)[:180]); fg_now={}; fg_prev={}
 btc=chart("BTC-USD"); eth=chart("ETH-USD")
 def ret(r,n):
  q=[float(x) for x in r.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None] if r else []
  if len(q)<22:return None
  return {"change1d":(q[-1]/q[-2]-1)*100,"change1w":(q[-1]/q[-6]-1)*100,"change1m":(q[-1]/q[-22]-1)*100,"last":q[-1]}
 feed["cryptoSentiment"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"fearGreed": {"value":num(fg_now.get("value")),"classification":fg_now.get("value_classification"),"previous":num(fg_prev.get("value"))},"btc":ret(btc,0),"eth":ret(eth,0),"source":"Alternative.me Fear & Greed + Yahoo Finance"}

def update_bond_market(feed):
 out=[]
 for name,sym in (("Treasuries largos","TLT"),("Treasuries intermedios","IEF"),("Treasuries cortos","SHY"),("High Yield","HYG"),("Investment Grade","LQD")):
  r=chart(sym)
  if not r:continue
  q=[float(x) for x in r.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
  if len(q)<22:continue
  out.append({"name":name,"symbol":sym,"change1d":(q[-1]/q[-2]-1)*100,"change1w":(q[-1]/q[-6]-1)*100,"change1m":(q[-1]/q[-22]-1)*100,"last":q[-1]})
 feed["bondMarket"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"method":"ETF price returns; complementa los niveles y spreads de Treasury/BCE por economía."}

def enrich_feed(feed):
 for name,fn in (("FX",update_fx),("COT",update_cot),("OPTIONS",update_options),("DARK_POOLS",update_dark_pools),("DARK_PRINTS",update_dark_pool_prints),("DARK_FLOW",update_dark_flow_radar),("SQUAWKFLOW",update_squawkflow),("ROTATION",update_markets_rotation),("CRYPTO",update_crypto_sentiment),("BONDS",update_bond_market),("BOND_CURVES",update_bond_curves),("SENTIMENT",update_traditional_sentiment),("OPTION_STATS",update_options_market_stats)):
  try:
   fn(feed)
  except Exception as e:
   print(name,type(e).__name__,str(e)[:180])
def update_risk(feed):
 data=[]
 for n,s in YAHOO.items():
  m=yahoo(s)
  if not m:continue
  v,c1,c5=m; r=chart(s)
  q=[float(x) for x in (r or {}).get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None] if r else []
  c20=(q[-1]/q[-22]-1)*100 if len(q)>=22 else None
  data.append({"name":n,"symbol":s,"value":v,"change1d":c1,"change1w":c5,"change5d":c5,"change1m":c20,"role":ROLES.get(n,"Confirmación")})
 if not data:return
 by={x["name"]:x for x in data};score=50.0;comp=[]
 def add(n,p,w):
  nonlocal score;score+=p;comp.append((p,n,w))
 for n,w in [("SP500",8),("NASDAQ",8)]:
  if n in by:add(n,max(-w,min(w,by[n]["change1w"]*w/1.5)),"tendencia 1S")
 if "VIX" in by:
  v=by["VIX"]["value"];add("VIX",8 if v<15 else 4 if v<20 else -4 if v<25 else -8,"nivel de volatilidad")
 if "VVIX" in by:
  v=by["VVIX"]["value"];add("VVIX",4 if v<90 else 1 if v<105 else -2 if v<115 else -4,"volatilidad de volatilidad")
 if "SKEW" in by:
  v=by["SKEW"]["value"];add("SKEW",3 if v<120 else 1 if v<130 else -2 if v<140 else -4,"riesgo de cola")
 if "MOVE" in by:
  v=by["MOVE"]["value"];add("MOVE",3 if v<70 else 1 if v<85 else -2 if v<110 else -5,"volatilidad de bonos")
 for n,w in [("AUDJPY",2),("DXY",-2),("COPPER",1.5),("BTC",.8),("ETH",.8),("HYG",1.5),("LQD",1)]:
  if n in by:add(n,max(-5,min(5,by[n]["change1w"]*w)),"confirmación intermercado")
 if "GOLD" in by:add("GOLD",max(-3,min(3,-by["GOLD"]["change1w"]*1.2)),"demanda defensiva")
 if "BRENT" in by and "WTI" in by:
  oil=max(by["BRENT"]["change1w"],by["WTI"]["change1w"]);add("OIL",-2 if oil>6 else -1 if oil<-6 else 0,"shock energético contextual")
 if "TLT" in by and "SPY" in by:add("TLT/SPY",max(-3,min(3,-(by["TLT"]["change1w"]-by["SPY"]["change1w"])*1.5)),"duración vs acciones")
 score=max(0,min(100,score));label="RISK ON" if score>=65 else "RISK OFF" if score<=35 else "NEUTRAL / MIXTO"
 pos=sum(p>.4 for p,_,_ in comp);neg=sum(p<-.4 for p,_,_ in comp);conf=round(max(35,min(90,55+min(20,abs(pos-neg)*3)-(10 if pos and neg and abs(pos-neg)<=1 else 0))))
 why={"SP500":"la bolsa amplia acompaña el apetito por riesgo","NASDAQ":"la beta alta acompaña el régimen","VIX":"la volatilidad bursátil está contenida","VVIX":"la volatilidad de la volatilidad no muestra estrés","SKEW":"el riesgo de cola no muestra tensión extrema","MOVE":"la volatilidad de bonos no muestra estrés significativo","HYG":"el crédito high yield acompaña el apetito por riesgo","LQD":"el crédito investment grade se mantiene estable","DXY":"el dólar actúa como refugio/liquidez","AUDJPY":"el carry confirma apetito por riesgo","COPPER":"el cobre acompaña la demanda cíclica","GOLD":"el oro muestra demanda defensiva","BTC":"cripto acompaña la liquidez/alta beta","ETH":"cripto acompaña la liquidez/alta beta","TLT/SPY":"la duración gana terreno relativo a acciones","OIL":"el petróleo aporta señal de crecimiento/inflación"}
 positives=sorted([x for x in comp if x[0]>0],reverse=True)[:5];negatives=sorted([x for x in comp if x[0]<0])[:5]
 feed["riskOnOff"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"score":round(score,1),"label":label,"confidence":conf,"method":"Composite intermercado: acciones, VIX/VVIX/SKEW, MOVE, crédito HYG/LQD, dólar, carry, materias primas, duración y cripto. El petróleo se trata como señal contextual de inflación/crecimiento.","assets":data,"confirmations":[f"{n}: {why.get(n,w)}." for _,n,w in positives],"tensions":[f"{n}: {why.get(n,w)}." for _,n,w in negatives],"coverage":feed.get("riskOnOff",{}).get("coverage",{})}


