from pathlib import Path
import re,sys
h=Path("index.html").read_text(encoding="utf-8")
required=[
"function fmtCompactMoney(","function fmtPct(","function fmtNum(","function fxBiasLabel(",
"function fxBiasClass(","function parseRate(","function buildFxComparator(",
"function renderRiskOnOff(","function renderOptionsSection(","function renderDarkPoolSection(",
"function renderRotationSection(","function renderCryptoBondSection(","function renderGlobalMarkets("
]
missing=[x for x in required if x not in h]
if missing:
    print("Missing required dashboard helpers:")
    print("\n".join(missing))
    sys.exit(1)
if "macro-feed.json" not in h:
    print("macro-feed.json loader missing")
    sys.exit(1)
print("Dashboard dependency check: OK")
