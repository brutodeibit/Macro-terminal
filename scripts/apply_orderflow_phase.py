from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'market_features.py';s=p.read_text(encoding='utf-8')
if 'def update_order_flow(feed):' not in s:
 fn=r'''def _yahoo_quote(symbols):
 try:return get("https://query1.finance.yahoo.com/v7/finance/quote",{"symbols":",".join(symbols)}).json().get("quoteResponse",{}).get("result",[])
 except Exception as e:print("YAHOO_QUOTE",type(e).__name__,str(e)[:120]);return []

def update_order_flow(feed):
 out=[]
 for x in _yahoo_quote(["SPY","QQQ","GLD","USO","AAPL","NVDA","IBIT"]):
  bid=num(x.get("bid"));ask=num(x.get("ask"));bs=num(x.get("bidSize"));az=num(x.get("askSize"));spot=num(x.get("regularMarketPrice") or x.get("postMarketPrice"))
  if bid is not None or ask is not None:
   out.append({"symbol":x.get("symbol"),"display":"Top of book · "+str(x.get("symbol")),"bestBid":bid,"bestAsk":ask,"mid":(bid+ask)/2 if bid is not None and ask is not None else spot,"spread":ask-bid if bid is not None and ask is not None else None,"bidSize":bs,"askSize":az,"bidDepth":bs,"askDepth":az,"imbalance":((bs or 0)-(az or 0))/max((bs or 0)+(az or 0),1)*100,"bids":[],"asks":[],"source":"Yahoo quote · top-of-book","dataStatus":"REAL / DELAYED · no Level 2"})
 for inst in ("BTC-PERPETUAL","ETH-PERPETUAL"):
  try:
   j=get("https://www.deribit.com/api/v2/public/get_order_book",{"instrument_name":inst,"depth":20}).json().get("result",{});b=[{"price":float(z[0]),"size":float(z[1])} for z in j.get("bids",[]) if len(z)>=2];a=[{"price":float(z[0]),"size":float(z[1])} for z in j.get("asks",[]) if len(z)>=2];bd=sum(z["size"] for z in b);ad=sum(z["size"] for z in a)
   out.append({"symbol":inst,"display":inst+" · 20 niveles","bestBid":b[0]["price"] if b else None,"bestAsk":a[0]["price"] if a else None,"mid":j.get("underlying_price"),"spread":a[0]["price"]-b[0]["price"] if b and a else None,"bidSize":b[0]["size"] if b else None,"askSize":a[0]["size"] if a else None,"bidDepth":bd,"askDepth":ad,"imbalance":(bd-ad)/(bd+ad)*100 if bd+ad else None,"bids":b,"asks":a,"source":"Deribit public order book","dataStatus":"REAL / PUBLIC · 20 levels"})
  except Exception as e:print("DERIBIT_BOOK",inst,type(e).__name__,str(e)[:120])
 feed["orderFlow"]={"updated":datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),"markets":out,"source":"Yahoo top-of-book + Deribit public depth","note":"Equities/ETF: top-of-book only; BTC/ETH: Deribit 20-level public depth."}
'''
 s=s.replace("def update_dark_pools(feed):",fn+"\n\ndef update_dark_pools(feed):",1)
p.write_text(s,encoding='utf-8')
print('ORDER FLOW BACKEND PHASE OK')
