"""Synchronize economy cards from dated evidence, never from old UI prose."""
import copy
import json
from pathlib import Path

def synchronize(feed, today):
    reviewed=json.loads(Path(__file__).with_name('v7-reviewed-meetings.json').read_text(encoding='utf-8'))
    for eid,e in feed.get('economies',{}).items():
        if eid=='de':continue
        c=e.setdefault('conference',{})
        archive={r['date']:r for r in c.get('meetingArchive',c.get('history',[])) if r.get('date')}
        for row in reviewed['meetings'].get(eid,[]):
            if row['date']>today:continue
            archive[row['date']]={**archive.get(row['date'],{}),**row,
                'id':eid+':'+row['date'],'verified':True,'publicationType':'decision',
                'manuallyVerifiedAt':reviewed['checkedAt']}
        history=sorted(archive.values(),key=lambda x:x['date'],reverse=True)
        c['meetingArchive']=list(reversed(history));c['history']=history[:3]
        if history:
            latest=history[0]
            for key in ('date','title','summary','tone','keyPoints'):
                c[key]=copy.deepcopy(latest.get(key,[] if key=='keyPoints' else ''))
            c['toneDescription']=latest.get('interpretation') or 'Interpretación detallada no validada para este documento.'
            c['toneBadge']='badge-neutral'
            if latest.get('manuallyVerifiedAt') and latest.get('newRate') is not None:
                e.setdefault('rates',{}).update(official=latest.get('officialRateLabel') or f"{latest['newRate']:.2f}%",
                    officialObservedAt=latest['date'],officialSourceUrl=latest.get('sourceUrl'))
        future=[r for r in feed.get('economicCalendar',{}).get('events',[]) if r.get('economyId')==eid and str(r.get('date',''))[:10]>=today]
        future.sort(key=lambda r:r['date'])
        c['watchFactors']=[r.get('event','Evento')+' · '+r['date'][:10] for r in future[:4]]
        if not future:c['watchFactors']=['Calendario sin próximos eventos recuperados; cobertura por completar.']
    if 'de' in feed.get('economies',{}) and 'eu' in feed['economies']:
        feed['economies']['de']['conference']=copy.deepcopy(feed['economies']['eu'].get('conference',{}))
