"""Public scheduled releases, separate from official central-bank meetings."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re
MAP={'USD':'us','EUR':'eu','GBP':'uk','JPY':'jp','CHF':'ch','AUD':'au','NZD':'nz','CAD':'ca'}

def bls_events(text):
    text=re.sub(r'\r?\n[ \t]','',text)
    out=[]
    for block in text.split('BEGIN:VEVENT')[1:]:
        start=re.search(r'DTSTART([^:]*):([^\r\n]+)',block)
        title=re.search(r'SUMMARY:([^\r\n]+)',block)
        if not start or not title:continue
        raw=start[2]
        try:
            t=datetime.strptime(raw.rstrip('Z'),'%Y%m%dT%H%M%S')
            zone=timezone.utc if raw.endswith('Z') else ZoneInfo('America/New_York')
            t=t.replace(tzinfo=zone).astimezone(timezone.utc)
        except ValueError:continue
        row=parse([{'country':'USD','title':title[1],'date':t.isoformat(),'impact':'High'}],
                  'https://www.bls.gov/schedule/news_release/bls.ics')[0]
        row['source']='BLS · calendario oficial';out.append(row)
    return out

def parse(rows,source):
    out=[]
    for r in rows:
        code=r.get('country');raw=r.get('date','')
        if code not in MAP:continue
        try:
            t=datetime.fromisoformat(raw.replace('Z','+00:00'))
            if t.tzinfo is None:continue
        except (ValueError,TypeError):continue
        date=t.astimezone(timezone.utc).isoformat()
        out.append({'id':code+':'+date+':'+r.get('title',''),'economyId':MAP[code],
            'currency':code,'country':code,'event':r.get('title',''),'date':date,
            'forecast':r.get('forecast',''),'previous':r.get('previous',''),'actual':r.get('actual',''),
            'importance':{'High':3,'Medium':2,'Low':1}.get(r.get('impact'),0),
            'source':'Forex Factory / Fair Economy · calendario de terceros','sourceUrl':source,
            'status':'scheduled','publishedAt':None,'fetchedAt':datetime.now(timezone.utc).isoformat()})
    return out

def update(feed,get):
    calendar=feed.setdefault('economicCalendar',{});old=calendar.get('events',[])
    retained=[x for x in old if not str(x.get('source','')).startswith('Forex Factory')]
    collected=[];errors=[]
    for period in ('thisweek',):
        url='https://nfs.faireconomy.media/ff_calendar_'+period+'.json'
        try:
            rows=get(url).json()
            if not isinstance(rows,list):raise ValueError('Expected event list')
            collected.extend(parse(rows,url))
        except Exception as exc:errors.append(str(exc)[:140])
    try:
        official=bls_events(get('https://www.bls.gov/schedule/news_release/bls.ics').text)
        if not official:raise ValueError('Empty BLS calendar')
        retained=[x for x in retained if x.get('source')!='BLS · calendario oficial']
        collected.extend(official)
    except Exception as exc:errors.append('BLS: '+str(exc)[:120])
    if errors:
        collected.extend(x for x in old if str(x.get('source','')).startswith('Forex Factory') and x.get('id') not in {r['id'] for r in collected})
    combined={x.get('id') or str((x.get('economyId'),x.get('date'),x.get('event'))):x for x in retained+collected}
    calendar.update(events=sorted(combined.values(),key=lambda x:x.get('date','')),
        releaseCalendarStatus='partial' if errors else 'retrieved',releaseCalendarErrors=errors)

