from pathlib import Path

p = Path("index.html")
html = p.read_text(encoding="utf-8")

old = """            const tabs=global?[
              ['sec-resumen','PANEL GLOBAL'],['sec-risk','RISK ON/OFF'],['sec-fx','DIVISAS / CARRY'],
              ['sec-cot','COT'],['sec-options','OPCIONES / GAMMA'],['sec-darkpool','DARK POOLS / OTC'],['sec-rotation','MERCADOS & ROTACIÓN'],['sec-sentiment','SENTIMIENTO / BONOS']
            ]:[
              ['sec-fx-weekly','FOREX RADAR'],['sec-tipos','TIPOS'],['sec-conferencia','RUEDA DE PRENSA'],['sec-bonos','CURVA'],
              ['sec-indicadores','INDICADORES']
            ];"""
new = """            // Three decision horizons keep the terminal actionable before it becomes analytical:
            // Ahora = current regime; Semana = catalysts and confirmation; Profundidad = diagnostics.
            const tabs=global?[
              ['sec-resumen','AHORA · RESUMEN'],['sec-risk','AHORA · RÉGIMEN'],
              ['sec-fx','SEMANA · DIVISAS'],['sec-sentiment','SEMANA · FLUJOS / SENTIMIENTO'],['sec-rotation','SEMANA · ROTACIÓN'],
              ['sec-cot','PROFUNDIDAD · COT'],['sec-options','PROFUNDIDAD · OPCIONES'],['sec-darkpool','PROFUNDIDAD · DARK POOLS']
            ]:[
              ['sec-fx-weekly','AHORA · SESGO FX'],['sec-tipos','SEMANA · TIPOS'],['sec-conferencia','SEMANA · BANCO CENTRAL'],
              ['sec-bonos','PROFUNDIDAD · CURVA'],['sec-indicadores','PROFUNDIDAD · INDICADORES']
            ];"""
if old not in html:
    raise SystemExit("ABORT: expected top-tab block not found; refusing a brittle UI edit")
html = html.replace(old, new, 1)
if "AHORA · RESUMEN" not in html or "SEMANA · DIVISAS" not in html or "PROFUNDIDAD · OPCIONES" not in html:
    raise SystemExit("ABORT: UI horizon markers were not written")
p.write_text(html, encoding="utf-8")
print("UI hierarchy applied: Ahora / Semana / Profundidad")
