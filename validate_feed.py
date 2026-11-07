"""Reject corrupt snapshots, report independent source gaps without blocking others."""
import json
from pathlib import Path

p=Path('macro-feed.json')
assert p.stat().st_size>1000, 'Suspiciously small feed'
feed=json.loads(p.read_text(encoding='utf-8'))
assert isinstance(feed.get('economies'),dict) and len(feed['economies'])>=8
assert feed.get('updated'), 'Missing generation time'
for name,key in [('options','markets'),('darkPoolPrints','assets'),('cot','markets')]:
    module=feed.get(name) or {}
    assert isinstance(module,dict), name+' invalid type'
    print(name, 'present' if module.get(key) else 'unavailable; independent module')
print('Feed structurally valid; individual source dates determine freshness.')
