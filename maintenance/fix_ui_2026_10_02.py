from pathlib import Path
import re

p = Path('index.html')
s = p.read_text(encoding='utf-8')

# 1) COT: the legacy SVG already has one X axis + one Y axis and point tooltips.
# The later Plotly wrapper was creating a second rendering layer and a second
# axis/range UI. Remove that wrapper so COT has exactly one visual layer.
marker = '/* PROFESSIONAL INTERACTIVE CHARTS · COT + DARK POOLS */'
start = s.find(marker)
if start >= 0:
    cot_start = s.find('renderCotSection=function(){', start)
    dp_start = s.find('renderDarkPoolSection=function(){', cot_start)
    if cot_start >= 0 and dp_start >= 0:
        # Keep the dark-pool wrapper, but replace only the COT wrapper.
        s = s[:cot_start] + 'renderCotSection=__renderCotLegacy;\n' + s[dp_start:]

# 2) COT labels: use month/year on the visible axis while keeping exact date,
# longs, shorts and net in the point tooltip. This avoids day/month clutter.
s = s.replace(
    "String(x.date||'').slice(0,10)",
    "(String(x.date||'').match(/(\\d{4})[-/](\\d{2})/)||[]).slice(1).join('/')"
)

# 3) Options: never silently replace an explicitly selected BTC/ETH market with
# the first available chain (which was usually BTC). Other assets may still use
# the automatic fallback on first load.
old = "let selected=window.__optTicker||(markets[0]?.ticker||'SPY');\n let m=markets.find(x=>(x.ticker||x.instrumentCode)===selected)||null;\n if(!m||m.referenceOnly||!Array.isArray(m.profiles)||!m.profiles.length||!Array.isArray(m.profiles[0].topGexStrikes)||!m.profiles[0].topGexStrikes.length){\n  const first=__optionsChainMarket(markets); if(first){selected=first.ticker||first.instrumentCode;window.__optTicker=selected;m=first;}\n }\n if(!m)m=markets.find(x=>(x.ticker||x.instrumentCode)===selected)||{};"
new = "let selected=window.__optTicker||(markets[0]?.ticker||'SPY');\n const explicitCrypto=(selected==='BTC'||selected==='ETH');\n let m=markets.find(x=>(x.ticker||x.instrumentCode)===selected)||null;\n if(!explicitCrypto && (!m||m.referenceOnly||!Array.isArray(m.profiles)||!m.profiles.length||!Array.isArray(m.profiles[0].topGexStrikes)||!m.profiles[0].topGexStrikes.length)){\n  const first=__optionsChainMarket(markets); if(first){selected=first.ticker||first.instrumentCode;window.__optTicker=selected;m=first;}\n }\n if(!m && !explicitCrypto)m=markets.find(x=>(x.ticker||x.instrumentCode)===selected)||{};"
if old not in s:
    raise SystemExit('options selection block not found; aborting without changes')
s = s.replace(old, new, 1)

# 4) If ETH/BTC has no chain, keep its own empty state rather than showing BTC.
s = s.replace(
    "const first=__optionsChainMarket(markets); if(first){selected=first.ticker||first.instrumentCode;window.__optTicker=selected;m=first;}",
    "const first=__optionsChainMarket(markets); if(first){selected=first.ticker||first.instrumentCode;window.__optTicker=selected;m=first;}",
    1,
)

p.write_text(s, encoding='utf-8')
print('UI fixes applied')
