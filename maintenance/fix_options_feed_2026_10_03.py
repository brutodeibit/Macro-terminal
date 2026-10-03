from pathlib import Path
import re

p = Path('market_features.py')
s = p.read_text(encoding='utf-8')
start = s.find('def update_options(feed):')
end = s.find('\ndef update_dark_pools(feed):', start)
if start < 0 or end < 0:
    raise SystemExit('ABORT: update_options boundaries not found')

new = r'''def update_options(feed):
 previous=feed.get('options',{}) if isinstance(feed.get('options'),dict) else {}
 old_by={m.get('ticker'):m for m in previous.get('markets',[]) if isinstance(m,dict) and m.get('ticker')}
 chain_targets=('SPX','SPY','NDX','QQQ','RUT','IWM','DIA','GLD','IAU','SLV','USO','BNO','AAPL','NVDA','HYG','TLT','IBIT')
 detailed={}; errors=[]

 # Preferred source when configured; public Yahoo chain is the fallback.
 for sym in chain_targets:
  try:
   x=_massive_option_chain(sym)
   if x:detailed[sym]=x
  except Exception as e:
   errors.append(f'Massive {sym}: {type(e).__name__}')
 for sym in ('SPY','QQQ','DIA','IWM','GLD','IAU','USO','BNO','AAPL','NVDA','HYG','TLT','IBIT'):
  if sym in detailed:continue
  try:
   x=opt(sym)
   if x:detailed[sym]=x
  except Exception as e:
   errors.append(f'Yahoo options {sym}: {type(e).__name__}')

 out=[]
 for entry in OPTION_CATALOG:
  code=entry['code']; x=detailed.get(code)
  if x:
   try:
    stats=_barchart_option_overview(code)
    if stats:
     x['stats']=stats
     p0=(x.get('profiles') or [{}])[0]
     for k in ('ivRank','ivPercentile','iv','putCallVol','putCallOi','expectedMove','expectedMovePct'):
      if stats.get(k) is not None:p0[k]=stats[k]
   except Exception as e: errors.append(f'Barchart {code}: {type(e).__name__}')
   x['family']=entry['family'];x['instrumentCode']=code;x['instrumentKind']=entry['kind'];x['referenceOnly']=False
   x['sourceDate']=x.get('asOf') or datetime.now(timezone.utc).isoformat()
   out.append(x);continue
  if entry.get('eurex'):
   try:
    ex=_eurex_snapshot(entry)
    if ex:
     q=ex.get('underlyingClose')
     out.append({**entry,'ticker':code,'name':entry['label'],'referenceOnly':True,'spot':q,
                 'quote':ex,'stats':ex,'dataStatus':ex.get('dataStatus'),'asOf':ex.get('asOfDate'),
                 'method':'Eurex: último snapshot público disponible. Sin cadena de strikes no se inventan Max Pain/GEX.'})
     continue
   except Exception as e: errors.append(f'Eurex {code}: {type(e).__name__}')
  if entry.get('yahoo'):
   try:
    ref=_option_reference_entry(entry)
    if ref:out.append(ref)
   except Exception as e: errors.append(f'Reference {code}: {type(e).__name__}')

 # SPX model fallback from SquawkFlow/Cboe-derived public OI estimate.
 sf=feed.get('squawkFlow',{}) if isinstance(feed.get('squawkFlow'),dict) else {}
 sx=sf.get('spxGex',{}).get('data') if isinstance(sf.get('spxGex'),dict) else None
 if isinstance(sx,dict) and not any(m.get('ticker')=='SPX' and not m.get('referenceOnly') for m in out):
  spxprof={'expiration':sx.get('asOfDate'),'daysToExpiry':None,'gammaNet':sx.get('netGex'),
           'gammaFlip':sx.get('gexFlipPrice'),'callWall':sx.get('callWall'),'putWall':sx.get('putWall'),
           'callWallOi':sx.get('callWall'),'putWallOi':sx.get('putWall'),'maxGammaStrike':sx.get('maxGammaStrike'),
           'volTrigger':sx.get('volTrigger'),'bucket':'SPX · GEX model','source':'SquawkFlow / Cboe OI-derived estimate',
           'dataStatus':'REAL / DELAYED · OI-derived'}
  spx={'ticker':'SPX','instrumentCode':'SPX','family':'S&P 500','name':'S&P 500 Index · SPX',
       'spot':sx.get('spotPrice'),'profiles':[spxprof],'referenceOnly':False,
       'source':'SquawkFlow · SPX GEX model','sourceUrl':'https://squawkflow.com/docs/endpoints',
       'dataStatus':'REAL / DELAYED · calculated from Cboe open interest',
       'method':'Fallback GEX model from Cboe open interest; used only when a full chain source is unavailable.'}
  out=[m for m in out if m.get('ticker')!='SPX'];out.insert(0,spx)

 # BTC/ETH: Deribit public chain is primary. Never merge BTC and ETH.
 for ccy in ('BTC','ETH'):
  try:
   der=_deribit_options(ccy)
   if der:
    crypto=dict(der);crypto['ticker']=ccy;crypto['instrumentCode']=ccy;crypto['family']='Cripto';crypto['referenceOnly']=False
    crypto['dataStatus']='REAL / DELAYED · Deribit public options'
    crypto['method']='Deribit public options. GEX/Gamma Flip are modeled from public OI/Greeks; CME and ETF layers remain separate.'
    crypto['cryptoPerspective']=True
    crypto['layers']={'deribit':der,'spotEtfFlows':_crypto_spot_etf_flows(ccy)}
    if ccy=='BTC':
     crypto['btcPerspective']=True;crypto['layers']['cme']=_cme_btc_option_layer()
    out=[m for m in out if m.get('ticker')!=ccy];out.append(crypto)
   elif not any(m.get('ticker')==ccy for m in out):
    ref=_option_reference_entry({'family':'Cripto','code':ccy,'label':ccy,'kind':'crypto','yahoo':ccy+'-USD','source':'Yahoo Finance · spot proxy','sourceUrl':'https://finance.yahoo.com/quote/'+ccy+'-USD/'})
    if ref:
     ref['dataStatus']='CHAIN UNAVAILABLE · spot disponible · último dato público retenido'
     ref['method']='No se inventan GEX/Max Pain. La cadena nativa de '+ccy+' procede de Deribit cuando su API pública responde.'
     out.append(ref)
  except Exception as e:
   errors.append(f'Deribit {ccy}: {type(e).__name__}')
   if not any(m.get('ticker')==ccy for m in out):
    old=old_by.get(ccy)
    if old:
     m=dict(old);m['dataStatus']='UNAVAILABLE · último snapshot válido retenido';m['updatedAttempt']=datetime.now(timezone.utc).isoformat();out.append(m)

 # Never let a temporary provider outage make an asset disappear from the selector.
 present={x.get('ticker') for x in out}
 for code,m in old_by.items():
  if code not in present and m.get('profiles'):
   m=dict(m);m['dataStatus']='UNAVAILABLE · último snapshot válido retenido';m['updatedAttempt']=datetime.now(timezone.utc).isoformat();out.append(m);present.add(code)

 flow=feed.get('squawkFlow',{}) if isinstance(feed.get('squawkFlow'),dict) else {}
 flow_data=flow.get('unusualOptions',{}).get('data') if isinstance(flow.get('unusualOptions'),dict) else []
 flow_data=flow_data[:30] if isinstance(flow_data,list) else []
 hist=dict(previous.get('history') or {});stamp=datetime.now(timezone.utc).isoformat()
 for m in out:
  if m.get('referenceOnly'):continue
  p=(m.get('profiles') or [{}])[0];arr=hist.get(m.get('ticker'),[])
  snap={'asOf':stamp,'expiration':m.get('expiration') or p.get('expiration'),'spot':m.get('spot'),
        'gammaNet':p.get('gammaNet'),'gammaFlip':p.get('gammaFlip'),'maxPain':p.get('maxPain'),
        'callWall':p.get('callWallOi') or p.get('callWall'),'putWall':p.get('putWallOi') or p.get('putWall'),
        'ivAtm':p.get('ivAtm'),'expectedMove':p.get('expectedMove'),'riskReversal25d':p.get('riskReversal25d')}
  arr=[h for h in arr if not (h.get('expiration')==snap.get('expiration') and h.get('asOf','')[:10]==stamp[:10])]
  arr.append(snap);hist[m.get('ticker')]=arr[-180:]

 full=sum(1 for m in out if not m.get('referenceOnly') and m.get('profiles'))
 refs=sum(1 for m in out if m.get('referenceOnly'))
 feed['options']={
  'updated':datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC'),
  'markets':out,'history':hist,'flow':flow_data,'optionsStats':feed.get('optionsStats') if isinstance(feed.get('optionsStats'),dict) else {},
  'catalog':OPTION_CATALOG,'providerStatus':{'fullChainMarkets':full,'referenceOnlyMarkets':refs,'totalMarkets':len(out),'errors':errors[-30:]},
  'source':'Massive full-chain snapshots + Cboe + Barchart + Deribit/CME + Yahoo fallback',
  'sourceStatus':'REAL / DELAYED · multi-source',
  'publication':'La cadena completa se usa solo cuando el proveedor la entrega. GEX/Gamma Flip/DEX/Max Pain son cálculos sobre OI/IV/Greeks públicos; Cboe no se presenta como proveedor de GEX propietario.',
  'note':'No se rellenan métricas inexistentes. Reference-only conserva precio y fecha para que el selector nunca desaparezca. BTC y ETH permanecen separados.'
 }
'''

s = s[:start] + new + s[end:]
p.write_text(s, encoding='utf-8')
print('Options feed patch applied')
