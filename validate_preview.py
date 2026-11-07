"""Structural gates, independent of any single external provider's availability."""
import json
from pathlib import Path

feed=json.loads(Path('macro-feed-v7.json').read_text(encoding='utf-8'))
assert feed.get('version')==7
assert isinstance(feed.get('economies'),dict) and len(feed['economies'])>=8
assert feed.get('generatedAt')
for eco in feed['economies'].values():
    h=eco.get('conference',{}).get('history',[])
    if any(x.get('verified') for x in h):
        assert len(h)<=3
        assert len({x['id'] for x in h})==len(h)
        assert [x['date'] for x in h]==sorted([x['date'] for x in h],reverse=True)
for asset,flow in feed.get('cryptoSentiment',{}).get('spotEtfFlows',{}).items():
    dates=[x['date'] for x in flow.get('history',[])]
    assert dates==sorted(set(dates)), asset
    assert all(isinstance(x['netFlowUsdM'],(int,float)) for x in flow.get('history',[]))
for m in feed.get('options',{}).get('markets',[]):
    for p in m.get('profiles',[]):
        if p.get('gammaFlipModel'):
            assert p.get('gammaFlip') is None or p['gammaFlip']>0
print('V7 structural validation passed; source health:',feed.get('sourceHealth',{}))
