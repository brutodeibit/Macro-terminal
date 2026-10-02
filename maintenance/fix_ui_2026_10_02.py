from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')

# COT: keep the original single SVG chart. Remove any later Plotly COT
# override regardless of which previous patch version is present.
marker = '/* PROFESSIONAL INTERACTIVE CHARTS · COT + DARK POOLS */'
dp_marker = 'const __renderDarkPoolLegacy=renderDarkPoolSection;'
if marker in s and dp_marker in s:
    section_start = s.find(marker)
    dp_start = s.find(dp_marker, section_start)
    if dp_start > section_start:
        before = s[:section_start]
        tail = s[dp_start:]
        # Keep Dark Pools and everything after it, but remove any COT override
        # between the professional marker and the Dark Pools legacy declaration.
        s = before + marker + '\n' + tail

# COT labels: show month/year on the axis. Exact date + long/short/net stay in
# the point tooltip, so the chart remains visually clean without losing detail.
s = s.replace(
    "String(x.date||'').slice(0,10)",
    "(String(x.date||'').match(/(\\d{4})[-/](\\d{2})/)||[]).slice(1).join('/')"
)

# Options: an explicitly selected BTC/ETH must never fall back silently to BTC
# (or to the first available chain). If its own chain is unavailable, keep its
# own empty state and tell the UI that data for that selected asset is missing.
old = """let selected=window.__optTicker||(markets[0]?.ticker||'SPY');
 let m=markets.find(x=>(x.ticker||x.instrumentCode)===selected)||null;
 if(!m||m.referenceOnly||!Array.isArray(m.profiles)||!m.profiles.length||!Array.isArray(m.profiles[0].topGexStrikes)||!m.profiles[0].topGexStrikes.length){
  const first=__optionsChainMarket(markets); if(first){selected=first.ticker||first.instrumentCode;window.__optTicker=selected;m=first;}
 }
 if(!m)m=markets.find(x=>(x.ticker||x.instrumentCode)===selected)||{};"""
new = """let selected=window.__optTicker||(markets[0]?.ticker||'SPY');
 const explicitCrypto=(selected==='BTC'||selected==='ETH');
 let m=markets.find(x=>(x.ticker||x.instrumentCode)===selected)||null;
 if(!explicitCrypto && (!m||m.referenceOnly||!Array.isArray(m.profiles)||!m.profiles.length||!Array.isArray(m.profiles[0].topGexStrikes)||!m.profiles[0].topGexStrikes.length)){
  const first=__optionsChainMarket(markets); if(first){selected=first.ticker||first.instrumentCode;window.__optTicker=selected;m=first;}
 }
 if(!m && !explicitCrypto)m=markets.find(x=>(x.ticker||x.instrumentCode)===selected)||{};"""
if old not in s:
    raise SystemExit('options selection block not found; aborting without changes')
s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('UI fixes applied')
