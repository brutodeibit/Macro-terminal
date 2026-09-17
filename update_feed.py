#!/usr/bin/env python3
"""MacroTerminal automatic feed updater.

Free-first design:
- US market curve: U.S. Treasury public daily yield-curve page.
- US labour/inflation series: BLS Public Data API (no key for small requests).
- Optional FRED/BEA connectors when keys are provided.
- Optional Trading Economics connector for consensus/forecast calendar fields.
- Never overwrites a good existing value with an empty/failed response.

The script writes macro-feed.json atomically.
"""
from __future__ import annotations
import csv, io, json, os, re, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
FEED_PATH = ROOT / "macro-feed.json"

UA = "MacroTerminal/1.0 (+personal dashboard; automated updater)"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
TIMEOUT = 25

ECONOMIES = {
    "us": {"te": "united states", "currency": "USD"},
    "eu": {"te": "euro area", "currency": "EUR"},
    "de": {"te": "germany", "currency": "EUR"},
    "uk": {"te": "united kingdom", "currency": "GBP"},
    "ch": {"te": "switzerland", "currency": "CHF"},
    "jp": {"te": "japan", "currency": "JPY"},
    "ca": {"te": "canada", "currency": "CAD"},
    "au": {"te": "australia", "currency": "AUD"},
    "nz": {"te": "new zealand", "currency": "NZD"},
}

# Semantic metadata drives the robust bias engine in the HTML.
# rate_sign: +1 means higher-than-expected is more hawkish; -1 means lower is more hawkish.
INDICATOR_META = {
    "cpi": ("INFLACIÓN", 3, +1),
    "core cpi": ("INFLACIÓN", 3, +1),
    "pce": ("INFLACIÓN", 3, +1),
    "core pce": ("INFLACIÓN", 3, +1),
    "ppi": ("INFLACIÓN", 2, +1),
    "core ppi": ("INFLACIÓN", 2, +1),
    "inflation expectations": ("INFLACIÓN", 2, +1),
    "unemployment": ("EMPLEO", 3, -1),
    "non farm payroll": ("EMPLEO", 3, +1),
    "payroll": ("EMPLEO", 3, +1),
    "wages": ("EMPLEO", 2, +1),
    "average hourly earnings": ("EMPLEO", 2, +1),
    "jobless claims": ("EMPLEO", 2, -1),
    "initial jobless claims": ("EMPLEO", 2, -1),
    "gdp": ("CRECIMIENTO", 3, +1),
    "retail sales": ("CRECIMIENTO", 2, +1),
    "industrial production": ("CRECIMIENTO", 2, +1),
    "ism": ("CRECIMIENTO", 2, +1),
    "pmi": ("CRECIMIENTO", 2, +1),
}

BLS_SERIES = {
    "IPC (Mensual)": ("CUUR0000SA0", "INFLACIÓN", +1, 3, "%"),
    "Core CPI (Mensual)": ("CUUR0000SA0L1E", "INFLACIÓN", +1, 3, "%"),
    "Nóminas no agrícolas (NFP)": ("CES0000000001", "EMPLEO", +1, 3, "K"),
    "Tasa de desempleo": ("LNS14000000", "EMPLEO", -1, 3, "%"),
    "Salarios (AHE)": ("CES0500000003", "EMPLEO", +1, 2, "%"),
}


def get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    r = requests.get(url, params=params or {}, headers={**HEADERS, **(headers or {})}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_text(url: str, params: dict[str, Any] | None = None) -> str:
    r = requests.get(url, params=params or {}, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


YAHOO_SYMBOLS = {
    "SP500":"^GSPC", "NASDAQ":"^IXIC", "VIX":"^VIX", "VVIX":"^VVIX", "SKEW":"^SKEW",
    "GOLD":"GC=F", "COPPER":"HG=F", "BRENT":"BZ=F", "WTI":"CL=F", "DXY":"DX-Y.NYB",
    "AUDJPY":"AUDJPY=X", "BTC":"BTC-USD", "ETH":"ETH-USD", "TLT":"TLT", "SPY":"SPY"
}

RISK_ROLES = {
    "SP500":"Equities / broad risk appetite", "NASDAQ":"Growth / high beta equities", "VIX":"Equity volatility", "VVIX":"Volatility-of-volatility",
    "SKEW":"Tail-risk pricing", "GOLD":"Defensive / real asset", "COPPER":"Cyclical growth proxy", "BRENT":"Energy / inflation shock",
    "WTI":"Energy / inflation shock", "DXY":"Dollar liquidity / stress", "AUDJPY":"Carry / risk appetite", "BTC":"High-beta liquidity proxy",
    "ETH":"High-beta liquidity proxy", "TLT":"Duration / defensive hedge", "SPY":"Equity benchmark"
}

def yahoo_chart(symbol: str, range_: str = '1mo') -> dict[str, Any] | None:
    try:
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/' + requests.utils.quote(symbol, safe='')
        data = get_json(url, {'range':range_, 'interval':'1d', 'events':'history'})
        return data.get('chart',{}).get('result',[{}])[0] or None
    except Exception as e:
        print(f'Yahoo {symbol}: {e}')
        return None

def yahoo_metrics(symbol: str) -> tuple[float,float,float] | None:
    res=yahoo_chart(symbol)
    if not res: return None
    q=res.get('indicators',{}).get('quote',[{}])[0]
    closes=[x for x in (q.get('close') or []) if x is not None]
    if not closes: return None
    last=float(closes[-1])
    prev=float(closes[-2]) if len(closes)>=2 else last
    prev5=float(closes[-6]) if len(closes)>=6 else closes[0]
    c1=(last/prev-1)*100 if prev else 0.0
    c5=(last/prev5-1)*100 if prev5 else 0.0
    return last,c1,c5

def build_risk_on_off(feed: dict[str,Any]) -> None:
    data=[]
    for name,symbol in YAHOO_SYMBOLS.items():
        m=yahoo_metrics(symbol)
        if not m: continue
        value,c1,c5=m
        data.append({'name':name,'symbol':symbol,'value':value,'change1d':c1,'change5d':c5,'role':RISK_ROLES.get(name,'Market confirmation')})
    if not data:
        return
    by={x['name']:x for x in data}
    score=50.0
    components=[]
    def add(label, pts, why):
        nonlocal score
        score += pts
        components.append((abs(pts), label, pts, why))
    # Equity breadth
    for n,w in [('SP500',8),('NASDAQ',8)]:
        if n in by:
            c=by[n]['change5d']; pts=max(-w,min(w,c*w/1.5)); add(n,pts,'5D price trend')
    # Volatility / tail risk levels and changes
    if 'VIX' in by:
        v=by['VIX']['value']; pts=8 if v<15 else 4 if v<20 else -4 if v<25 else -8; add('VIX',pts,'absolute volatility level')
    if 'VVIX' in by:
        v=by['VVIX']['value']; pts=4 if v<90 else 1 if v<105 else -2 if v<115 else -4; add('VVIX',pts,'vol-of-vol level')
    if 'SKEW' in by:
        v=by['SKEW']['value']; pts=3 if v<120 else 1 if v<130 else -2 if v<140 else -4; add('SKEW',pts,'tail-risk pricing')
    # Cross-asset confirmations
    if 'AUDJPY' in by: add('AUDJPY',max(-5,min(5,by['AUDJPY']['change5d']*2.0)),'carry/risk appetite')
    if 'DXY' in by: add('DXY',max(-5,min(5,-by['DXY']['change5d']*2.0)),'dollar direction')
    if 'COPPER' in by: add('COPPER',max(-4,min(4,by['COPPER']['change5d']*1.5)),'cyclical confirmation')
    if 'GOLD' in by: add('GOLD',max(-3,min(3,-by['GOLD']['change5d']*1.2)),'defensive demand')
    if 'BTC' in by: add('BTC',max(-3,min(3,by['BTC']['change5d']*0.8)),'liquidity/high beta')
    if 'ETH' in by: add('ETH',max(-2,min(2,by['ETH']['change5d']*0.8)),'liquidity/high beta')
    # Oil is contextual: strong rise is NOT automatically risk-on because it can be inflation shock.
    if 'BRENT' in by and 'WTI' in by:
        oil=max(by['BRENT']['change5d'],by['WTI']['change5d'])
        if oil>6: add('OIL',-2,'large energy shock / inflation risk')
        elif oil<-6: add('OIL',-1,'weak cyclical demand signal')
    # Duration relative to equities: rising duration demand can be defensive.
    if 'TLT' in by and 'SPY' in by:
        rel=by['TLT']['change5d']-by['SPY']['change5d']
        add('TLT/SPY',max(-3,min(3,-rel*1.5)),'relative duration vs equities')
    score=max(0,min(100,score))
    if score>=65: label='RISK ON'
    elif score<=35: label='RISK OFF'
    else: label='NEUTRAL / MIXTO'
    agreement=sum(1 for _,_,p,_ in components if p>0.4)
    disagreement=sum(1 for _,_,p,_ in components if p<-0.4)
    conf=round(max(35,min(90,55 + min(20,abs(agreement-disagreement)*3) - (10 if agreement and disagreement and abs(agreement-disagreement)<=1 else 0))))
    confirmations=[]; tensions=[]
    positives=sorted([x for x in components if x[2]>0], reverse=True)[:5]
    negatives=sorted([x for x in components if x[2]<0], reverse=True)[:5]
    for _,lab,pts,why in positives: confirmations.append(f'{lab}: {why}.')
    for _,lab,pts,why in negatives: tensions.append(f'{lab}: {why}.')
    stamp=datetime.now(timezone.utc).astimezone().strftime('%d/%m/%Y %H:%M %Z')
    for x in data:
        if x['name'] in ('SP500','NASDAQ','VIX','VVIX','SKEW','AUDJPY','DXY','COPPER','GOLD','BTC','ETH'):
            # Asset-level signal is local, intentionally not same as macro regime.
            x['signal']='risk-on' if x['change5d']>0.8 and x['name'] not in ('VIX','VVIX','SKEW','DXY','GOLD') else 'risk-off' if x['change5d']<-0.8 and x['name'] not in ('VIX','VVIX','SKEW','DXY','GOLD') else 'neutral'
        else: x['signal']='neutral'
        x['signalLabel']={'risk-on':'↑ favorable','risk-off':'↓ stress','neutral':'→ mixed'}[x['signal']]
    feed['riskOnOff']={
        'updated':stamp,'score':round(score,1),'label':label,'confidence':conf,
        'method':'Composite transparent regime: equities, volatility, tail-risk, FX, commodities, duration and crypto. Large oil moves are treated as contextual inflation risk, not automatically as risk-on.',
        'assets':data,'confirmations':confirmations,'tensions':tensions,
        'coverage':feed.get('riskOnOff',{}).get('coverage',{})
    }

def num(x: Any) -> float | None:
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    s = str(x).strip().replace(",", "")
    s = re.sub(r"[^0-9+\-.]", "", s)
    if s in ("", ".", "+", "-"): return None
    try: return float(s)
    except ValueError: return None


def fmt(x: float | None, unit: str = "") -> str:
    if x is None: return ""
    if unit == "K": return f"{x/1000:.0f}K" if abs(x) > 10000 else f"{x:.0f}K"
    if unit == "%": return f"{x:.1f}%"
    return f"{x:.2f}"


def load_feed() -> dict[str, Any]:
    with FEED_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write(obj: dict[str, Any]) -> None:
    tmp = FEED_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(FEED_PATH)


def latest_bls(series_id: str) -> tuple[float, str] | None:
    now = datetime.now(timezone.utc)
    years = [str(now.year), str(now.year - 1)]
    payload = {"seriesid": [series_id], "startyear": years[1], "endyear": years[0]}
    try:
        data = requests.post("https://api.bls.gov/publicAPI/v2/timeseries/data/", json=payload, headers={**HEADERS, "Content-Type": "application/json"}, timeout=TIMEOUT).json()
        rows = data.get("Results", {}).get("series", [{}])[0].get("data", [])
        if not rows: return None
        row = rows[0]
        return float(row["value"]), f"{row.get('year')}-{row.get('periodName','')[:3]}"
    except Exception as e:
        print(f"BLS {series_id}: {e}")
        return None



FRED_SERIES = {
    "PCE subyacente (Anual)": ("PCEPILFE", "INFLACIÓN", +1, 3, "%"),
    "PCE (Índice)": ("PCEPI", "INFLACIÓN", +1, 2, ""),
    "PIB (Trimestral)": ("A191RL1Q225SBEA", "CRECIMIENTO", +1, 3, "%"),
}


def latest_fred(series_id: str, api_key: str) -> tuple[float, str] | None:
    try:
        data = get_json("https://api.stlouisfed.org/fred/series/observations", {
            "series_id": series_id, "api_key": api_key, "file_type": "json",
            "sort_order": "desc", "limit": 3
        })
        rows = data.get("observations", [])
        for row in rows:
            v = num(row.get("value"))
            if v is not None:
                return v, str(row.get("date", ""))
    except Exception as e:
        print(f"FRED {series_id}: {e}")
    return None


def update_us_fred(feed: dict[str, Any]) -> None:
    key = os.getenv("FRED_API_KEY")
    if not key: return
    us = feed.get("economies", {}).get("us", {})
    inds = us.setdefault("indicators", [])
    by_name = {x.get("name"): x for x in inds}
    for name, (sid, cat, sign, imp, unit) in FRED_SERIES.items():
        result = latest_fred(sid, key)
        if not result: continue
        value, date = result
        row = by_name.get(name)
        if row is None:
            row = {"cat":cat,"name":name,"actual":"","est":"","surprise":"","date":"","imp":"★"*imp,"source":"Federal Reserve Bank of St. Louis (FRED)","rateImpact":sign}
            inds.append(row)
        row["actual"] = fmt(value, unit)
        row["date"] = date
        row["source"] = "Federal Reserve Bank of St. Louis (FRED)"
        row["rateImpact"] = sign

def update_us_bls(feed: dict[str, Any]) -> None:
    us = feed.get("economies", {}).get("us", {})
    inds = us.setdefault("indicators", [])
    by_name = {x.get("name"): x for x in inds}
    for name, (sid, cat, sign, imp, unit) in BLS_SERIES.items():
        result = latest_bls(sid)
        if not result: continue
        val, period = result
        row = by_name.get(name)
        if not row:
            row = {"cat": cat, "name": name, "actual": "", "est": "", "surprise": "", "date": period, "imp": "★" * imp, "source": "U.S. Bureau of Labor Statistics", "rateImpact": sign}
            inds.append(row)
        row["actual"] = fmt(val, unit)
        row["date"] = period
        row["source"] = "U.S. Bureau of Labor Statistics"
        row["rateImpact"] = sign


def update_us_treasury(feed: dict[str, Any]) -> None:
    us = feed.get("economies", {}).get("us", {})
    year = datetime.now(timezone.utc).year
    month = datetime.now(timezone.utc).month
    url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView"
    params = {"field_tdr_date_value_month": f"{year}{month:02d}", "type": "daily_treasury_yield_curve"}
    try:
        html = get_text(url, params)
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table: return
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if cells: rows.append(cells)
        if len(rows) < 2: return
        header = rows[0]
        data_rows = [r for r in rows[1:] if len(r) >= len(header)]
        if not data_rows: return
        latest = data_rows[-1]
        mapping = {h.upper().replace(" ", ""): i for i,h in enumerate(header)}
        wanted = {"2 YR": "2Y", "5 YR": "5Y", "10 YR": "10Y", "20 YR": "20Y", "30 YR": "30Y", "3 MO": "3M", "1 YR": "1Y"}
        # Normalize header names.
        def idx(label: str):
            for i,h in enumerate(header):
                if h.strip().upper() == label: return i
            return None
        vals = {}
        for src, dst in wanted.items():
            i = idx(src)
            if i is not None and i < len(latest):
                v = num(latest[i])
                if v is not None: vals[dst] = v
        if not vals: return
        terms = []
        old = {x.get("term"): x for x in us.get("bonds", {}).get("tenors", [])}
        for term in ["3M","1Y","2Y","5Y","10Y","20Y","30Y"]:
            if term in vals:
                terms.append({"term": term, "yield": f"{vals[term]:.3f}%", "change": old.get(term,{}).get("change", ""), "isKey": term in ("2Y","10Y")})
        b = us.setdefault("bonds", {})
        b["tenors"] = terms
        if "2Y" in vals and "10Y" in vals:
            b["spreads"] = [
                {"label":"10Y − 2Y", "desc":"Pendiente 2s10s", "value":f"{vals['10Y']-vals['2Y']:+.2f}%"},
                *[x for x in b.get("spreads", [])[1:] if x.get("label") != "10Y − 2Y"]
            ]
        b["date"] = latest[0]
        b["source"] = "U.S. Department of the Treasury"
    except Exception as e:
        print(f"Treasury: {e}")


def update_te_calendar(feed: dict[str, Any]) -> None:
    key = os.getenv("TE_API_KEY")
    if not key: return
    # c=key:secret or the user's token, stored only in GitHub Actions Secrets.
    now = datetime.now(timezone.utc)
    d1 = (now - timedelta(days=14)).date().isoformat()
    d2 = (now + timedelta(days=21)).date().isoformat()
    for eid, cfg in ECONOMIES.items():
        try:
            url = f"https://api.tradingeconomics.com/calendar/country/{requests.utils.quote(cfg['te'])}/{d1}/{d2}"
            data = get_json(url, {"c": key, "f":"json", "importance": 2, "lang":"es"})
            if not isinstance(data, list): continue
            economy = feed.get("economies", {}).get(eid, {})
            ind = economy.setdefault("indicators", [])
            for ev in data:
                actual = ev.get("Actual")
                forecast = ev.get("Forecast") or ev.get("TEForecast")
                if actual in (None, "", "-", "N/A"): continue
                name = ev.get("Event") or ev.get("Category") or "Evento"
                # Keep only meaningful macro signals for this terminal.
                lname = name.lower()
                keep = any(k in lname for k in ["cpi","inflation","pce","ppi","unemployment","payroll","employment","wage","claims","gdp","retail","industrial production","pmi","ism","interest rate","policy rate","core"])
                if not keep: continue
                meta = None
                for k,v in INDICATOR_META.items():
                    if k in lname: meta=v; break
                cat, imp, sign = meta if meta else (ev.get("Category") or "MACRO", int(ev.get("Importance") or 2), 0)
                row = next((x for x in ind if x.get("name") == name), None)
                if row is None:
                    row = {"cat":cat,"name":name,"actual":"","est":"","surprise":"","date":"","imp":"★"*max(1,imp),"source":ev.get("Source") or "Trading Economics calendar (official source attribution)","rateImpact":sign}
                    ind.append(row)
                row["actual"] = str(actual)
                row["est"] = str(forecast or "")
                row["date"] = str(ev.get("Date") or "")[:16].replace("T"," ")
                row["source"] = ev.get("Source") or row.get("source")
                row["sourceUrl"] = ev.get("SourceURL") or row.get("sourceUrl")
                row["importance"] = int(ev.get("Importance") or imp)
                if forecast not in (None, ""):
                    a,n = num(actual),num(forecast)
                    if a is not None and n is not None:
                        delta=(a-n)*sign
                        row["surprise"] = f"{delta:+.2f}"
        except Exception as e:
            print(f"TE {eid}: {e}")


def refresh_metadata(feed: dict[str, Any], source_notes: list[str]) -> None:
    stamp = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M %Z")
    feed["version"] = 4
    feed["updated"] = stamp
    feed["description"] = "Feed automático de MacroTerminal. Los datos se conservan cuando una fuente falla; el campo source indica el origen del último valor recibido."
    feed["automation"] = {
        "updatedAt": stamp,
        "runner": "GitHub Actions / update_feed.py",
        "intervalMinutes": 15,
        "notes": source_notes,
    }


def main() -> int:
    feed = load_feed()
    notes = ["U.S. Treasury + BLS conectores gratuitos activos cuando sus endpoints responden."]
    if os.getenv("TE_API_KEY"):
        notes.append("Calendario/consenso Trading Economics activo mediante TE_API_KEY; los valores Actual proceden de las fuentes que TE atribuye.")
    else:
        notes.append("TE_API_KEY no configurada: Actual/Anterior desde fuentes oficiales conectadas; Consenso/Forecast queda sin completar donde no existe una fuente pública oficial.")
    update_us_treasury(feed)
    update_us_bls(feed)
    update_us_fred(feed)
    update_te_calendar(feed)
    build_risk_on_off(feed)
    refresh_metadata(feed, notes)
    atomic_write(feed)
    print(f"Feed actualizado: {FEED_PATH}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
