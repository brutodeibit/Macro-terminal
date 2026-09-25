from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'market_features.py';s=p.read_text(encoding='utf-8')
helper=r'''def _option_professional_metrics(rows,spot):
 calls=[x for x in rows if x.get('type')=='C'];puts=[x for x in rows if x.get('type')=='P'];total=sum(float(x.get('openInterest') or 0) for x in rows)
 def oi(items,fn): return sum(float(x.get('openInterest') or 0) for x in items if fn(float(x.get('strike') or 0)))
 above=oi(rows,lambda k:k>spot);below=oi(rows,lambda k:k<spot);at=oi(rows,lambda k:abs(k-spot)<=max(spot*.005,.01))
 def near(items):
  v=[x for x in items if x.get('delta') is not None and x.get('iv') is not None and abs(abs(float(x['delta']))-.25)<=.15]
  return min(v,key=lambda x:abs(abs(float(x['delta']))-.25)) if v else None
 c25=near(calls);p25=near(puts);civ=float(c25.get('iv') or 0)*100 if c25 else None;piv=float(p25.get('iv') or 0)*100 if p25 else None
 cw=max(calls,key=lambda x:float(x.get('openInterest') or 0),default=None);pw=max(puts,key=lambda x:float(x.get('openInterest') or 0),default=None)
 return {'oiAboveSpot':above,'oiBelowSpot':below,'oiAtSpot':at,'oiAbovePct':above/total*100 if total else None,'oiBelowPct':below/total*100 if total else None,'oiAtPct':at/total*100 if total else None,'call25dIv':civ,'put25dIv':piv,'skew25d':piv-civ if civ is not None and piv is not None else None,'riskReversal25d':civ-piv if civ is not None and piv is not None else None,'call25dStrike':c25.get('strike') if c25 else None,'put25dStrike':p25.get('strike') if p25 else None,'callWall':cw.get('strike') if cw else None,'putWall':pw.get('strike') if pw else None,'callWallOi':float(cw.get('openInterest') or 0) if cw else None,'putWallOi':float(pw.get('openInterest') or 0) if pw else None,'callWallVolume':float(cw.get('volume') or 0) if cw else None,'putWallVolume':float(pw.get('volume') or 0) if pw else None}
'''
if 'def _option_professional_metrics' not in s:
 s=s.replace('def _option_summary(',helper+'\n\ndef _option_summary(',1)
 marker='  \"topGexStrikes\":sorted(gex_by,key=lambda z:abs(z[\"gex\"]),reverse=True)[:10]'
 s=s.replace(marker,marker+',\n  **_option_professional_metrics(rows,spot)',1)
deri=r'''def _deribit_options(currency):
 try:
  ins=get('https://www.deribit.com/api/v2/public/get_instruments',{'currency':currency,'kind':'option','expired':'false'}).json().get('result',[]);sm=get('https://www.deribit.com/api/v2/public/get_book_summary_by_currency',{'currency':currency,'kind':'option'}).json().get('result',[]);by={x.get('instrument_name'):x for x in sm if isinstance(x,dict)}
  spot=num(get('https://www.deribit.com/api/v2/public/get_index_price',{'index_name':currency.lower()+'_usd'}).json().get('result',{}).get('index_price'))
  if not spot:return None
  today=datetime.now(timezone.utc).date();groups={}
  for i in ins:
   name=i.get('instrument_name');ts=i.get('expiration_timestamp');st=by.get(name)
   if not name or not ts or not st:continue
   d=(datetime.fromtimestamp(ts/1000,tz=timezone.utc).date()-today).days;b='0DTE' if d==0 else 'NEXT' if d<=7 else '7-30D' if d<=30 else '30-90D' if d<=90 else None
   if b and b not in groups:groups[b]=(ts,[])
   if b:groups[b][1].append((i,st))
  profiles=[]
  for b,(ts,pairs) in groups.items():
   rows=[];tt=max((ts/1000-datetime.now(timezone.utc).timestamp())/(365*86400),1/3650)
   for i,st in pairs:
    K=num(i.get('strike'));typ='C' if str(i.get('option_type','')).lower()=='call' else 'P';iv=num(st.get('mark_iv')) or 0;iv=iv/100 if iv>3 else iv
    if K is None:continue
    delta,gamma,vanna,charm=_bs_greeks(spot,K,tt,iv,.04,typ);rows.append({'strike':K,'openInterest':num(st.get('open_interest')) or 0,'volume':num(st.get('volume')) or 0,'iv':iv,'gamma':gamma,'delta':delta,'vanna':vanna,'charm':charm,'type':typ})
   if rows:
    pp=_option_summary(rows,spot,datetime.fromtimestamp(ts/1000,tz=timezone.utc));pp['bucket']=b;profiles.append(pp)
  return {'name':currency+' · Deribit','ticker':currency+'-DERIBIT','spot':spot,'profiles':profiles,'source':'Deribit public API','sourceUrl':'https://www.deribit.com/','instrumentType':'Crypto options','dataStatus':'REAL / PUBLIC API','marketLayer':'PRIMARY CRYPTO OPTIONS'}
 except Exception as e:print('DERIBIT',currency,type(e).__name__,str(e)[:160]);return None
'''
if 'def _deribit_options(currency)' not in s:s=s.replace('def update_options(feed):',deri+'\n\ndef update_options(feed):',1)
start=s.index('def update_options(feed):');end=s.index('\ndef enrich_feed(feed):',start)
block=s[start:end]
block=block.replace('(\"SPY\",\"QQQ\",\"QQQM\",\"TQQQ\",\"DIA\",\"IWM\",\"GLD\",\"IAU\",\"GDX\",\"SLV\",\"USO\",\"BNO\",\"UUP\",\"FXE\",\"AAPL\",\"NVDA\")','(\"SPY\",\"QQQ\",\"DIA\",\"IWM\",\"GLD\",\"IAU\",\"USO\",\"BNO\",\"AAPL\",\"NVDA\",\"HYG\",\"TLT\",\"IBIT\")')
if 'for c in (\"BTC\",\"ETH\"):' not in block:
 pos=block.find(' if not out:')
 block=block[:pos]+' for c in (\"BTC\",\"ETH\"):\n  x=_deribit_options(c)\n  if x:out.append(x)\n'+block[pos:]
s=s[:start]+block+s[end:]
p.write_text(s,encoding='utf-8')
print('OPTIONS BACKEND PHASE OK')