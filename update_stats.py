#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
ROOT=Path(__file__).resolve().parent; OUT=ROOT/"stats-feed.json"; TIMEOUT=15
UA={"User-Agent":"MacroTerminal/1.0"}
ASSETS={"SP500":"^GSPC","NASDAQ":"^IXIC","DOW":"^DJI","DAX":"^GDAXI","GOLD":"GC=F","SILVER":"SI=F","WTI":"CL=F","BRENT":"BZ=F","BTC":"BTC-USD","ETH":"ETH-USD","DXY":"DX-Y.NYB"}
def chart(sym,rg,iv):
 u="https://query1.finance.yahoo.com/v8/finance/chart/"+requests.utils.quote(sym,safe="")
 j=requests.get(u,params={"range":rg,"interval":iv,"events":"history"},headers=UA,timeout=TIMEOUT).json().get("chart",{}).get("result")
 if not j:return []
 j=j[0]; ts=j.get("timestamp") or []; q=(j.get("indicators",{}).get("quote") or [{}])[0]; out=[]
 for i,t in enumerate(ts):
  z={"ts":int(t)}; ok=True
  for k in ("open","high","low","close","volume"):
   a=q.get(k) or []; v=a[i] if i<len(a) else None; z[k]=float(v) if v is not None else None
   if k!="volume" and v is None:ok=False
  if ok:out.append(z)
 return out
def med(x):
 x=[v for v in x if v is not None and math.isfinite(v)]; return statistics.median(x) if x else None
def mean(x):
 x=[v for v in x if v is not None and math.isfinite(v)]; return sum(x)/len(x) if x else None
def ret(a,b): return (a/b-1)*100 if b else None
def stats(r):
 c=[x["close"] for x in r]; rg=[(x["high"]-x["low"])/x["close"]*100 for x in r]; rt=[None]+[ret(c[i],c[i-1]) for i in range(1,len(c))]
 sma=[mean(c[max(0,i-19):i+1]) for i in range(len(c))]; m20=[med(rg[max(0,i-19):i+1]) for i in range(len(c))]
 pb=[];imp=[];exp=[];active=False;start=peak=depth=None
 for i,x in enumerate(r):
  trend=i>=20 and sma[i]>sma[i-5] and x["close"]>sma[i]; counter=trend and i and x["close"]<c[i-1]
  if counter and not active: active=True;start=i;peak=c[i-1];depth=0
  elif active:
   depth=max(depth,(peak-x["close"])/peak*100)
   if x["close"]>=peak or i-start>=10:
    pb.append({"start":r[start]["ts"],"depthPct":round(depth,2),"duration":i-start+1,"recovered":x["close"]>=peak});active=False
  body=abs(x["close"]-x["open"])/max(x["high"]-x["low"],1e-9)
  if i>=20 and rg[i]>1.5*(m20[i] or rg[i]) and body>=.6:imp.append({"ts":x["ts"],"returnPct":round(rt[i],3),"rangePct":round(rg[i],3)})
  if i>=20:
   v=statistics.pstdev([z for z in rt[max(1,i-19):i+1] if z is not None])
   if v and abs(rt[i])>2*v:exp.append({"ts":x["ts"],"returnPct":round(rt[i],3),"vol20":round(v,3)})
 peak=c[0] if c else None; dd=0
 for z in c: peak=max(peak,z);dd=min(dd,(z/peak-1)*100)
 dm={}
 for i,x in enumerate(r): dm.setdefault(str(datetime.fromtimestamp(x["ts"],timezone.utc).day),[]).append(rt[i])
 seas=[]
 for k,v in sorted(dm.items(),key=lambda z:int(z[0])):
  v=[z for z in v if z is not None]; seas.append({"day":int(k),"avgPct":round(mean(v),3),"positivePct":round(sum(z>0 for z in v)/max(1,len(v))*100,1),"n":len(v)})
 return {"observations":len(r),"firstDate":datetime.fromtimestamp(r[0]["ts"],timezone.utc).date().isoformat(),"lastDate":datetime.fromtimestamp(r[-1]["ts"],timezone.utc).date().isoformat(),"last":c[-1],"return1d":rt[-1],"return1w":ret(c[-1],c[-6]) if len(c)>=6 else None,"return1m":ret(c[-1],c[-22]) if len(c)>=22 else None,"maxDrawdownPct":round(dd,2),"avgDailyRangePct":round(mean(rg),3),"pullbackCount":len(pb),"pullbackRecoveryPct":round(sum(x["recovered"] for x in pb)/max(1,len(pb))*100,1),"pullbackMedianDepthPct":round(med([x["depthPct"] for x in pb]) or 0,2),"impulses":imp[-100:],"explosiveDays":exp[-100:],"seasonalityByDayOfMonth":seas}
def liquidity(r):
 ny=ZoneInfo("America/New_York"); b={}
 for x in r:
  d=datetime.fromtimestamp(x["ts"],timezone.utc).astimezone(ny);m=d.hour*60+d.minute
  k="NY_OPEN_09:30-10:00" if 570<=m<600 else "NY_10:00-10:30" if 600<=m<630 else "NY_MIDDAY_11:30-13:00" if 690<=m<780 else "NY_AFTERNOON_13:00-15:00" if 780<=m<900 else "NY_CLOSE_15:00-16:00" if 900<=m<960 else "OUTSIDE_REGULAR_NY"
  b.setdefault(k,[]).append((x["high"]-x["low"])/x["close"]*100)
 return {"status":"PARTIAL_INTRADAY_SAMPLE","sampleDays":len(r),"timezone":"America/New_York","note":"Muestra intradía pública disponible; todavía no es el backtest de 1–3 años.","windows":[{"window":k,"observations":len(v),"avgRangePct":round(mean(v),4),"medianRangePct":round(med(v),4)} for k,v in b.items()]}
def main():
 try:f=json.loads(OUT.read_text())
 except:f={"version":1,"assets":{},"liquidity":{}}
 for n,s in ASSETS.items():
  try:
   r=chart(s,"5y","1d");f["assets"][n]={"symbol":s,"stats":stats(r),"source":"Yahoo Finance chart endpoint","dataStatus":"PUBLIC / DELAYED"}
   try:f["liquidity"][n]=liquidity(chart(s,"60d","5m"))
   except Exception as e:f["liquidity"][n]={"status":"UNAVAILABLE","error":type(e).__name__}
  except Exception as e:f["assets"].setdefault(n,{"symbol":s,"dataStatus":"LAST_VALID_SNAPSHOT","error":type(e).__name__})
 f["updated"]=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC");f["source"]="Yahoo Finance · daily 5Y where available · intraday 60D where available";OUT.write_text(json.dumps(f,ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":main()
