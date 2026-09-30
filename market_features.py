from __future__ import annotations
import json, math, os, re, requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
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

def _max_pain(calls,puts):
 """Strike with the lowest aggregate holder payoff at expiration from public OI."""
 strikes=sorted({float(x.get("strike") or 0) for x in calls+puts if float(x.get("strike") or 0)>0})
 if not strikes:return None
 losses=[]
 for settlement in strikes:
  call_loss=sum(max(0.0,settlement-float(x.get("strike") or 0))*float(x.get("openInterest") or 0) for x in calls)
  put_loss=sum(max(0.0,float(x.get("strike") or 0)-settlement)*float(x.get("openInterest") or 0) for x in puts)
  losses.append((settlement,call_loss+put_loss))
 return min(losses,key=lambda x:x[1])[0] if losses else None

def _option_gex(calls,puts,spot):
 scale=float(spot or 0)**2*0.01*100.0
 by_strike={}; posZones=[]; negZones=[]; callWall=None; putWall=None
 for x in calls:
  strike=float(x.get("strike") or 0)
  v=float(x.get("openInterest",0) or 0)*float(x.get("gamma",0) or 0)*scale
  by_strike[strike]=by_strike.get(strike,0.0)+v
  posZones.append({"strike":x.get("strike"),"gamma":v})
  if callWall is None or v>callWall["gamma"]: callWall={"strike":x.get("strike"),"gamma":v}
 for x in puts:
  strike=float(x.get("strike") or 0)
  v=-float(x.get("openInterest",0) or 0)*float(x.get("gamma",0) or 0)*scale
  by_strike[strike]=by_strike.get(strike,0.0)+v
  negZones.append({"strike":x.get("strike"),"gamma":v})
  if putWall is None or abs(v)>abs(putWall["gamma"]): putWall={"strike":x.get("strike"),"gamma":v}
 vals=sorted(by_strike.items())
 net=sum(v for _,v in vals); pos=sum(v for _,v in vals if v>0); neg=sum(v for _,v in vals if v<0)
 # Public-chain gamma-flip proxy: the strike where cumulative signed GEX crosses zero.
 cum=0.0; prev_k=None; prev_cum=None; flip=None
 for k,v in vals:
  nxt=cum+v
  if prev_k is not None and ((cum<0 and nxt>=0) or (cum>0 and nxt<=0)):
   flip=prev_k+(0-cum)*(k-prev_k)/(nxt-cum) if nxt!=cum else k
   break
  prev_k,prev_cum=k,cum
  cum=nxt
 regime="NEGATIVE · potencial amplificación" if net<0 else "POSITIVE · potencial estabilización" if net>0 else "NEUTRAL"
 effect="Los hedges modelados pueden reforzar el movimiento" if net<0 else "Los hedges modelados pueden amortiguar el movimiento" if net>0 else "Sin sesgo de gamma agregado"
 return {
  "gammaPositive":pos,"gammaNegative":neg,"gammaNet":net,"gammaTotal":net,
  "gammaRegime":regime,"gammaEffect":effect,"gammaFlip":flip,"zeroGamma":flip,
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
 total_oi=co+po
 above_oi=sum(float(x.get("openInterest",0) or 0) for x in rows if float(x.get("strike") or 0)>spot)
 below_oi=sum(float(x.get("openInterest",0) or 0) for x in rows if float(x.get("strike") or 0)<spot)
 at_oi=max(0,total_oi-above_oi-below_oi)
 atm=sorted(rows,key=lambda x:abs(float(x.get("strike") or 0)-spot))[:4]
 ivs=[float(x.get("iv") or 0) for x in atm if float(x.get("iv") or 0)>0]
 iv_atm=sum(ivs)/len(ivs) if ivs else None
 if iv_atm and iv_atm>3:iv_atm/=100.0
 atm_row=atm[0] if atm else {}
 atm_delta=atm_row.get("delta");atm_gamma=atm_row.get("gamma");atm_vanna=atm_row.get("vanna");atm_charm=atm_row.get("charm")
 expected=spot*iv_atm*math.sqrt(max(ex,0)/365.0) if iv_atm and ex>0 else None
 max_pain=_max_pain(calls,puts)
 dex=None;vanna=None;charm_vals=[];gex_by=[]
 for x in rows:
  oi=float(x.get("openInterest",0) or 0); delta=x.get("delta"); gamma=float(x.get("gamma",0) or 0)
  if delta is not None:dex=(dex or 0)+oi*float(delta)*spot*100.0
  iv=float(x.get("iv") or 0); k=float(x.get("strike") or 0)
  if x.get("vanna") is not None:vanna=(vanna or 0)+oi*float(x["vanna"])*100.0
  else:
   vp=_vanna_proxy(spot,k,iv,max(ex,0)/365.0)
   if vp is not None:vanna=(vanna or 0)+oi*vp*100.0
  if x.get("charm") is not None:charm_vals.append(oi*float(x["charm"])*100.0)
  sign=1 if x.get("type")=="C" else -1
  gex_by.append({"strike":x.get("strike"),"gex":sign*oi*gamma*(spot**2)*0.01*100.0,"oi":oi,"volume":float(x.get("volume",0) or 0),"type":x.get("type")})
 oi_delta=None;largest_oi_change=None
 if oi_prev:
  oi_delta=sum(float(x.get("openInterest",0) or 0)-float(oi_prev.get(x.get("key"),0) or 0) for x in rows)
  changes=[]
  for x in rows:
   k=x.get("key")
   if k in oi_prev:
    d=float(x.get("openInterest",0) or 0)-float(oi_prev.get(k,0) or 0);changes.append({"strike":x.get("strike"),"type":x.get("type"),"change":d})
  if changes:largest_oi_change=max(changes,key=lambda z:abs(z["change"]))
 charm=sum(charm_vals) if charm_vals else None
 calls25=[x for x in calls if x.get("delta") is not None and float(x.get("iv") or 0)>0]
 puts25=[x for x in puts if x.get("delta") is not None and float(x.get("iv") or 0)>0]
 c25=min(calls25,key=lambda x:abs(float(x.get("delta"))-0.25)) if calls25 else None
 p25=min(puts25,key=lambda x:abs(float(x.get("delta"))+0.25)) if puts25 else None
 iv25c=float(c25.get("iv")) if c25 else None;iv25p=float(p25.get("iv")) if p25 else None
 if iv25c and iv25c>3:iv25c/=100.0
 if iv25p and iv25p>3:iv25p/=100.0
 rr25=(iv25c-iv25p)*100 if iv25c is not None and iv25p is not None else None
 call_oi_wall=max(calls,key=lambda x:float(x.get("openInterest",0) or 0)) if calls else None
 put_oi_wall=max(puts,key=lambda x:float(x.get("openInterest",0) or 0)) if puts else None
 strike_map={}
 for z in gex_by:
  k=z.get("strike")
  if k is None:continue
  key=str(k); a=strike_map.setdefault(key,{"strike":k,"gex":0.0,"callOi":0.0,"putOi":0.0,"callVolume":0.0,"putVolume":0.0})
  a["gex"]+=float(z.get("gex") or 0)
  if z.get("type")=="C":a["callOi"]+=float(z.get("oi") or 0);a["callVolume"]+=float(z.get("volume") or 0)
  else:a["putOi"]+=float(z.get("oi") or 0);a["putVolume"]+=float(z.get("volume") or 0)
 strike_map=sorted(strike_map.values(),key=lambda z:float(z["strike"]))
 if len(strike_map)>60:
  strike_map=sorted(strike_map,key=lambda z:abs(float(z["strike"])-spot))[:60]
  strike_map=sorted(strike_map,key=lambda z:float(z["strike"]))
 return {
  "expiration":expiration.date().isoformat(),"daysToExpiry":round(ex,2),
  "callOi":co,"putOi":po,"putCallOi":po/co if co else None,"callVolume":cv,"putVolume":pv,"putCallVolume":pv/cv if cv else None,"putCallVol":pv/cv if cv else None,"totalVolume":cv+pv,"totalOpenInterest":total_oi,
  "oiAboveSpot":above_oi,"oiBelowSpot":below_oi,"oiAtSpot":at_oi,"oiAbovePct":above_oi/total_oi*100 if total_oi else None,"oiBelowPct":below_oi/total_oi*100 if total_oi else None,
  "ivAtm":iv_atm*100 if iv_atm else None,"atmDelta":atm_delta,"atmGamma":atm_gamma,"atmVega":(float(atm_row.get("vega")) if atm_row.get("vega") is not None else None),"atmCharm":atm_charm,"expectedMove":expected,"expectedMovePct":expected/spot*100 if expected and spot else None,
  "iv25dCall":iv25c*100 if iv25c else None,"iv25dPut":iv25p*100 if iv25p else None,"riskReversal25d":rr25,"skew25d":rr25,
  "call25dStrike":c25.get("strike") if c25 else None,"put25dStrike":p25.get("strike") if p25 else None,
  "maxPain":max_pain,"maxPainDistance":max_pain-spot if max_pain is not None else None,"maxPainDistancePct":(max_pain-spot)/spot*100 if max_pain is not None and spot else None,
  "callWallOi":call_oi_wall.get("strike") if call_oi_wall else None,"callWallOiValue":call_oi_wall.get("openInterest") if call_oi_wall else None,"callWallVolume":call_oi_wall.get("volume") if call_oi_wall else None,
  "putWallOi":put_oi_wall.get("strike") if put_oi_wall else None,"putWallOiValue":put_oi_wall.get("openInterest") if put_oi_wall else None,"putWallVolume":put_oi_wall.get("volume") if put_oi_wall else None,
  "dexProxy":dex,"vannaProxy":vanna,"charm":charm,"oiChange":oi_delta,"largestOiChange":largest_oi_change,
  **gp,"gammaFlipDistance":(gp.get("gammaFlip")-spot) if gp.get("gammaFlip") is not None else None,"gammaFlipDistancePct":(gp.get("gammaFlip")-spot)/spot*100 if gp.get("gammaFlip") is not None and spot else None,
  "topGexStrikes":sorted(gex_by,key=lambda z:abs(z["gex"]),reverse=True)[:16],
  "strikeMap":strike_map,
  "sourceWindow":"Public delayed chain · OI/volume/IV; Greeks calculated with Black-Scholes"
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

def _massive_json(path, params=None):
 try:
  key=os.getenv("MASSIVE_API_KEY")
  if not key:return None
  p=dict(params or {});p["apiKey"]=key
  return get("https://api.massive.com"+path,p,{"Accept":"application/json","User-Agent":"MacroTerminal/6.0"}).json()
 except Exception as e:
  print("MASSIVE",path,type(e).__name__,str(e)[:160]);return None

def _massive_follow_pages(j,max_pages=5):
 rows=list((j or {}).get("results") or []);nxt=(j or {}).get("next_url");pages=1
 while nxt and pages<max_pages:
  try:
   key=os.getenv("MASSIVE_API_KEY")
   if not key:break
   url=nxt+("&" if "?" in nxt else "?")+"apiKey="+requests.utils.quote(key,safe="")
   jj=get(url,{"limit":"250"},{"Accept":"application/json","User-Agent":"MacroTerminal/6.0"}).json()
   if not isinstance(jj,dict):break
   more=jj.get("results") or []
   if not more:break
   rows.extend(more);nxt=jj.get("next_url");pages+=1
  except Exception as e:
   print("MASSIVE PAGINATION",type(e).__name__,str(e)[:140]);break
 return rows

def _massive_option_chain(underlying):
 try:
  if not os.getenv("MASSIVE_API_KEY"):return None
  today=datetime.now(timezone.utc).date()
  base=_massive_json("/v3/snapshot/options/"+requests.utils.quote(underlying,safe=""),{"expiration_date.gte":today.isoformat(),"limit":"250"})
  if not base:return None
  base_rows=_massive_follow_pages(base)
  if not base_rows:return None
  spot=None
  for x in base_rows:
   spot=num((x.get("underlying_asset") or {}).get("price") or x.get("underlying_price"))
   if spot is not None:break
  exps=sorted({str((x.get("details") or {}).get("expiration_date") or x.get("expiration_date") or "")[:10] for x in base_rows if (x.get("details") or {}).get("expiration_date") or x.get("expiration_date")})
  exps=[x for x in exps if x]
  if not exps:return None
  candidates=[]
  for ex in exps:
   try:
    d=datetime.fromisoformat(ex).date();days=(d-today).days
    if days>=0:candidates.append((d,ex,days))
   except Exception:pass
  if not candidates:return None
  selected=[]
  for bucket,predicate in (
   ("0DTE",lambda d:d==0),("NEXT",lambda d:0<d<=2),("7-30D",lambda d:7<d<=30),("30-90D",lambda d:30<d<=90)):
   c=[z for z in candidates if predicate(z[2])]
   if c:selected.append((bucket,c[0]))
  if not selected:selected=[("NEXT",candidates[0])]
  profiles=[]
  for bucket,(_,ex,_) in selected[:4]:
   j=_massive_json("/v3/snapshot/options/"+requests.utils.quote(underlying,safe=""),{"expiration_date":ex,"limit":"250"})
   rows=_massive_follow_pages(j or {})
   mapped=[]
   for x in rows:
    det=x.get("details") or {};day=x.get("day") or {};greeks=x.get("greeks") or {}
    typ=str(det.get("contract_type") or x.get("contract_type") or "").lower()
    if typ not in ("call","put"):continue
    strike=num(det.get("strike_price") or x.get("strike_price"))
    if strike is None:continue
    mapped.append({
     "strike":strike,"openInterest":num(x.get("open_interest")) or 0,"volume":num(day.get("volume") or x.get("volume")) or 0,
     "iv":num(x.get("implied_volatility") or greeks.get("iv")) or 0,"delta":num(greeks.get("delta")),"gamma":num(greeks.get("gamma")),
     "vanna":num(greeks.get("vanna")),"charm":num(greeks.get("charm")),"vega":num(greeks.get("vega")),
     "type":"C" if typ=="call" else "P","expiration":ex,
     "bid":num((x.get("last_quote") or {}).get("bid")),"ask":num((x.get("last_quote") or {}).get("ask")),
     "lastPrice":num((x.get("last_trade") or {}).get("price")),"contractSymbol":det.get("ticker") or x.get("ticker")
    })
   if mapped and spot is not None:
    p=_option_summary(mapped,float(spot),datetime.fromisoformat(ex).replace(tzinfo=timezone.utc))
    p.update(bucket=bucket,source="Massive · full-chain snapshot",dataStatus="REAL / DELAYED · Massive",chainCount=len(mapped),coverage="Full listed chain returned by provider")
    profiles.append(p)
  if not profiles:return None
  return {"ticker":underlying,"name":underlying,"spot":spot,"profiles":profiles,
          "termStructure":[{"bucket":p.get("bucket"),"expiration":p.get("expiration"),"dte":p.get("daysToExpiry"),"ivAtm":p.get("ivAtm")} for p in profiles],
          "zeroDteVolume":next((p.get("totalVolume") for p in profiles if p.get("bucket")=="0DTE"),None),
          "source":"Massive Options Snapshot","sourceUrl":"https://massive.com/docs/rest/options/overview","dataStatus":"REAL / DELAYED · Massive","referenceOnly":False,
          "method":"Massive full-chain snapshot; OI/volume/IV/Greeks supplied by provider. GEX/Gamma Flip/DEX are calculated from the returned chain."}
 except Exception as e:
  print("MASSIVE OPTIONS",underlying,type(e).__name__,str(e)[:180]);return None

def opt(sym):
 try:
  base=_yahoo_option_chain(sym)
  if not base:return None
  spot=num(base.get("quote",{}).get("regularMarketPrice") or base.get("quote",{}).get("postMarketPrice"))
  expirations=[int(x) for x in (base.get("expirationDates") or [])]
  now=datetime.now(timezone.utc);expirations=[x for x in expirations if datetime.fromtimestamp(x,tz=timezone.utc)>now]
  if not spot or not expirations:return None
  monthly=[x for x in expirations if datetime.fromtimestamp(x,tz=timezone.utc).weekday()==4 and 15<=datetime.fromtimestamp(x,tz=timezone.utc).day<=21]
  # Keep a compact but useful horizon: 0DTE (when available), next, 7-30D and 30-90D.
  buckets=[]
  today=datetime.now(timezone.utc).date()
  for ex in expirations:
   d=datetime.fromtimestamp(ex,tz=timezone.utc);days=(d.date()-today).days
   if days==0 or days<=2: bucket="0DTE"
   elif days<=7: bucket="NEXT"
   elif days<=30: bucket="7-30D"
   elif days<=90: bucket="30-90D"
   else: bucket=None
   if bucket and bucket not in [b[0] for b in buckets]:buckets.append((bucket,ex))
  if not buckets:buckets=[("NEXT",expirations[0])]
  selected=[]
  for label,ex in buckets:
   if ex not in selected:selected.append(ex)
  if monthly:
   mex=monthly[0]
   if mex not in selected and len(selected)<4:selected.append(mex)
  profiles=[];all_raw=[]
  for ex in selected[:4]:
   chain=_yahoo_option_chain(sym,ex)
   if not chain:continue
   rows=[]
   for typ,key in (("C","calls"),("P","puts")):
    for x in chain.get(key,[]) or []:
     K=num(x.get("strike"));oi=num(x.get("openInterest")) or 0;vol=num(x.get("volume")) or 0;iv=num(x.get("impliedVolatility")) or 0
     if not K:continue
     T=max((ex-datetime.now(timezone.utc).timestamp())/(365*86400),1/3650)
     delta,gamma,vanna,charm=_bs_greeks(spot,K,T,iv,0.04,typ)
     rows.append({"strike":K,"openInterest":oi,"volume":vol,"iv":iv,"gamma":gamma,"delta":delta,"vanna":vanna,"charm":charm,"vega":(float(_norm_pdf(((math.log(spot/K)+(0.04+0.5*(iv if iv<3 else iv/100)**2)*T)/((iv if iv<3 else iv/100)*math.sqrt(T))))*spot*math.sqrt(T)) if iv else None),"type":typ,"expiration":ex,"bid":num(x.get("bid")),"ask":num(x.get("ask")),"lastPrice":num(x.get("lastPrice")),"contractSymbol":x.get("contractSymbol")})
   if rows:
    p=_option_summary(rows,spot,datetime.fromtimestamp(ex,tz=timezone.utc));p["bucket"]=next((b for b,e in buckets if e==ex),"OTHER");profiles.append(p);all_raw.extend(rows)
  if not profiles:return None
  for p in profiles:
   ex=int(datetime.fromisoformat(p["expiration"]).replace(tzinfo=timezone.utc).timestamp());rr=[x for x in all_raw if x["expiration"]==ex]
   coi=sum(x["openInterest"] for x in rr if x["type"]=="C");poi=sum(x["openInterest"] for x in rr if x["type"]=="P");cv=sum(x["volume"] for x in rr if x["type"]=="C");pv=sum(x["volume"] for x in rr if x["type"]=="P")
   p["putCallOi"]=poi/coi if coi else None;p["putCallVolume"]=pv/cv if cv else None;p["putCallVol"]=p["putCallVolume"];p["totalVolume"]=cv+pv
  return {"name":("USO · ETF proxy WTI" if sym=="USO" else sym),"ticker":sym,"spot":spot,"expiration":datetime.fromtimestamp(selected[0],tz=timezone.utc).date().isoformat(),"monthlyExpiration":datetime.fromtimestamp(monthly[0],tz=timezone.utc).date().isoformat() if monthly else None,"profiles":profiles,"method":"Yahoo Finance public option chain · OI/volume/IV + Black-Scholes Greeks. GEX/Gamma Flip/DEX/Vanna/Charm are modeled proxies, not observed dealer positioning.","source":"Yahoo Finance public option chain","sourceUrl":"https://finance.yahoo.com/quote/"+sym+"/options/","gammaNote":"GEX by strike is an exposure model based on public OI, IV and model gamma; call/put walls are OI concentrations and do not guarantee support/resistance."}
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
def yahoo_ytd(sym):
 try:
  u="https://query1.finance.yahoo.com/v8/finance/chart/"+requests.utils.quote(sym,safe="")
  j=get(u,{"range":"1y","interval":"1d"}).json().get("chart",{}).get("result",[])
  if not j:return None
  r=j[0];ts=r.get("timestamp") or [];q=(r.get("indicators",{}).get("quote") or [{}])[0].get("close") or []
  rows=[]
  for t,v in zip(ts,q):
   if v is None:continue
   d=datetime.fromtimestamp(float(t),tz=timezone.utc).date()
   rows.append((d,float(v)))
  if not rows:return None
  year=datetime.now(timezone.utc).year;start=next(((d,v) for d,v in rows if d.year==year),None)
  if not start:return None
  last=rows[-1][1]
  return {"changeYtd":(last/start[1]-1)*100,"ytdStart":start[1],"last":last,"ytdDate":start[0].isoformat()}
 except Exception as e:
  print("YTD",sym,type(e).__name__,str(e)[:120]);return None

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


def cot_rows(dataset,where,limit=260):
 try:
  h={"X-App-Token":os.getenv("CFTC_APP_TOKEN")} if os.getenv("CFTC_APP_TOKEN") else {}
  return get("https://publicreporting.cftc.gov/resource/"+dataset+".json",{
   "$limit":str(limit),
   "$order":"report_date_as_yyyy_mm_dd DESC",
   "$where":where
  },h).json()
 except Exception as e:
  print("COT_ROWS",dataset,type(e).__name__,str(e)[:160]); return []

def _cot_num(row,*keys):
 for k in keys:
  v=num(row.get(k))
  if v is not None:return v
 return None

def _cot_percentile(history,current,lookback=52):
 vals=[x.get("net") for x in history[:lookback] if x.get("net") is not None]
 if len(vals)<8 or current is None:return None
 return round(100*sum(1 for v in vals if v<=current)/len(vals),1)

def _cot_z(history,current,lookback=52):
 vals=[x.get("net") for x in history[:lookback] if x.get("net") is not None]
 return zscore(vals,current) if len(vals)>=8 and current is not None else None

def _cot_category(row,pairs,oi=None):
 out={}
 oi=oi if oi is not None else _cot_num(row,"open_interest_all","open_interest")
 for key,label in pairs:
  lv=_cot_num(row,key+"_long_all",key+"_long",key.lower()+"_long_all",key.lower()+"_long")
  sv=_cot_num(row,key+"_short_all",key+"_short",key.lower()+"_short_all",key.lower()+"_short")
  sp=_cot_num(row,key+"_spread_all",key+"_spread",key.lower()+"_spread_all",key.lower()+"_spread")
  if lv is not None or sv is not None:
   lv=lv or 0; sv=sv or 0
   out[label]={
    "long":lv,"short":sv,"spread":sp,"net":lv-sv,
    "longPctOI":(lv/oi*100) if oi else None,
    "shortPctOI":(sv/oi*100) if oi else None,
    "spreadPctOI":(sp/oi*100) if oi and sp is not None else None
   }
 return out

def cot_one(rows,label,family,code,group):
 if not rows:return None
 if family=="TFF":
  primary=[
   ("dealer_positions","Dealer / Intermediarios"),
   ("asset_mgr_positions","Asset Managers"),
   ("lev_money_positions","Leveraged Funds"),
   ("other_rept_positions","Otros reportables"),
   ("nonrept_positions","No reportables")
  ]
 else:
  primary=[
   ("prod_merc_positions","Productores / Comerciantes"),
   ("swap_positions","Swap Dealers"),
   ("m_money_positions","Managed Money"),
   ("other_rept_positions","Otros reportables"),
   ("nonrept_positions","No reportables")
  ]

 def snapshot(r):
  oi=_cot_num(r,"open_interest_all","open_interest")
  cats=_cot_category(r,primary,oi)
  # The selected category is the one used in the dashboard headline.
  cat=cats.get(group)
  if not cat:
   # fallback by matching a shortened category label
   cat=next((v for k,v in cats.items() if group.lower() in k.lower()),None)
  lv=cat.get("long") if cat else None
  sv=cat.get("short") if cat else None
  if lv is None or sv is None:return None
  oi=_cot_num(r,"open_interest_all","open_interest")
  return {
   "date":str(r.get("report_date_as_yyyy_mm_dd",""))[:10],
   "net":lv-sv,"long":lv,"short":sv,"spread":cat.get("spread"),
   "openInterest":oi,
   "netPctOI":((lv-sv)/oi*100) if oi else None,
   "categories":cats
  }

 hist=[]
 for r in rows:
  s=snapshot(r)
  if s:hist.append(s)
 if not hist:return None
 cur=hist[0]; prev=hist[1] if len(hist)>1 else None; prev4=hist[4] if len(hist)>4 else None
 net=cur["net"]
 percentile52=_cot_percentile(hist,net,52)
 z52=_cot_z(hist,net,52)
 percentile260=_cot_percentile(hist,net,260)
 lo52=min((x["net"] for x in hist[:52] if x["net"] is not None),default=None)
 hi52=max((x["net"] for x in hist[:52] if x["net"] is not None),default=None)
 if percentile52 is None:state="SIN HISTÓRICO SUFICIENTE"
 elif percentile52>=90:state="EXTREMO · percentil alto"
 elif percentile52<=10:state="EXTREMO · percentil bajo"
 elif percentile52>=75:state="Sesgo alto"
 elif percentile52<=25:state="Sesgo bajo"
 else:state="Zona intermedia"

 return {
  "name":label,"reportDate":cur["date"],"net":net,"long":cur["long"],"short":cur["short"],"spread":cur.get("spread"),
  "openInterest":cur.get("openInterest"),"netPctOI":cur.get("netPctOI"),
  "zScore":z52,"z52":z52,"percentile52":percentile52,"percentile260":percentile260,
  "netChange":net-(prev["net"] if prev else net),
  "change1w":net-(prev["net"] if prev else net),
  "change4w":net-(prev4["net"] if prev4 else net),
  "range52Min":lo52,"range52Max":hi52,
  "reading":("Largos netos" if net>0 else "Cortos netos" if net<0 else "Neutro"),
  "state":state,"traderGroup":group,"reportFamily":family,
  "contractCode":code,
  "contract":str(rows[0].get("contract_market_name") or rows[0].get("market_and_exchange_names") or ""),
  "history":hist[:260],
  "historyWeeks":len(hist),
  "historyPolicy":"260 semanas almacenadas · 52 semanas por defecto en pantalla",
  "categories":cur.get("categories") or {}
 }

def update_cot(feed):
 cfg=[
  ("S&P 500 E-Mini","gpe5-46if","13874A","Leveraged Funds","TFF"),
  ("Nasdaq-100","gpe5-46if","209742","Leveraged Funds","TFF"),
  ("Dow Jones","gpe5-46if","124603","Leveraged Funds","TFF"),
  ("DXY · USD Index","gpe5-46if","098662","Leveraged Funds","TFF"),
  ("Euro FX","gpe5-46if","099741","Leveraged Funds","TFF"),
  ("Bitcoin · CME","gpe5-46if","133741","Leveraged Funds","TFF"),
  ("Ether · CME","gpe5-46if","146021","Leveraged Funds","TFF"),
  ("Oro","72hh-3qpy","088691","Managed Money","Disaggregated"),
  ("Plata","72hh-3qpy","084691","Managed Money","Disaggregated"),
  ("WTI","72hh-3qpy","067651","Managed Money","Disaggregated"),
  ("Brent","72hh-3qpy","06765T","Managed Money","Disaggregated")
 ]
 out=[];errors=[]
 for name,ds,code,group,fam in cfg:
  rows=cot_rows(ds,"cftc_contract_market_code='"+code+"'",260)
  x=cot_one(rows,name,fam,code,group) if rows else None
  if x:out.append(x)
  else:errors.append(name)
 if out:
  feed["cot"]={
   "updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
   "markets":out,
   "source":"CFTC Public Reporting Environment",
   "sourceUrl":"https://publicreporting.cftc.gov/",
   "method":"COT semanal. La cabecera usa Leveraged Funds para TFF y Managed Money para Disaggregated. Se conservan hasta 260 observaciones semanales por mercado.",
   "historyDefaultWeeks":52,
   "historyStoredWeeks":260,
   "releaseContext":"Datos de cada martes; publicación general viernes 15:30 ET. El histórico sirve para contexto semanal/mensual, no para timing intradía.",
   "errors":errors
  }

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

def _deribit_options(currency):
 out=[]
 try:
  instruments=get("https://www.deribit.com/api/v2/public/get_instruments",{"currency":currency,"kind":"option","expired":"false"}).json().get("result",[])
  idx=get("https://www.deribit.com/api/v2/public/get_index_price",{"index_name":currency.lower()+"_usd"}).json().get("result",{}).get("index_price")
  summaries=get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency",{"currency":currency,"kind":"option"}).json().get("result",[])
  if idx is None or not summaries:return None
  by_name={str(x.get("instrument_name")):x for x in summaries}
  now=datetime.now(timezone.utc);groups={"0DTE":[] ,"NEXT":[],"7-30D":[],"30-90D":[]}
  for ins in instruments:
   name=str(ins.get("instrument_name") or "");exp=ins.get("expiration_timestamp")
   if not name or not exp:continue
   d=datetime.fromtimestamp(float(exp)/1000,tz=timezone.utc);days=(d-now).total_seconds()/86400
   if days<0:continue
   b="0DTE" if days<1 else "NEXT" if days<=7 else "7-30D" if days<=30 else "30-90D" if days<=90 else None
   if b:groups[b].append((d,ins,by_name.get(name,{})))
  for bucket,items in groups.items():
   if not items:continue
   exp,ins,sm=min(items,key=lambda x:x[0])
   calls=[x for x in items if str(x[1].get("option_type","" )).lower()=="call"];puts=[x for x in items if str(x[1].get("option_type","" )).lower()=="put"]
   # Build strike clusters directly from Deribit public OI; IV is attached when the summary exposes it.
   clusters=[]
   for d0,ii,ss in items:
    oi=float(ss.get("open_interest") or 0);iv=float(ss.get("mark_iv") or 0);strike=float(ii.get("strike") or 0)
    if not oi or not strike:continue
    gamma=None;T=max((d0-now).total_seconds()/31536000,1/3650);typ="C" if str(ii.get("option_type","")).lower()=="call" else "P"
    _,gamma,_,_=_bs_greeks(float(idx),strike,T,iv/100 if iv>3 else iv,0.04,typ) if iv else (None,None,None,None)
    g=(1 if typ=="C" else -1)*oi*(gamma or 0)*float(idx)**2*0.01*1.0
    clusters.append({"strike":strike,"gex":g,"oi":oi,"volume":float(ss.get("volume") or 0),"type":typ,"iv":iv})
   call_clusters=[x for x in clusters if x["type"]=="C"];put_clusters=[x for x in clusters if x["type"]=="P"]
   callwall=max(call_clusters,key=lambda x:x["oi"],default=None);putwall=max(put_clusters,key=lambda x:x["oi"],default=None)
   net=sum(x["gex"] for x in clusters)
   strikes=sorted({x["strike"] for x in clusters});cum=0;flip=None;prev=None
   byk={k:sum(x["gex"] for x in clusters if x["strike"]==k) for k in strikes}
   for k in strikes:
    nxt=cum+byk[k]
    if prev is not None and ((cum<0<=nxt) or (cum>0>=nxt)):flip=prev;break
    prev=k;cum=nxt
   out.append({"ticker":currency+" · Deribit","name":currency+" Options · Deribit","source":"Deribit public options","sourceUrl":"https://www.deribit.com/options","spot":float(idx),"expiration":exp.date().isoformat(),"daysToExpiry":round((exp-now).total_seconds()/86400,2),"bucket":bucket,"gammaNet":net,"gammaFlip":flip,"callWall":callwall.get("strike") if callwall else None,"putWall":putwall.get("strike") if putwall else None,"callWallOiValue":callwall.get("oi") if callwall else None,"putWallOiValue":putwall.get("oi") if putwall else None,"topGexStrikes":sorted(clusters,key=lambda x:abs(x["gex"]),reverse=True)[:16],"note":"Deribit public BTC/ETH options. GEX is a modeled exposure estimate; not dealer positioning."})
  return {"ticker":currency,"name":currency+" Options · Deribit","spot":float(idx),"profiles":out,"source":"Deribit public options","sourceUrl":"https://www.deribit.com/options","method":"Public option instruments/book summaries; BTC/ETH kept separate from CME and IBIT."} if out else None
 except Exception as e:
  print("DERIBIT OPTIONS",currency,type(e).__name__,str(e)[:180]);return None

def _farside_num(v):
 try:
  s=str(v or "").strip().replace(",","")
  if s in ("","-","—"):return None
  if s.startswith("(") and s.endswith(")"):return -float(s[1:-1])
  return float(re.sub(r"[^0-9.+-]","",s))
 except Exception:return None

def _crypto_spot_etf_flows(asset="BTC"):
 try:
  slug="btc" if str(asset).upper()=="BTC" else "eth"
  html=get(f"https://farside.co.uk/{slug}/").text
  soup=BeautifulSoup(html,"html.parser");table=None
  for tbl in soup.find_all("table"):
   sample=" ".join(" ".join(td.stripped_strings) for td in tbl.find_all("tr")[:5]).lower()
   if "total" in sample and (("ibit" in sample and slug=="btc") or ("etha" in sample and slug=="eth")):
    table=tbl;break
  if table is None:return None
  rows=[]
  for tr in table.find_all("tr"):
   cells=[re.sub(r"\s+"," "," ".join(td.stripped_strings)).strip() for td in tr.find_all(["th","td"])]
   if len(cells)<3:continue
   if re.match(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$",cells[0]):
    total=_farside_num(cells[-1])
    if total is not None:rows.append({"date":cells[0],"netFlowUsdM":total})
  if not rows:return None
  vals=[x["netFlowUsdM"] for x in rows]
  return {"provider":"Farside Investors","source":f"U.S. spot {asset} ETF flow table","sourceUrl":f"https://farside.co.uk/{slug}/","asOf":rows[-1]["date"],"netFlowUsdM":rows[-1]["netFlowUsdM"],"netFlow1d":rows[-1]["netFlowUsdM"],"netFlow5d":sum(vals[-5:]),"netFlow21d":sum(vals[-21:]),"history":rows[-60:],"note":f"Flujo neto agregado de todos los emisores ETF spot {asset} incluidos en la columna Total de Farside."}
 except Exception as e:
  print("FARSIDE ETF",asset,type(e).__name__,str(e)[:180]);return None

def _bitcoin_etf_flows():
 return _crypto_spot_etf_flows("BTC")

def _cme_walk(obj):
 if isinstance(obj,dict):
  yield obj
  for v in obj.values():yield from _cme_walk(v)
 elif isinstance(obj,list):
  for v in obj:yield from _cme_walk(v)

def _cme_float(d,*keys):
 for k in keys:
  if d.get(k) not in (None,""):
   v=_farside_num(d.get(k))
   if v is not None:return v
 return None

def _cme_product_id():
 try:
  j=get("https://www.cmegroup.com/CmeWS/mvc/ProductSlate/V2/List",{"pageNumber":"1","sortAsc":"false","sortField":"rank","searchString":"BTC","pageSize":"10"}).json()
  candidates=[]
  for d in _cme_walk(j):
   vals=" ".join(str(d.get(k,"")) for k in ("globex","symbol","code","name","description","productName","productCode")).upper()
   pid=d.get("id") or d.get("Id") or d.get("productId") or d.get("ProductId")
   if pid is not None and ("BTC" in vals or "BITCOIN" in vals):candidates.append((str(pid),vals))
  if not candidates:return None
  candidates.sort(key=lambda x:(0 if "FUTURE" in x[1] else 1,0 if "BTC" in x[1] else 1))
  return candidates[0][0]
 except Exception as e:
  print("CME PRODUCT",type(e).__name__,str(e)[:160]);return None

def _cme_parse_date(v):
 if v in (None,""):return None
 s=str(v).strip()
 for fmt in ("%Y-%m-%d","%m/%d/%Y","%m/%d/%y","%Y%m%d","%d/%m/%Y"):
  try:return datetime.strptime(s[:10],fmt).replace(tzinfo=timezone.utc)
  except Exception:pass
 m=re.search(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})",s)
 if m:
  try:return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)),tzinfo=timezone.utc)
  except Exception:pass
 return None

def _cme_expirations(product_id):
 try:
  arr=get(f"https://www.cmegroup.com/CmeWS/mvc/Settlements/Options/TradeDateAndExpirations/{product_id}").json()
  now=datetime.now(timezone.utc);found={}
  for d in _cme_walk(arr):
   date=None;code=None
   for k,v in d.items():
    kl=str(k).lower()
    if "expiration" in kl or kl in ("expiry","expirydate"):
     if isinstance(v,str):
      date=date or _cme_parse_date(v)
      code=code or (v.strip() if len(v.strip())<=12 else None)
     elif isinstance(v,(int,float)) and v>1e9:
      try:date=date or datetime.fromtimestamp(float(v)/1000 if v>1e11 else float(v),tz=timezone.utc)
      except Exception:pass
    if kl in ("code","expirationcode","monthcode","contractmonth") and v not in (None,""):
     code=code or str(v).strip()
   if date and date>now:found[date.date().isoformat()]=(date,code or date.strftime("%b%y").upper())
  return sorted(found.values(),key=lambda x:x[0])[:3]
 except Exception as e:
  print("CME EXPIRATIONS",type(e).__name__,str(e)[:160]);return []

def _cme_chain(product_id,exp_code):
 try:
  url=f"https://www.cmegroup.com/CmeWS/mvc/Quotes/Option/{product_id}/G/{requests.utils.quote(str(exp_code),safe='')}/ALL"
  j=get(url,{"_":str(int(datetime.now(timezone.utc).timestamp()*1000))}).json()
  quotes=[]
  for d in _cme_walk(j):
   for k,v in d.items():
    if k.lower() in ("optioncontractquotes","quotes","optionquotes") and isinstance(v,list):quotes.extend(v)
  rows=[]
  for x in quotes:
   if not isinstance(x,dict):continue
   K=_cme_float(x,"strikePrice","strike","strike_price","exercisePrice","exercise_price")
   if K is None:continue
   oi=_cme_float(x,"openInterest","open_interest","oi") or 0
   vol=_cme_float(x,"volume","tradeVolume","volumeValue") or 0
   iv=_cme_float(x,"impliedVolatility","iv","markIV","markIv") or 0
   typ=str(x.get("optionType") or x.get("type") or x.get("putCall") or x.get("callPut") or "").upper()
   typ="C" if "CALL" in typ or typ=="C" else "P" if "PUT" in typ or typ=="P" else ""
   if not typ:continue
   if iv>3:iv/=100.0
   rows.append({"strike":K,"openInterest":oi,"volume":vol,"iv":iv,"type":typ})
  return rows
 except Exception as e:
  print("CME CHAIN",exp_code,type(e).__name__,str(e)[:160]);return []

def _cme_btc_option_layer():
 try:
  pid=_cme_product_id()
  if not pid:return None
  exps=_cme_expirations(pid)
  if not exps:return None
  profiles=[];spot=None
  for d,code in exps:
   rows=_cme_chain(pid,code)
   if not rows:continue
   strikes=[x["strike"] for x in rows]
   if spot is None and strikes:
    # CME endpoint is a futures-options chain; use the central listed strike only as fallback.
    ss=sorted(set(strikes));spot=ss[len(ss)//2]
   p=_option_summary(rows,float(spot),d)
   p["bucket"]="CME · "+("NEXT" if not profiles else "SIGUIENTE")
   p["source"]="CME public option quotes · options on BTC futures"
   p["sourceUrl"]="https://www.cmegroup.com/markets/cryptocurrencies/bitcoin/bitcoin.contractSpecs.options.html"
   profiles.append(p)
  if not profiles:return None
  return {"ticker":"BTC-CME","name":"Bitcoin Options · CME futures","spot":float(spot),"profiles":profiles,
          "source":"CME public option quotes","sourceUrl":"https://www.cmegroup.com/markets/cryptocurrencies/bitcoin/bitcoin.contractSpecs.options.html",
          "status":"REAL / DELAYED · CME public chain",
          "method":"Opciones sobre futuros de Bitcoin; Max Pain y paredes usan OI público, GEX/Greeks son modelos."}
 except Exception as e:
  print("CME BTC OPTIONS",type(e).__name__,str(e)[:180]);return None

OPTION_CATALOG=[
 {"family":"S&P 500","code":"SPX","label":"S&P 500 Index","kind":"index","yahoo":"^GSPC","source":"Yahoo Finance · índice de referencia","sourceUrl":"https://finance.yahoo.com/quote/%5EGSPC/"},
 {"family":"S&P 500","code":"SPY","label":"SPDR S&P 500 ETF","kind":"etf","yahoo":"SPY","source":"Yahoo Finance · NYSE Arca","sourceUrl":"https://finance.yahoo.com/quote/SPY/"},
 {"family":"S&P 500","code":"ES","label":"E-mini S&P 500 Futures","kind":"future","yahoo":"ES=F","source":"CME / Yahoo Finance · futuro","sourceUrl":"https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.html"},
 {"family":"Nasdaq-100","code":"NDX","label":"Nasdaq-100 Index","kind":"index","yahoo":"^NDX","source":"Nasdaq · índice de referencia","sourceUrl":"https://www.nasdaq.com/market-activity/index/ndx"},
 {"family":"Nasdaq-100","code":"QQQ","label":"Invesco QQQ ETF","kind":"etf","yahoo":"QQQ","source":"Yahoo Finance · Nasdaq","sourceUrl":"https://finance.yahoo.com/quote/QQQ/"},
 {"family":"Nasdaq-100","code":"NQ","label":"E-mini Nasdaq-100 Futures","kind":"future","yahoo":"NQ=F","source":"CME / Yahoo Finance · futuro","sourceUrl":"https://www.cmegroup.com/markets/equities/nasdaq/nasdaq-100-futures.html"},
 {"family":"Dow Jones","code":"DJI","label":"Dow Jones Industrial Average","kind":"index","yahoo":"^DJI","source":"Yahoo Finance · índice de referencia","sourceUrl":"https://finance.yahoo.com/quote/%5EDJI/"},
 {"family":"Dow Jones","code":"DIA","label":"SPDR Dow Jones ETF","kind":"etf","yahoo":"DIA","source":"Yahoo Finance · NYSE Arca","sourceUrl":"https://finance.yahoo.com/quote/DIA/"},
 {"family":"Dow Jones","code":"YM","label":"E-mini Dow Futures","kind":"future","yahoo":"YM=F","source":"CME / Yahoo Finance · futuro","sourceUrl":"https://www.cmegroup.com/markets/equities/dow-jones.html"},
 {"family":"Russell 2000","code":"RUT","label":"Russell 2000 Index","kind":"index","yahoo":"^RUT","source":"Yahoo Finance · índice de referencia","sourceUrl":"https://finance.yahoo.com/quote/%5ERUT/"},
 {"family":"Russell 2000","code":"IWM","label":"iShares Russell 2000 ETF","kind":"etf","yahoo":"IWM","source":"Yahoo Finance · NYSE Arca","sourceUrl":"https://finance.yahoo.com/quote/IWM/"},
 {"family":"Russell 2000","code":"RTY","label":"E-mini Russell 2000 Futures","kind":"future","yahoo":"RTY=F","source":"CME / Yahoo Finance · futuro","sourceUrl":"https://www.cmegroup.com/markets/equities/russell-2000.html"},
 {"family":"DAX","code":"DAX","label":"DAX Index","kind":"index","yahoo":"^GDAXI","source":"Deutsche Börse / Yahoo Finance · índice","sourceUrl":"https://finance.yahoo.com/quote/%5EGDAXI/"},
 {"family":"DAX","code":"FDAX","label":"DAX Futures","kind":"future","eurex":"https://www.eurex.com/ex-en/markets/idx/dax/DAX-Futures-34642","source":"Eurex · FDAX","sourceUrl":"https://www.eurex.com/ex-en/markets/idx/dax/DAX-Futures-34642"},
 {"family":"DAX","code":"ODAX","label":"DAX Options","kind":"option_index","eurex":"https://www.eurex.com/ex-en/markets/idx/dax/DAX-Options-139884","source":"Eurex · ODAX","sourceUrl":"https://www.eurex.com/ex-en/markets/idx/dax/DAX-Options-139884"},
 {"family":"EURO STOXX 50","code":"SX5E","label":"EURO STOXX 50 Index","kind":"index","yahoo":"^STOXX50E","source":"Yahoo Finance · índice de referencia","sourceUrl":"https://finance.yahoo.com/quote/%5ESTOXX50E/"},
 {"family":"EURO STOXX 50","code":"FESX","label":"EURO STOXX 50 Futures","kind":"future","eurex":"https://www.eurex.com/ex-en/markets/idx/stx/euro-stoxx-50-derivatives/products/EURO-STOXX-50-Index-Futures-34652","source":"Eurex · FESX","sourceUrl":"https://www.eurex.com/ex-en/markets/idx/stx/euro-stoxx-50-derivatives/products/EURO-STOXX-50-Index-Futures-34652"},
 {"family":"EURO STOXX 50","code":"OESX","label":"EURO STOXX 50 Options","kind":"option_index","eurex":"https://www.eurex.com/ex-en/markets/idx/stx/euro-stoxx-50-derivatives/products/EURO-STOXX-50-Index-Options-46548","source":"Eurex · OESX","sourceUrl":"https://www.eurex.com/ex-en/markets/idx/stx/euro-stoxx-50-derivatives/products/EURO-STOXX-50-Index-Options-46548"},
 {"family":"Gold","code":"XAU","label":"Gold Spot · referencia","kind":"spot_reference","source":"Referencia spot · sin cadena propia aquí","sourceUrl":"https://www.cmegroup.com/markets/metals/precious/gold.html"},
 {"family":"Gold","code":"GC","label":"COMEX Gold Futures","kind":"future","yahoo":"GC=F","source":"CME / Yahoo Finance · futuro","sourceUrl":"https://www.cmegroup.com/markets/metals/precious/gold.html"},
 {"family":"Gold","code":"GLD","label":"SPDR Gold Shares ETF","kind":"etf","yahoo":"GLD","source":"Yahoo Finance · NYSE Arca","sourceUrl":"https://finance.yahoo.com/quote/GLD/"},
 {"family":"Gold","code":"IAU","label":"iShares Gold Trust ETF","kind":"etf","yahoo":"IAU","source":"Yahoo Finance · NYSE Arca","sourceUrl":"https://finance.yahoo.com/quote/IAU/"},
 {"family":"Silver","code":"SI","label":"COMEX Silver Futures","kind":"future","yahoo":"SI=F","source":"CME / Yahoo Finance · futuro","sourceUrl":"https://www.cmegroup.com/markets/metals/precious/silver.html"},
 {"family":"Silver","code":"SLV","label":"iShares Silver Trust ETF","kind":"etf","yahoo":"SLV","source":"Yahoo Finance · NYSE Arca","sourceUrl":"https://finance.yahoo.com/quote/SLV/"},
 {"family":"WTI","code":"CL","label":"WTI Crude Futures","kind":"future","yahoo":"CL=F","source":"NYMEX/CME · futuro","sourceUrl":"https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.html"},
 {"family":"WTI","code":"USO","label":"United States Oil Fund ETF","kind":"etf","yahoo":"USO","source":"Yahoo Finance · NYSE Arca","sourceUrl":"https://finance.yahoo.com/quote/USO/"},
 {"family":"Brent","code":"BZ","label":"Brent Crude Futures","kind":"future","yahoo":"BZ=F","source":"ICE / Yahoo Finance · futuro","sourceUrl":"https://www.theice.com/products/219/Brent-Crude-Futures"},
 {"family":"Brent","code":"BNO","label":"United States Brent Oil Fund ETF","kind":"etf","yahoo":"BNO","source":"Yahoo Finance · NYSE Arca","sourceUrl":"https://finance.yahoo.com/quote/BNO/"},
 {"family":"Volatilidad","code":"VIX","label":"Cboe Volatility Index","kind":"index","yahoo":"^VIX","source":"Cboe · índice de volatilidad","sourceUrl":"https://www.cboe.com/tradable_products/vix/"},
 {"family":"Cripto","code":"IBIT","label":"iShares Bitcoin Trust ETF","kind":"etf","yahoo":"IBIT","source":"Yahoo Finance · Nasdaq","sourceUrl":"https://finance.yahoo.com/quote/IBIT/"},
 {"family":"Cripto","code":"BTC","label":"Bitcoin","kind":"crypto","yahoo":"BTC-USD","source":"Yahoo Finance · spot proxy","sourceUrl":"https://finance.yahoo.com/quote/BTC-USD/"},
 {"family":"Cripto","code":"ETH","label":"Ethereum","kind":"crypto","yahoo":"ETH-USD","source":"Yahoo Finance · spot proxy","sourceUrl":"https://finance.yahoo.com/quote/ETH-USD/"},
 {"family":"Acciones referencia","code":"AAPL","label":"Apple","kind":"stock","yahoo":"AAPL","source":"Yahoo Finance · Nasdaq","sourceUrl":"https://finance.yahoo.com/quote/AAPL/"},
 {"family":"Acciones referencia","code":"NVDA","label":"NVIDIA","kind":"stock","yahoo":"NVDA","source":"Yahoo Finance · Nasdaq","sourceUrl":"https://finance.yahoo.com/quote/NVDA/"},
 {"family":"Macro · Crédito","code":"HYG","label":"iShares High Yield Corporate Bond ETF","kind":"etf","yahoo":"HYG","source":"Yahoo Finance · NYSE Arca","sourceUrl":"https://finance.yahoo.com/quote/HYG/"},
 {"family":"Macro · Duración","code":"TLT","label":"iShares 20+ Year Treasury Bond ETF","kind":"etf","yahoo":"TLT","source":"Yahoo Finance · Nasdaq","sourceUrl":"https://finance.yahoo.com/quote/TLT/"}
]

def _latest_yahoo_quote(sym):
 try:
  r=chart(sym)
  if not r:return None
  ts=r.get("timestamp") or [];q=(r.get("indicators",{}).get("quote") or [{}])[0].get("close") or []
  vals=[(t,v) for t,v in zip(ts,q) if v is not None]
  if not vals:return None
  t,v=vals[-1]
  dt=datetime.fromtimestamp(float(t),tz=timezone.utc)
  prev=vals[-2][1] if len(vals)>1 else None
  return {"last":float(v),"previousClose":float(prev) if prev is not None else None,
          "change1d":(float(v)/float(prev)-1)*100 if prev not in (None,0) else None,
          "asOf":dt.isoformat(),"date":dt.date().isoformat(),"delayNote":"Último cierre disponible desde Yahoo Finance; puede estar retrasado fuera de sesión."}
 except Exception as e:
  print("REFERENCE QUOTE",sym,type(e).__name__,str(e)[:120]);return None

def _barchart_option_overview(sym):
 try:
  html=get("https://www.barchart.com/stocks/quotes/"+requests.utils.quote(sym,safe="")+"/overview").text
  text=" ".join(BeautifulSoup(html,"html.parser").stripped_strings)
  pats={
   "iv":"Implied Volatility\\s+([0-9.]+)%",
   "ivPercentile":"IV Percentile\\s+([0-9.]+)%",
   "ivRank":"IV Rank\\s+([0-9.]+)%",
   "ivHigh":"IV High\\s+([0-9.]+)%",
   "ivLow":"IV Low\\s+([0-9.]+)%",
   "putCallVol":"Put/Call Vol Ratio\\s+([0-9.]+)",
   "putCallOi":"Put/Call OI Ratio\\s+([0-9.]+)",
   "expectedMove":"Expected Move \\(DTE [0-9]+\\)\\s+([0-9.]+)",
   "expectedMovePct":"Expected Move \\(DTE [0-9]+\\)\\s+[0-9.]+ \\(([0-9.]+)%\\)"
  }
  out={}
  for k,p in pats.items():
   m=re.search(p,text,re.I)
   if(m):out[k]=float(m.group(1))
  if not out:return None
  out["source"]="Barchart · Options Overview";out["sourceUrl"]="https://www.barchart.com/stocks/quotes/"+sym+"/overview";out["dataStatus"]="REAL / DELAYED · Barchart";out["asOf"]="Último snapshot visible de Barchart"
  return out
 except Exception as e:
  print("BARCHART OPTIONS",sym,type(e).__name__,str(e)[:140]);return None

def _eurex_snapshot(entry):
 try:
  html=get(entry["eurex"]).text
  text=" ".join(BeautifulSoup(html,"html.parser").stripped_strings)
  out={"source":entry["source"],"sourceUrl":entry["sourceUrl"],"dataStatus":"REAL / DELAYED · Eurex","asOfDate":None}
  m=re.search(r"Trading Date\s+(\d{2}/\d{2}/\d{4})",text)
  if m:out["asOfDate"]=m.group(1)
  for key,label in (("volume","Volume"),("openInterest","Open Interest"),("putCallRatio","Put/Call ratio"),("underlyingClose","Underlying closing price")):
   m=re.search(re.escape(label)+r"\\s+([0-9][0-9,]*(?:\\.[0-9]+)?)",text,re.I)
   if m:
    v=_farside_num(m.group(1))
    if v is not None:out[key]=v
  rows=[]
  rgx=re.compile(r"(W|M|E|Q|S|Y)\\s+(\\d{2}/\\d{2}/\\d{4})\\s+([0-9,]+)\\s+([0-9,]+)\\s+([0-9,]+)\\s+([0-9,]+)\\s+([0-9.]+|n/a)",re.I)
  for m in rgx.finditer(text):
   rows.append({"type":m.group(1),"date":m.group(2),"callVolume":_farside_num(m.group(3)),"callOI":_farside_num(m.group(4)),"putVolume":_farside_num(m.group(5)),"putOI":_farside_num(m.group(6)),"putCall":_farside_num(m.group(7))})
  if rows:out["expiryStats"]=rows[:12]
  return out if len(out)>3 else None
 except Exception as e:
  print("EUREX SNAPSHOT",entry.get("code"),type(e).__name__,str(e)[:140]);return None

def _option_reference_entry(entry):
 q=_latest_yahoo_quote(entry["yahoo"]) if entry.get("yahoo") else None
 if not q:return None
 out={**entry,"ticker":entry["code"],"name":entry["label"],"referenceOnly":True,"spot":q["last"],"quote":q,"source":entry["source"],"sourceUrl":entry["sourceUrl"],
      "dataStatus":"REAL / DELAYED · último dato disponible","asOf":q["asOf"],"method":"Referencia de precio; la cadena de opciones no está disponible públicamente en esta capa."}
 if entry["code"] in ("SPY","QQQ","DIA","IWM","GLD","IAU","USO","BNO","AAPL","NVDA","HYG","TLT"):
  stats=_barchart_option_overview(entry["code"])
  if stats:out["stats"]=stats
 return out

def update_options(feed):
 previous=feed.get("options",{}) if isinstance(feed.get("options"),dict) else {}
 old_by={m.get("ticker"):m for m in previous.get("markets",[]) if isinstance(m,dict) and m.get("ticker")}
 chain_targets=("SPX","SPY","NDX","QQQ","RUT","IWM","DIA","GLD","IAU","SLV","USO","BNO","AAPL","NVDA","HYG","TLT","IBIT")
 detailed={}
 # Preferred chain source: Massive. Yahoo remains a public fallback.
 for sym in chain_targets:
  try:
   x=_massive_option_chain(sym)
   if x:detailed[sym]=x
  except Exception as e:print("MASSIVE TARGET",sym,type(e).__name__,str(e)[:120])
 for sym in ("SPY","QQQ","DIA","IWM","GLD","IAU","USO","BNO","AAPL","NVDA","HYG","TLT","IBIT"):
  if sym in detailed:continue
  try:
   x=opt(sym)
   if x:detailed[sym]=x
  except Exception as e:print("OPTIONS",sym,type(e).__name__,str(e)[:160])

 out=[]
 for entry in OPTION_CATALOG:
  code=entry["code"]
  x=detailed.get(code)
  if x:
   stats=_barchart_option_overview(code)
   if stats:
    x["stats"]=stats
    p0=(x.get("profiles") or [{}])[0]
    for k in ("ivRank","ivPercentile","iv","putCallVol","putCallOi","expectedMove","expectedMovePct"):
     if stats.get(k) is not None:p0[k]=stats[k]
   x["family"]=entry["family"];x["instrumentCode"]=code;x["instrumentKind"]=entry["kind"]
   x["sourceDate"]=x.get("asOf") or datetime.now(timezone.utc).isoformat()
   out.append(x);continue
  if entry.get("eurex"):
   ex=_eurex_snapshot(entry)
   if ex:
    q=ex.get("underlyingClose")
    out.append({**entry,"ticker":code,"name":entry["label"],"referenceOnly":True,"spot":q,
                "quote":ex,"stats":ex,"dataStatus":ex.get("dataStatus"),"asOf":ex.get("asOfDate"),
                "method":"Eurex: último snapshot público disponible. Sin cadena de strikes no se inventan Max Pain/GEX."})
    continue
  if entry.get("yahoo"):
   ref=_option_reference_entry(entry)
   if ref:out.append(ref)

 # SPX GEX fallback only if no full chain arrived from Massive/Yahoo.
 sf=feed.get("squawkFlow",{}) if isinstance(feed.get("squawkFlow"),dict) else {}
 sx=sf.get("spxGex",{}).get("data") if isinstance(sf.get("spxGex"),dict) else None
 if isinstance(sx,dict) and not any(m.get("ticker")=="SPX" and not m.get("referenceOnly") for m in out):
  spxprof={"expiration":sx.get("asOfDate"),"daysToExpiry":None,"gammaNet":sx.get("netGex"),
           "gammaFlip":sx.get("gexFlipPrice"),"callWall":sx.get("callWall"),"putWall":sx.get("putWall"),
           "callWallOi":sx.get("callWall"),"putWallOi":sx.get("putWall"),"maxGammaStrike":sx.get("maxGammaStrike"),
           "volTrigger":sx.get("volTrigger"),"bucket":"SPX · GEX model","source":"SquawkFlow / Cboe OI-derived estimate",
           "dataStatus":"REAL / DELAYED · OI-derived"}
  spx={"ticker":"SPX","instrumentCode":"SPX","family":"S&P 500","name":"S&P 500 Index · SPX",
       "spot":sx.get("spotPrice"),"profiles":[spxprof],"referenceOnly":False,
       "source":"SquawkFlow · SPX GEX model","sourceUrl":"https://squawkflow.com/docs/endpoints",
       "dataStatus":"REAL / DELAYED · calculated from Cboe open interest",
       "method":"Fallback GEX model from Cboe open interest; used only when a full chain source is unavailable."}
  out=[m for m in out if m.get("ticker")!="SPX"];out.insert(0,spx)

 # Crypto options: Deribit is primary; CME is a separate layer, never merged into Deribit metrics.
 for ccy in ("BTC","ETH"):
  try:
   der=_deribit_options(ccy)
   if der:
    crypto=dict(der);crypto["ticker"]=ccy;crypto["instrumentCode"]=ccy;crypto["family"]="Cripto";crypto["referenceOnly"]=False
    crypto["dataStatus"]="REAL / DELAYED · Deribit public options"
    crypto["method"]="Deribit public options. GEX/Gamma Flip are modeled from public OI/Greeks; CME and ETF layers remain separate."
    if ccy=="BTC":
     crypto["btcPerspective"]=True
     crypto["layers"]={"deribit":der,"cme":_cme_btc_option_layer(),"spotEtfFlows":_crypto_spot_etf_flows(ccy)}
    out=[m for m in out if m.get("ticker")!=ccy];out.append(crypto)
  except Exception as e:print("CRYPTO OPTIONS",ccy,type(e).__name__,str(e)[:160])

 present={x.get("ticker") for x in out}
 for code,m in old_by.items():
  if code not in present and m.get("profiles"):
   m=dict(m);m["dataStatus"]="UNAVAILABLE · último snapshot válido retenido";m["updatedAttempt"]=datetime.now(timezone.utc).isoformat();out.append(m)

 flow=feed.get("squawkFlow",{}) if isinstance(feed.get("squawkFlow"),dict) else {}
 flow_data=flow.get("unusualOptions",{}).get("data") if isinstance(flow.get("unusualOptions"),dict) else []
 flow_data=flow_data[:30] if isinstance(flow_data,list) else []

 hist=dict(previous.get("history") or {});stamp=datetime.now(timezone.utc).isoformat()
 for m in out:
  if m.get("referenceOnly"):continue
  p=(m.get("profiles") or [{}])[0];arr=hist.get(m.get("ticker"),[])
  snap={"asOf":stamp,"expiration":m.get("expiration") or p.get("expiration"),"spot":m.get("spot"),
        "gammaNet":p.get("gammaNet"),"gammaFlip":p.get("gammaFlip"),"maxPain":p.get("maxPain"),
        "callWall":p.get("callWallOi") or p.get("callWall"),"putWall":p.get("putWallOi") or p.get("putWall"),
        "ivAtm":p.get("ivAtm"),"expectedMove":p.get("expectedMove"),"riskReversal25d":p.get("riskReversal25d")}
  arr=[h for h in arr if not (h.get("expiration")==snap.get("expiration") and h.get("asOf","")[:10]==stamp[:10])]
  arr.append(snap);hist[m.get("ticker")]=arr[-180:]

 feed["options"]={
  "updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
  "markets":out,"history":hist,"flow":flow_data,
  "optionsStats":feed.get("optionsStats") if isinstance(feed.get("optionsStats"),dict) else {},
  "catalog":OPTION_CATALOG,
  "source":"Massive full-chain snapshots + Cboe + Barchart + Deribit/CME + Yahoo fallback",
  "sourceStatus":"REAL / DELAYED · multi-source",
  "publication":"Massive supplies chain-level OI/volume/IV/Greeks where available; Cboe supplies market-wide statistics; Barchart complements IV rank/percentile; Deribit is primary crypto chain; Yahoo is fallback only.",
  "note":"No se rellenan métricas inexistentes. Reference-only instruments muestran precio/fecha y explican por qué no hay cadena. Max Pain/GEX/Gamma Flip/DEX son cálculos sobre snapshots públicos y no observación directa del libro de dealers."
 }
def update_dark_pools(feed):
    token=finra_access_token()
    if not token:return
    auth={"Authorization":"Bearer "+token,"Content-Type":"application/json","Accept":"application/json","Data-API-Version":"1"}
    try:
        part=post("https://api.finra.org/partitions/group/otcmarket/name/weeklySummary",{},auth).json()
        vals=[]
        for x in part.get("availablePartitions",[]) if isinstance(part,dict) else []:
            p=(x.get("partitions") or []) if isinstance(x,dict) else []
            vals += [str(v)[:10] for v in p]
        weeks=sorted(set(v for v in vals if re.match(r"^20\\d\\d-\\d\\d-\\d\\d$",v)),reverse=True)[:8]
    except Exception as e:
        print("FINRA PARTITIONS",type(e).__name__,str(e)[:160]); weeks=[]
    if not weeks:
        # Fallback: recent Mondays, because FINRA requires weekStartDate to be a Monday.
        today=datetime.now(timezone.utc).date()
        monday=today-timedelta(days=today.weekday())
        weeks=[str(monday-timedelta(days=7*i)) for i in range(8)]
    symbols=("SPY","QQQ","GLD","USO","AAPL","NVDA","HYG")
    out=[]; old=feed.get("darkPools",{}) if isinstance(feed.get("darkPools"),dict) else {}; old_hist=dict(old.get("history") or {})
    for sym in symbols:
        found=None
        for week in weeks:
            try:
                payload={"limit":1000,"fields":["issueSymbolIdentifier","issueName","MPID","marketParticipantName","weekStartDate","summaryStartDate","initialPublishedDate","lastReportedDate","lastUpdateDate","totalWeeklyTradeCount","totalWeeklyShareQuantity","tierIdentifier","summaryTypeCode"],
                         "compareFilters":[
                           {"compareType":"equal","fieldName":"tierIdentifier","fieldValue":"T1"},
                           {"compareType":"equal","fieldName":"weekStartDate","fieldValue":week},
                           {"compareType":"equal","fieldName":"summaryTypeCode","fieldValue":"ATS_W_SMBL"},
                           {"compareType":"equal","fieldName":"issueSymbolIdentifier","fieldValue":sym}]}
                ats=post("https://api.finra.org/data/group/otcmarket/name/weeklySummary",payload,auth).json()
                payload["compareFilters"][2]["fieldValue"]="OTC_W_SMBL"
                otc=post("https://api.finra.org/data/group/otcmarket/name/weeklySummary",payload,auth).json()
                ats=ats if isinstance(ats,list) else []; otc=otc if isinstance(otc,list) else []
                if not ats and not otc: continue
                rows=ats+otc
                found={"symbol":sym,"weekStart":week,
                       "initialPublishedDate":max([str(x.get("initialPublishedDate") or "") for x in rows])[:10],
                       "lastReportedDate":max([str(x.get("lastReportedDate") or "") for x in rows])[:10],
                       "lastUpdateDate":max([str(x.get("lastUpdateDate") or "") for x in rows])[:10],
                       "atsShares":sum(float(x.get("totalWeeklyShareQuantity") or 0) for x in ats),
                       "otcShares":sum(float(x.get("totalWeeklyShareQuantity") or 0) for x in otc),
                       "atsTrades":sum(float(x.get("totalWeeklyTradeCount") or 0) for x in ats),
                       "otcTrades":sum(float(x.get("totalWeeklyTradeCount") or 0) for x in otc)}
                found["totalOffExchange"]=found["atsShares"]+found["otcShares"]
                found["avgSharesPerTrade"]=found["totalOffExchange"]/max(found["atsTrades"]+found["otcTrades"],1)
                found["lagLabel"]="FINRA · T1 · publicación con retraso"
                found["note"]="ATS + OTC agregado. No identifica comprador/vendedor ni demuestra acumulación por precio."
                break
            except Exception as e:
                print("FINRA",sym,week,type(e).__name__,str(e)[:120])
        if found:
            hist=[]
            for h in old_hist.get(sym,[]):
                if isinstance(h,dict) and h.get("weekStart")!=found["weekStart"]:
                    hist.append({k:v for k,v in h.items() if k!="history"})
            snapshot={k:v for k,v in found.items() if k not in ("history","zScore")}
            hist.append(snapshot)
            hist=sorted(hist,key=lambda x:x.get("weekStart",""))[-12:]
            vals=[h.get("totalOffExchange") for h in hist if h.get("totalOffExchange") is not None]
            found["zScore"]=zscore(vals,found["totalOffExchange"])
            found["history"]=[{k:v for k,v in h.items() if k!="history"} for h in hist]
            old_hist[sym]=found["history"]
            out.append(found)
    if out:
        feed["darkPools"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"history":old_hist,
                           "source":"FINRA OTC Transparency","sourceUrl":"https://www.finra.org/filing-reporting/otc-transparency",
                           "method":"Weekly Summary production dataset · rolling 12 months; se consulta la partición semanal más reciente disponible.","coverage":"T1 · ATS_W_SMBL + OTC_W_SMBL",
                           "dataStatus":"REAL AGGREGATED FINRA DATA · DELAYED"}

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


def _nested_print_rows(obj):
 rows=[]
 if isinstance(obj,dict):
  keys={str(k).lower() for k in obj}
  if ({'ticker','symbol'} & keys) and ({'size','shares','quantity','trade_size'} & keys) and ({'price','execution_price','trade_price','last_price'} & keys):
   rows.append(obj)
  for v in obj.values(): rows.extend(_nested_print_rows(v))
 elif isinstance(obj,list):
  for v in obj: rows.extend(_nested_print_rows(v))
 return rows

def _capitol_structured_rows(soup):
 out=[]
 for tag in soup.find_all("script"):
  txt=tag.string or tag.get_text("",strip=False)
  if not txt:continue
  if tag.get("id")=="__NEXT_DATA__":
   try: out.extend(_nested_print_rows(json.loads(txt)))
   except Exception: pass
  # Look for compact JSON state blocks with obvious print keys.
  if "dark" in txt.lower() and ("price" in txt.lower()) and ("size" in txt.lower()):
   for raw in re.findall(r'(?s)\{[^{}]{0,12000}\}',txt):
    try: out.extend(_nested_print_rows(json.loads(raw)))
    except Exception: pass
 return out

def _time_to_session_ts(ts_text, series):
 if not ts_text or not series:return None
 m=re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$',str(ts_text).strip())
 if not m:return None
 hh,mm,ss=int(m.group(1)),int(m.group(2)),int(m.group(3) or 0)
 try:
  ny=ZoneInfo("America/New_York")
  session=datetime.fromtimestamp(series[-1]["ts"],tz=timezone.utc).astimezone(ny).date()
  target=datetime(session.year,session.month,session.day,hh,mm,ss,tzinfo=ny).timestamp()
  return target
 except Exception:return None

def update_dark_pool_prints(feed):
 prints=[]; sources=[]; assets={}
 universe={
  "SPY":{"label":"SPY","proxyFor":"S&P 500 E-Mini"},"QQQ":{"label":"QQQ","proxyFor":"Nasdaq-100"},"DIA":{"label":"DIA","proxyFor":"Dow Jones"},
  "UUP":{"label":"UUP","proxyFor":"DXY / USD Index"},"FXE":{"label":"FXE","proxyFor":"Euro FX"},"GLD":{"label":"GLD","proxyFor":"Gold"},"SLV":{"label":"SLV","proxyFor":"Silver"},
  "USO":{"label":"USO","proxyFor":"WTI"},"BNO":{"label":"BNO","proxyFor":"Brent"},"AAPL":{"label":"AAPL","proxyFor":"Equity"},"NVDA":{"label":"NVDA","proxyFor":"Equity"},"IWM":{"label":"IWM","proxyFor":"Small Caps"}
 }
 try:
  html=get("https://capitolwhale.com/dark-pool-prints").text
  soup=BeautifulSoup(html,"html.parser"); text=" ".join(soup.stripped_strings)
  def money(pattern):
   m=re.search(pattern,text,re.I);return _parse_money_token(m.group(1)) if m else None
  def pct(pattern):
   m=re.search(pattern,text,re.I);return float(m.group(1)) if m else None
  def integer(pattern):
   m=re.search(pattern,text,re.I);return int(m.group(1).replace(",","")) if m else None

  print_count=integer(r'\bPrints\s+([\d,]+)'); total_premium=money(r'Total premium\s+\$?([\d.,]+[KMB]?)')
  bullish=pct(r'Bullish\s+([\d.]+)%'); largest=money(r'Largest\s+\$?([\d.,]+[KMB]?)')
  mb=re.search(r'Aggressor imbalance\s+Buy\s+([\d.]+)%\s*Sell\s+([\d.]+)%',text,re.I)
  buy_pct=float(mb.group(1)) if mb else None; sell_pct=float(mb.group(2)) if mb else None

  structured=_capitol_structured_rows(soup); structured_count=0
  for row in structured:
   sym=str(row.get("ticker") or row.get("symbol") or "").upper()
   if sym not in universe:continue
   p=_norm_dark_print(row,sym,"Capitol Whale · structured free data")
   if not p.get("timestamp") or not p.get("size"):continue
   p["sourceMode"]="EXACT_STRUCTURED"; prints.append(p);structured_count+=1

  # Server-rendered compact rows remain useful fallback when structured data is not exposed.
  seen={(x["ticker"],str(x.get("timestamp")),round(float(x.get("size") or 0),2)) for x in prints}
  for raw in soup.stripped_strings:
   p=_parse_capitol_print_line(raw)
   if not p:continue
   if p["ticker"] not in universe:continue
   key=(p["ticker"],str(p["time"]),round(float(p.get("size") or 0),2))
   if key in seen:continue
   p.update({"timestamp":p.pop("time"),"price":None,"priceApprox":None,"notional":None,"side":"UNKNOWN","directionConfidence":None,
             "sideBasis":"No individual side in free compact row","source":"Capitol Whale · free public view","realPrint":True,"sourceMode":"COMPACT"})
   prints.append(p);seen.add(key)
  prints=prints[-300:]
  if prints:sources.append("Capitol Whale")
 except Exception as e:
  print("CAPITOL DARK PRINTS",type(e).__name__,str(e)[:180])
  print_count=total_premium=bullish=largest=buy_pct=sell_pct=None;structured_count=0

 for t,meta in universe.items():
  try:
   series=yahoo_intraday(t,"5m","1d") or []
   spot=series[-1]["price"] if series else None
   # Enrich every visible print with exact structured price when available; otherwise
   # use the market price nearest to the reported print time and label it as an approximation.
   arr=[]
   for p in prints:
    if p["ticker"]!=t:continue
    if p.get("price") is None:
     target=_time_to_session_ts(p.get("timestamp"),series)
     if target and series:
      nearest=min(series,key=lambda z:abs(float(z["ts"])-target))
      p["priceApprox"]=nearest["price"];p["approxTs"]=nearest["ts"]
      p["priceBasis"]="Yahoo 5m close nearest to print timestamp"
    else:
      p["priceBasis"]="Provider exact execution price"
    if p.get("price") is not None and p.get("notional") is None and p.get("size"):p["notional"]=float(p["price"])*float(p["size"])
    if p.get("priceApprox") is not None and p.get("notional") is None and p.get("size"):p["notional"]=float(p["priceApprox"])*float(p["size"])
    arr.append(p)
   cs=chart_exchange_offexchange(t) or {}
   venue_map={}
   for p in arr:
    venue=str(p.get("venue") or "TRF"); z=venue_map.setdefault(venue,{"venue":venue,"prints":0,"shares":0,"notional":0})
    z["prints"]+=1;z["shares"]+=float(p.get("size") or 0);z["notional"]+=float(p.get("notional") or 0)
   assets[t]={"ticker":t,"label":meta.get("label",t),"proxyFor":meta.get("proxyFor"),"lastPrice":spot,"priceSeries":series[-90:],"prints":arr,
     "printCount":len(arr),"shareCount":sum(float(x.get("size") or 0) for x in arr),
     "notional":sum(float(x.get("notional") or 0) for x in arr),
     "dailyOffExchange":cs,"venueClusters":sorted(venue_map.values(),key=lambda x:x["shares"],reverse=True)[:8],
     "source":"Capitol Whale free prints + Yahoo intraday overlay + ChartExchange public off-exchange totals",
     "note":"Los prints son ejecuciones TRF reales. Cuando el proveedor gratuito no expone precio por fila, el punto usa el cierre Yahoo 5m más cercano a la hora del print y queda etiquetado como aproximación."}
  except Exception as e:print("DARK ASSET",t,type(e).__name__,str(e)[:140])

 feed["darkPoolPrints"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"prints":prints,"assets":assets,"sources":sources,
   "printCount":print_count,"totalPremium":total_premium,"bullishPct":bullish,"largestPrintPremium":largest,"buyPct":buy_pct,"sellPct":sell_pct,
   "topTickers":[],"structuredPrints":structured_count,"dataStatus":"REAL TRF PRINTS · EXACT PRICE WHEN PUBLIC STRUCTURED DATA IS EXPOSED; OTHERWISE 5M PRICE OVERLAY",
   "free":True,"documentedDelay":"Capitol Whale free core view is intraday; SensaMarket free view is ~4h delayed.",
   "note":"BUY/SELL agregado y cualquier side individual se tratan como inferencia cuando no hay dato explícito. No identifica la cartera final."}


def update_traditional_fear_greed(feed):
 previous=feed.get("traditionalFearGreed",{}) if isinstance(feed.get("traditionalFearGreed"),dict) else {}
 result={**previous,"score":previous.get("score"),"rating":previous.get("rating","—"),"timestamp":previous.get("timestamp"),"previous_close":previous.get("previous_close"),"previous_1_week":previous.get("previous_1_week"),"previous_1_month":previous.get("previous_1_month"),"previous_1_year":previous.get("previous_1_year"),"history":previous.get("history",[]),"components":previous.get("components",{}),"source":"CNN Fear & Greed Index","sourceUrl":"https://www.cnn.com/markets/fear-and-greed","sourceStatus":"UNAVAILABLE · last valid snapshot retained"}
 try:
  headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153.0 Safari/537.36","Accept":"application/json, text/plain, */*","Origin":"https://www.cnn.com","Referer":"https://www.cnn.com/"}
  d=get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",h=headers).json()
  fg=d.get("fear_and_greed",{})
  result.update({k:fg.get(k) for k in ("score","rating","timestamp","previous_close","previous_1_week","previous_1_month","previous_1_year")})
  hist=(d.get("fear_and_greed_historical") or {}).get("data") or []
  result["history"]=[{"date":datetime.fromtimestamp(float(x.get("x",0))/1000,tz=timezone.utc).strftime("%Y-%m-%d"),"value":float(x.get("y"))} for x in hist if x.get("x") is not None and x.get("y") is not None][-90:]
  result["components"]={}
  for k,v in d.items():
   if k.startswith("market_") or k in ("stock_price_strength","stock_price_breadth","put_call_options","junk_bond_demand","safe_haven_demand"):
    if isinstance(v,dict):
     val=v.get("score",v.get("value"))
     if val is not None:result["components"][k]=val
  result["sourceStatus"]="REAL / DAILY"
 except Exception as e:
  print("CNN F&G",type(e).__name__,str(e)[:180])
 result["updated"]=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
 feed["traditionalFearGreed"]=result

def update_traditional_sentiment(feed):
    result={"bullishPct":28.8,"neutralPct":17.9,"bearishPct":53.3,"previousBullishPct":38.0,"previousNeutralPct":22.7,"previousBearishPct":39.3,"week":"2026-09-16","source":"AAII Investor Sentiment Survey","sourceUrl":"https://www.aaii.com/sentimentsurvey","bullBearSpread":-24.5,"history":[]}
    try:
        html=get("https://www.aaii.com/sentimentsurvey").text
        vals=re.findall(r'Bullish.*?([0-9]+\.[0-9]+)%.*?Neutral.*?([0-9]+\.[0-9]+)%.*?Bearish.*?([0-9]+\.[0-9]+)%',html,re.I|re.S)
        if vals:
            bb,nn,br=map(float,vals[0]); result.update(bullishPct=bb,neutralPct=nn,bearishPct=br,bullBearSpread=round(bb-br,1))
    except Exception as e: print("AAII",type(e).__name__,str(e)[:180])
    result["updated"]=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    feed["traditionalSentiment"]=result

def update_options_market_stats(feed):
 try:
  html=get("https://www.cboe.com/data/mktstat.aspx").text
  patterns={
   "totalPutCall":r"TOTAL PUT/CALL RATIO\D+([0-9.]+)",
   "indexPutCall":r"INDEX PUT/CALL RATIO\D+([0-9.]+)",
   "etpPutCall":r"EXCHANGE TRADED PRODUCTS PUT/CALL RATIO\D+([0-9.]+)",
   "equityPutCall":r"EQUITY PUT/CALL RATIO\D+([0-9.]+)",
   "vixPutCall":r"CBOE VOLATILITY INDEX \(VIX\) PUT/CALL RATIO\D+([0-9.]+)",
   "spxPutCall":r"SPX \+ SPXW PUT/CALL RATIO\D+([0-9.]+)",
   "russellPutCall":r"MRUT PUT/CALL RATIO\D+([0-9.]+)"
  }
  out={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"source":"Cboe Daily Market Statistics","sourceUrl":"https://www.cboe.com/data/mktstat.aspx","dataStatus":"REAL / DAILY · Cboe public statistics"}
  for k,p in patterns.items():
   m=re.search(p,html,re.I)
   if m:out[k]=float(m.group(1))
  def section(title):
   pos=html.upper().find(title.upper())
   if pos<0:return {}
   chunk=html[pos:pos+7000];z={}
   for metric in ("VOLUME","OPEN INTEREST"):
    m=re.search(metric+r".{0,500}?([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)",chunk,re.I|re.S)
    if m:z[metric.lower().replace(" ","_")]={"call":int(m.group(1).replace(",","")),"put":int(m.group(2).replace(",","")),"total":int(m.group(3).replace(",",""))}
   return z
  for name,title in (("all","SUM OF ALL PRODUCTS"),("index","INDEX OPTIONS"),("etp","EXCHANGE TRADED PRODUCTS"),("equity","EQUITY OPTIONS")):
   z=section(title)
   if z:out[name]=z
  feed["optionsStats"]=out
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
 sector_cfg=[("Tecnología","XLK"),("Energía","XLE"),("Financieras","XLF"),("Industriales","XLI"),("Salud","XLV"),("Consumo discrecional","XLY"),("Consumo básico","XLP"),("Utilities","XLU"),("Materiales","XLB"),("Comunicación","XLC"),("REITs","XLRE")]
 style_cfg=[("Growth vs Value","VUG","VTV"),("Cíclicos vs Defensivos","XLY","XLP"),("Small vs Large","IWM","SPY"),("High Beta vs Low Vol","SPHB","SPLV"),("Nasdaq vs S&P","QQQ","SPY")]
 def series(sym):
  r=chart(sym)
  if not r:return None
  q=[float(x) for x in r.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None]
  if len(q)<22:return None
  y=yahoo_ytd(sym) or {}
  return {"last":q[-1],"d1":(q[-1]/q[-2]-1)*100,"w1":(q[-1]/q[-6]-1)*100,"m1":(q[-1]/q[-22]-1)*100,"ytd":y.get("changeYtd"),"p1":q[-1]-q[-2],"pw":q[-1]-q[-6],"pm":q[-1]-q[-22]}
 def rel(a,b,key):
  x=series(a);y=series(b)
  if not x or not y:return None
  return x[key]-y[key]
 sectors=[]
 for name,sym in sector_cfg:
  x=series(sym)
  if x:sectors.append({"name":name,"symbol":sym,"last":x["last"],"change1d":x["d1"],"change1w":x["w1"],"change1m":x["m1"],"changeYtd":x.get("ytd"),"pointChange1d":x["p1"],"pointChange1w":x["pw"],"pointChange1m":x["pm"],"vsSpy1d":rel(sym,"SPY","d1"),"vsSpy1w":rel(sym,"SPY","w1"),"vsSpy1m":rel(sym,"SPY","m1")})
 styles=[]
 for name,a1,b1 in style_cfg:
  a=series(a1);b=series(b1);styles.append({"name":name,"long":a1,"short":b1,"change1d":rel(a1,b1,"d1"),"change1w":rel(a1,b1,"w1"),"change1m":rel(a1,b1,"m1"),"changeYtd":(a.get("ytd")-b.get("ytd")) if a and b and a.get("ytd") is not None and b.get("ytd") is not None else None})
 up=sum(x["change1w"]>0 for x in sectors);down=sum(x["change1w"]<0 for x in sectors);neutral=len(sectors)-up-down
 sentiment={"bullishPct":round(up*100/len(sectors),1) if sectors else 0,"neutralPct":round(neutral*100/len(sectors),1) if sectors else 0,"bearishPct":round(down*100/len(sectors),1) if sectors else 0}
 feed["rotation"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"sectors":sectors,"styles":styles,"sentimentTraditional":sentiment,"method":"ETF sectorial: precio actual + cambios 1D/1S/1M/YTD + fuerza relativa frente a SPY."}

def update_global_markets(feed):
 regions={
  "ASIA":[("Hong Kong · Hang Seng","^HSI"),("Japón · Nikkei 225","^N225"),("Corea del Sur · KOSPI","^KS11"),("China continental · Shanghai Composite","000001.SS"),("Taiwán · TAIEX","^TWII")],
  "EUROPA":[("STOXX Europe 600","^STOXX"),("Alemania · DAX","^GDAXI"),("Reino Unido · FTSE 100","^FTSE"),("Francia · CAC 40","^FCHI"),("España · IBEX 35","^IBEX")]
 }
 out={}
 for region,items in regions.items():
  arr=[]
  for name,sym in items:
   r=chart(sym);y=yahoo_ytd(sym) or {}
   q=[float(x) for x in (r or {}).get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None] if r else []
   if len(q)<22:continue
   arr.append({"name":name,"symbol":sym,"last":q[-1],"change1d":(q[-1]/q[-2]-1)*100,"change1w":(q[-1]/q[-6]-1)*100,"change1m":(q[-1]/q[-22]-1)*100,"changeYtd":y.get("changeYtd"),"ytdStart":y.get("ytdStart"),"source":"Yahoo Finance public market data"})
  out[region]=arr
 feed["globalMarkets"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"regions":out,"source":"Yahoo Finance public market data","method":"Índices de referencia por región. Variaciones 1D/1S/1M/YTD; YTD se calcula desde el primer cierre disponible del año natural."}


def _cmc_day(timestamp):
 if timestamp is None:return None
 try:
  # CMC can return Unix seconds/milliseconds or an ISO timestamp.
  if isinstance(timestamp,(int,float)) or re.fullmatch(r"\d+(?:\.\d+)?",str(timestamp).strip()):
   raw=float(timestamp)
   if raw>10_000_000_000:raw/=1000.0
   return datetime.fromtimestamp(raw,tz=timezone.utc).strftime("%Y-%m-%d")
  return datetime.fromisoformat(str(timestamp).replace("Z","+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%d")
 except (TypeError,ValueError,OverflowError):return None

def update_crypto_sentiment(feed):
 previous=feed.get("cryptoSentiment",{}) if isinstance(feed.get("cryptoSentiment"),dict) else {}
 fg=[]; cmc_ok=False
 try:
  fg=get("https://pro-api.coinmarketcap.com/public-api/v3/fear-and-greed/historical",{"start":"1","limit":"120","convert":"USD"}).json().get("data",[])
  if isinstance(fg,dict):fg=fg.get("data") or []
  fg=fg if isinstance(fg,list) else []
  cmc_ok=bool(fg)
 except Exception as e:print("CMC CRYPTO FNG",type(e).__name__,str(e)[:180])
 prior_fg=previous.get("fearGreed",{}) if isinstance(previous.get("fearGreed"),dict) else {}
 fg_now=fg[0] if fg else {}
 fg_prev=fg[1] if len(fg)>1 else {}
 fng_by_date={};hist_fng=[]
 for item in fg:
  day=_cmc_day(item.get("timestamp"))
  val=num(item.get("value"))
  if day is None or val is None:continue
  fng_by_date[day]=val
  hist_fng.append({"date":day,"value":val,"classification":item.get("value_classification")})
 if not hist_fng:
  hist_fng=list(prior_fg.get("history") or [])
  fng_by_date={x.get("date"):num(x.get("value")) for x in hist_fng if x.get("date") and num(x.get("value")) is not None}
 # Normaliza el histórico a orden cronológico. Algunos feeds devuelven los días más recientes primero.
 hist_fng=sorted(hist_fng,key=lambda x:str(x.get("date") or ""))
 fng_by_date={x.get("date"):num(x.get("value")) for x in hist_fng if x.get("date") and num(x.get("value")) is not None}
 # El proveedor actual puede traer el valor de hoy aunque aún no aparezca en su histórico.
 today_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d")
 if fg_now.get("value") is not None:
  current_value=num(fg_now.get("value"))
  if current_value is not None:
   fng_by_date[today_utc]=current_value
   if not any(x.get("date")==today_utc for x in hist_fng):
    hist_fng.append({"date":today_utc,"value":current_value,"classification":fg_now.get("value_classification")})
    hist_fng=sorted(hist_fng,key=lambda x:str(x.get("date") or ""))
 btc=chart("BTC-USD");eth=chart("ETH-USD")
 def ret(r):
  q=[float(x) for x in r.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None] if r else []
  if len(q)<22:return None
  return {"change1d":(q[-1]/q[-2]-1)*100,"change1w":(q[-1]/q[-6]-1)*100,"change1m":(q[-1]/q[-22]-1)*100,"last":q[-1]}
 btc_history=[]
 try:
  stamps=btc.get("timestamp",[]) if btc else []
  q=btc.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if btc else []
  for stamp,val in list(zip(stamps,q))[-120:]:
   if val is None:continue
   day=datetime.fromtimestamp(float(stamp),tz=timezone.utc).strftime("%Y-%m-%d")
   fg_value=fng_by_date.get(day)
   # El índice se publica una vez al día. Si el proveedor ya tiene el valor de hoy,
   # úsalo también para el último punto aunque la serie histórica aún no lo haya incluido.
   today_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d")
   if fg_value is None and day==today_utc and fg_now.get("value") is not None:
    fg_value=num(fg_now.get("value"))
   btc_history.append({"date":day,"price":float(val),"fearGreed":fg_value})
 except Exception as e:print("CRYPTO BTC HISTORY",type(e).__name__,str(e)[:120])
 if not btc_history:btc_history=list(previous.get("btcHistory") or [])
 feed["cryptoSentiment"]={
  "updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
  "fearGreed":{"value":num(fg_now.get("value")) if cmc_ok else prior_fg.get("value"),"classification":fg_now.get("value_classification") if cmc_ok else prior_fg.get("classification"),"previous":num(fg_prev.get("value")) if cmc_ok else prior_fg.get("previous"),"history":hist_fng[-120:]},
  "btc":ret(btc) or previous.get("btc"),"eth":ret(eth) or previous.get("eth"),"btcHistory":btc_history,
  "source":"CoinMarketCap Fear & Greed + Yahoo Finance","sourceUrl":"https://coinmarketcap.com/charts/",
  "sourceStatus":"REAL / DAILY" if cmc_ok else "UNAVAILABLE · last valid CMC snapshot retained",
  "dataStatus":"REAL / DAILY · CMC Fear & Greed is published at 00:00 UTC; BTC series from public market chart data."
}

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
 for name,fn in (("FX",update_fx),("COT",update_cot),("OPTIONS",update_options),("DARK_POOLS",update_dark_pools),("DARK_PRINTS",update_dark_pool_prints),("DARK_FLOW",update_dark_flow_radar),("SQUAWKFLOW",update_squawkflow),("ROTATION",update_markets_rotation),("GLOBAL_MARKETS",update_global_markets),("CRYPTO",update_crypto_sentiment),("BONDS",update_bond_market),("BOND_CURVES",update_bond_curves),("SENTIMENT",update_traditional_sentiment),("OPTION_STATS",update_options_market_stats),("TRAD_FG",update_traditional_fear_greed)):
  try:
   fn(feed)
  except Exception as e:
   print(name,type(e).__name__,str(e)[:180])
def update_risk(feed):
 data=[]
 for n,sym in YAHOO.items():
  r=chart(sym)
  q=[float(x) for x in (r or {}).get("indicators",{}).get("quote",[{}])[0].get("close",[]) if x is not None] if r else []
  if len(q)<22:continue
  last=q[-1]
  data.append({"name":n,"symbol":sym,"value":last,
   "change1d":(last/q[-2]-1)*100,"change1w":(last/q[-6]-1)*100,"change1m":(last/q[-22]-1)*100,
   "pointChange1d":last-q[-2],"pointChange1w":last-q[-6],"pointChange1m":last-q[-22],
   "role":ROLES.get(n,"Confirmación")})
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
 pos=sum(p>.4 for p,_,_ in comp);neg=sum(p<-.4 for p,_,_ in comp)
 conf=round(max(35,min(90,55+min(20,abs(pos-neg)*3)-(10 if pos and neg and abs(pos-neg)<=1 else 0))))
 why={"SP500":"la bolsa amplia acompaña el apetito por riesgo","NASDAQ":"la beta alta acompaña el régimen","VIX":"la volatilidad bursátil está contenida","VVIX":"la volatilidad de la volatilidad no muestra estrés","SKEW":"el riesgo de cola no muestra tensión extrema","MOVE":"la volatilidad de bonos no muestra estrés significativo","HYG":"el crédito high yield acompaña el régimen","LQD":"el crédito investment grade acompaña el régimen","DXY":"el dólar actúa como refugio/liquidez","AUDJPY":"el carry confirma apetito por riesgo","COPPER":"el cobre acompaña la demanda cíclica","GOLD":"el oro muestra demanda defensiva","BTC":"cripto acompaña liquidez/beta","ETH":"cripto acompaña liquidez/beta","TLT/SPY":"la duración frente a acciones aporta contexto","OIL":"el petróleo aporta contexto de inflación/crecimiento"}
 positives=sorted([x for x in comp if x[0]>0],reverse=True)[:5];negatives=sorted([x for x in comp if x[0]<0])[:5]
 feed["riskOnOff"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"score":round(score,1),"label":label,"confidence":conf,
  "method":"Composite intermercado. 1D/1S/1M = retorno del último cierre disponible; pointChange = cambio absoluto en unidades del propio activo.",
  "assets":data,"confirmations":[f"{n}: {why.get(n,w)}." for _,n,w in positives],"tensions":[f"{n}: {why.get(n,w)}." for _,n,w in negatives],
  "coverage":{"totalAssets":len(data),"windows":["1D","1S","1M"],"symbols":[x["symbol"] for x in data]}}


