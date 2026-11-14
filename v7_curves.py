"""Official curves: observed benchmarks and explicitly identified official estimates."""
import csv
import io
import re
from datetime import datetime, timezone
import update_feed as api


def parse_japan_csv(text):
    """MOF files contain a title, blank lines and footnotes around the table."""
    header = None
    rows = []
    for cells in csv.reader(io.StringIO(text.replace('\r\r\n', '\n'))):
        if not cells:
            continue
        if cells[0].strip().lstrip('\ufeff') == 'Date':
            header = [c.strip() for c in cells]
            continue
        if not header or not re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}', cells[0].strip()):
            continue
        day = datetime.strptime(cells[0].strip(), '%Y/%m/%d').date().isoformat()
        values = {term: api.num(value) for term, value in zip(header, cells)
                  if term in ('1Y','2Y','5Y','10Y','20Y','30Y')}
        rows.append({'date': day, 'values': values})
    return rows


def japan(feed):
    base = 'https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/'
    rows = list(feed['economies']['jp'].get('bonds', {}).get('history', []))
    # Bootstrap the history only when missing; daily refresh is a small monthly CSV.
    if len(rows) < 252 or rows[-1].get('date', '')[:7] != datetime.now(timezone.utc).strftime('%Y-%m'):
        rows = parse_japan_csv(api.get(base+'historical/jgbcme_all.csv').text)
    rows += parse_japan_csv(api.get(base+'jgbcme.csv').text)
    store_curve(feed, 'jp', rows, 'Japan Ministry of Finance', base+'jgbcme.csv',
                'Official constant-maturity JGB yields based on secondary-market closing prices; semiannual compounding. No synthetic 3M maturity.',
                status='calculated')


def parse_rba_csv(text):
    mapping = {'FCMYGBAG2D':'2Y','FCMYGBAG5D':'5Y','FCMYGBAG10D':'10Y'}
    header, publication, rows = None, None, []
    for cells in csv.reader(io.StringIO(text)):
        if not cells:
            continue
        if cells[0] == 'Publication date':
            publication = datetime.strptime(cells[1], '%d-%b-%Y').date().isoformat()
        if cells[0] == 'Series ID':
            header = cells
            continue
        if not header or not re.fullmatch(r'\d{2}-[A-Za-z]{3}-\d{4}', cells[0]):
            continue
        day = datetime.strptime(cells[0], '%d-%b-%Y').date().isoformat()
        rows.append({'date':day, 'values':{mapping[code]:api.num(value)
                    for code, value in zip(header, cells) if code in mapping}})
    return rows, publication


def australia(feed):
    url = 'https://www.rba.gov.au/statistics/tables/csv/f2-data.csv'
    rows, publication = parse_rba_csv(api.get(url).text)
    store_curve(feed, 'au', rows, 'Reserve Bank of Australia · F2', url,
                'Official interpolated Australian government nominal yields. Excludes inflation-indexed yields; weekly publication of daily observations.',
                status='estimated')
    for tenor in feed['economies']['au']['bonds']['tenors']:
        tenor['publishedAt'] = publication


def store_curve(feed, eid, rows, source, url, methodology, status='observed'):
    now = datetime.now(timezone.utc)
    records = {}
    for row in rows:
        day = row['date']
        if day > now.date().isoformat():continue
        records.setdefault(day, {}).update({k:v for k,v in row['values'].items() if v is not None})
    history = [{'date':d,'values':v} for d,v in sorted(records.items()) if v]
    if not history:raise ValueError(source+': no dated curve observations')
    terms = ['3M','1Y','2Y','5Y','10Y','20Y','30Y','LT']
    tenors = []
    for term in terms:
        series = [(r['date'], r['values'][term]) for r in history if term in r['values']]
        if not series:continue
        day,value = series[-1]
        item = dict(term=term,yield_=value,observedAt=day,publishedAt=None,fetchedAt=now.isoformat(),
                    source=source,sourceUrl=url,status=status,unit='percent',methodology=methodology,
                    isKey=term in ('2Y','10Y'))
        item['yield']=f'{item.pop("yield_"):.3f}%'
        for n,name in ((1,'change1dBp'),(5,'change5sBp'),(21,'change21sBp')):
            item[name]=round((value-series[-1-n][1])*100,2) if len(series)>n else None
        prior=[v for d,v in series if d[:4]==str(now.year-1)]
        item['changeYtdBp']=round((value-prior[-1])*100,2) if prior else None
        tenors.append(item)
    feed['economies'][eid]['bonds'] = dict(tenors=tenors,history=history[-520:],date=history[-1]['date'],
        source=source,sourceUrl=url,methodology=methodology,status=status)


def canada(feed):
    base='https://www.bankofcanada.ca/valet/observations/'
    start=f'{datetime.now(timezone.utc).year-1}-12-01'
    rows=[]
    mapping={'BD.CDN.2YR.DQ.YLD':'2Y','BD.CDN.5YR.DQ.YLD':'5Y','BD.CDN.10YR.DQ.YLD':'10Y','BD.CDN.LONG.DQ.YLD':'LT',
             'V39065':'3M','V39067':'1Y'}
    for path in ('group/bond_yields_all/json','V39065/json','V39067/json'):
        try:data=api.get(base+path,{'start_date':start}).json()
        except Exception as exc:
            feed.setdefault('sourceWarnings',{})['CANADA_'+path]=str(exc)[:150]
            continue
        for row in data.get('observations',[]):
            values={term:api.num(row.get(code,{}).get('v')) for code,term in mapping.items()}
            rows.append({'date':row['d'],'values':values})
    store_curve(feed,'ca',rows,'Bank of Canada',base+'group/bond_yields_all/json',
        '3M/1Y: secondary-market Treasury bills; 2Y/5Y/10Y: benchmark bonds. LT: designated long-term benchmark, not an exact 30Y maturity.')


def euro_area(feed):
    suffixes='SR_3M+SR_1Y+SR_2Y+SR_5Y+SR_10Y+SR_20Y+SR_30Y'
    url='https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.'+suffixes
    response=api.get(url,{'format':'csvdata','startPeriod':f'{datetime.now(timezone.utc).year-1}-12-01'})
    rows=[]
    for row in csv.DictReader(io.StringIO(response.text.lstrip('\ufeff'))):
        term=row.get('KEY','').split('.')[-1].removeprefix('SR_')
        value=api.num(row.get('OBS_VALUE'))
        day=row.get('TIME_PERIOD','')
        if term in ('3M','1Y','2Y','5Y','10Y','20Y','30Y') and value is not None and len(day)==10:
            rows.append({'date':day,'values':{term:value}})
    store_curve(feed,'eu',rows,'ECB · AAA zero-coupon spot curve',url,
        'Official ECB Svensson fitted spot curve for AAA euro-area sovereigns. Estimated maturities, including 20Y; not a German benchmark or an interpolated series produced by this app.',status='estimated')
