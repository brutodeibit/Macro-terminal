#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]

def rjs(s,name,next_name,repl):
    pat=rf"function {re.escape(name)}\s*\(\)\s*\{{.*?(?=\n\s*function {re.escape(next_name)}\s*\(\))"
    out,n=re.subn(pat,repl.rstrip()+"\n\n",s,count=1,flags=re.S)
    if n!=1: raise RuntimeError(f"{name} replace matches={n}")
    return out

def cot():
    p=ROOT/'index.html';s=p.read_text(encoding='utf-8')
    # Keep the replacement intentionally compact and deterministic.
    repl='''function renderCotSection(){
 const c=macroDatabase.__cot||{updated:'—',markets:[]},ms=c.markets||[],keys=ms.map(m=>m.name).filter(Boolean),sel=(window.__cotMarket&&ms.find(x=>x.name===window.__cotMarket))?window.__cotMarket:(keys[0]||'');window.__cotMarket=sel;
 const m=ms.find(x=>x.name===sel)||ms[0]||{},h=m.history||[],range=Math.min(window.__cotRange||52,h.length||52),v=h.slice(0,range).reverse();
 const n=x=>Number.isFinite(Number(x))?Number(x).toLocaleString('es-ES'):'—',sg=x=>Number.isFinite(Number(x))?(Number(x)>=0?'+':'')+n(x):'—';
 const vals=h.map(x=>Number(x.net)).filter(Number.isFinite),lo=vals.length?Math.min(...vals):0,hi=vals.length?Math.max(...vals):1,sp=Math.max(hi-lo,1),W=1100,H=390,L=80,R=30,T=25,B=65,px=i=>L+i*(W-L-R)/Math.max(v.length-1,1),py=x=>T+(hi-x)*(H-T-B)/sp;
 const y= [0,.2,.4,.6,.8,1].map(t=>{let yy=T+t*(H-T-B),z=hi-t*sp;return '<line x1="'+L+'" x2="'+(W-R)+'" y1="'+yy+'" y2="'+yy+'" stroke="#334155" stroke-dasharray="3 5"/><text x="'+(L-10)+'" y="'+(yy+4)+'" text-anchor="end" fill="#dbe4f0" font-size="11">'+n(z)+'</text>'}).join('');
 const step=Math.max(1,Math.floor(Math.max(v.length-1,1)/7)),xt=v.map((x,i)=>i===0||i===v.length-1||i%step===0?'<text x="'+px(i)+'" y="'+(H-24)+'" text-anchor="middle" fill="#dbe4f0" font-size="10">'+esc(x.date||'')+'</text>':'').join('');
 const pts=v.map((x,i)=>px(i).toFixed(1)+','+py(Number(x.net)).toFixed(1)).join(' '),dots=v.map((x,i)=>'<circle cx="'+px(i).toFixed(1)+'" cy="'+py(Number(x.net))+'" r="5" fill="#facc15" stroke="#0b1220" stroke-width="2"><title>'+esc(x.date||'')+' · Neto '+n(x.net)+' · Largos '+n(x.long)+' · Cortos '+n(x.short)+'</title></circle>').join('');
 const tab=v.slice().reverse().map(x=>'<tr class="border-b border-gray-800"><td class="py-2 px-2 text-xs">'+esc(x.date||'')+'</td><td class="py-2 px-2 text-xs text-right">'+n(x.long)+'</td><td class="py-2 px-2 text-xs text-right">'+n(x.short)+'</td><td class="py-2 px-2 text-xs text-right">'+sg(x.net)+'</td><td class="py-2 px-2 text-xs text-right">'+(Number.isFinite(Number(x.openInterest))?((Number(x.net)/Number(x.openInterest))*100).toFixed(1)+'%':'—')+'</td></tr>').join('');
 const opts=keys.map(k=>'<option value="'+esc(k)+'" '+(k===sel?'selected':'')+'>'+esc(k)+'</option>').join('');
 return '<section id="sec-cot" class="space-y-4"><div class="glass rounded-2xl p-5"><div class="flex flex-col lg:flex-row lg:items-center justify-between gap-3"><div><div class="text-[10px] uppercase tracking-wider text-gray-400">CFTC · POSICIONAMIENTO SEMANAL</div><h2 class="text-xl font-black text-white mt-1">COT · FUTURES</h2><p class="text-sm text-gray-300 mt-1">Cada punto = una observación semanal. Amarillo = neto. Cursor = fecha, largos, cortos y neto.</p></div><div class="flex gap-2"><span class="mini-pill">'+esc(c.updated||'—')+'</span><select onchange="window.__cotMarket=this.value;renderContent()" class="bg-gray-900 border border-gray-600 text-white rounded-lg px-3 py-2">'+opts+'</select></div></div></div><div class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3">'+[['NETO',sg(m.net)],['LARGOS',n(m.long)],['CORTOS',n(m.short)],['Δ 1S',sg(m.change1w??m.netChange)],['Δ 4S',sg(m.change4w)],['% OI',m.netPctOI==null?'—':Number(m.netPctOI).toFixed(1)+'%'],['PERCENTIL 52S',m.percentile52==null?'—':Number(m.percentile52).toFixed(1)+'%'],['Z · 52S',Number.isFinite(Number(m.z52??m.zScore))?Number(m.z52??m.zScore).toFixed(2)+'σ':'—']].map(x=>'<div class="metric p-3"><span class="text-[10px] text-gray-400">'+x[0]+'</span><b class="block text-lg text-white mt-1">'+x[1]+'</b></div>').join('')+'</div><div class="metric rounded-xl p-5"><div class="flex justify-between gap-3"><b class="text-sm text-white">'+esc(m.name||'')+' · NET POSITIONING</b></div><div class="overflow-x-auto">'+(v.length>1?'<svg viewBox="0 0 '+W+' '+H+'" class="w-full min-w-[760px] h-[390px]">'+y+'<polyline points="'+pts+'" fill="none" stroke="#facc15" stroke-width="2.7" stroke-linecap="round"/>'+dots+'</svg>':'<div class="h-[390px] grid place-items-center text-gray-400">Histórico insuficiente.</div>')+'</div></div><div class="metric rounded-xl p-5 overflow-x-auto"><b class="text-sm text-white">HISTÓRICO COT</b><table class="w-full min-w-[700px] mt-3"><thead><tr class="border-b border-gray-700 text-[10px] text-gray-400 uppercase"><th class="text-left py-2">Fecha</th><th class="text-right py-2">Largos</th><th class="text-right py-2">Cortos</th><th class="text-right py-2">Neto</th><th class="text-right py-2">% OI</th></tr></thead><tbody>'+tab+'</tbody></table></div></section>'; }'''
    p.write_text(rjs(s,'renderCotSection','renderOptionsSection',repl),encoding='utf-8')

if __name__=='__main__':
    cot()
    print('COT phase OK')