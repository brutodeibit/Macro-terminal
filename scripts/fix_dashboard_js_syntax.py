from pathlib import Path
p=Path(__file__).resolve().parents[1]/'index.html'
s=p.read_text(encoding='utf-8')
old="['OFF-EXCHANGE',Number.isFinite(+dpx.offExchangePct)?(+dpx.offExchangePct).toFixed(1)+'%':'No disponible'].map(x=>"
new="['OFF-EXCHANGE',Number.isFinite(+dpx.offExchangePct)?(+dpx.offExchangePct).toFixed(1)+'%':'No disponible']].map(x=>"
if old not in s:
    raise SystemExit('dark-pool card array pattern not found')
p.write_text(s.replace(old,new,1),encoding='utf-8')
print('dark-pool syntax fixed')
