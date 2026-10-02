from pathlib import Path
import re

p = Path("index.html")
html = p.read_text(encoding="utf-8")

# COT: there must be exactly one COT renderer. Remove any injected override
# between the COT professional marker and the Dark Pools renderer.
marker = "/* PROFESSIONAL INTERACTIVE CHARTS · COT + DARK POOLS */"
dp = "const __renderDarkPoolLegacy=renderDarkPoolSection;"
if marker in html and dp in html:
    a = html.find(marker)
    b = html.find(dp, a)
    if b > a:
        segment = html[a:b]
        segment = re.sub(r"renderCotSection=function\(\)\{[\\s\\S]*?\n\};\n?", "", segment)
        html = html[:a] + segment + html[b:]

# Options: explicit BTC/ETH selection must remain on that asset. For non-crypto
# assets we retain the old fallback-to-first-valid-chain behaviour.
opt_start = html.find("renderOptionsSection=function(){")
opt_end = html.find("\n};\n\n" + marker, opt_start)
if opt_start < 0 or opt_end < 0:
    raise SystemExit("ABORT: options renderer boundaries not found")

options = r"""renderOptionsSection=function(){
 const o=macroDatabase.__options||{},markets=o.markets||[];
 let selected=window.__optTicker||(markets[0]?.ticker||'SPY');
 selected=String(selected).toUpperCase();
 const explicitCrypto=(selected==='BTC'||selected==='ETH');
 let m=markets.find(x=>String(x.ticker||x.instrumentCode||'').toUpperCase()===selected)||null;
 if(!m && explicitCrypto){
  m=markets.find(x=>{
   const k=String(x.ticker||x.instrumentCode||'').toUpperCase();
   return k.startsWith(selected+'-')||k.startsWith(selected+'/');
  })||null;
 }
 if(!explicitCrypto && (!m||m.referenceOnly||!Array.isArray(m.profiles)||!m.profiles.length||!Array.isArray(m.profiles[0].topGexStrikes)||!m.profiles[0].topGexStrikes.length)){
  const first=__optionsChainMarket(markets);
  if(first){selected=first.ticker||first.instrumentCode;window.__optTicker=selected;m=first;}
 }
 if(!m)m={ticker:selected,instrumentCode:selected,profiles:[],dataStatus:'SIN CADENA PARA '+selected};
 const p=(m.profiles||[])[0]||{};
 const chart=__optionsInteractiveHtml(m,p);
 const html=__renderOptionsLegacy();
 if(!chart)return html;
 const marker='<div class="metric rounded-xl p-4"><b class="text-sm text-white">METODOLOGÍA</b>';
 const out=html.replace(marker,chart+marker);
 if(Array.isArray(p.topGexStrikes)&&p.topGexStrikes.length)setTimeout(()=>__drawOptionsCharts(m,p),80);
 return out;
};"""
html = html[:opt_start] + options + html[opt_end+3:]

p.write_text(html, encoding="utf-8")
print("UI fixes applied")
