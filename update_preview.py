"""Isolated Claude V7 feed. Never writes index.html or macro-feed.json."""
import argparse
import copy
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

import market_features as mf
import update_feed as legacy
import v7_curves

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'macro-feed-v7.json'
NOW = lambda: datetime.now(timezone.utc)


def dated_rows(rows, key='date'):
    """Idempotent ISO-day windows; revised observations replace the same day."""
    out = {}
    for r in rows:
        day = str(r.get(key, ''))[:10]
        try:
            datetime.strptime(day, '%Y-%m-%d')
        except ValueError:
            continue
        if day <= NOW().date().isoformat():
            out[day] = r
    return [out[k] for k in sorted(out)]


def treasury(feed):
    url = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView'
    labels = {'3 Mo':'3M','1 Yr':'1Y','2 Yr':'2Y','5 Yr':'5Y','10 Yr':'10Y','20 Yr':'20Y','30 Yr':'30Y'}
    records = []
    # Annual table supplies the genuine session history, including prior-year YTD base.
    for year in (NOW().year - 1, NOW().year):
        soup = legacy.BeautifulSoup(legacy.get(url, {'type':'daily_treasury_yield_curve', 'field_tdr_date_value':year}).text, 'html.parser')
        for table in soup.find_all('table'):
            rows = [[c.get_text(' ', strip=True) for c in tr.find_all(['th','td'])] for tr in table.find_all('tr')]
            if not rows or '2 Yr' not in rows[0]:
                continue
            header = rows[0]
            for cells in rows[1:]:
                try:
                    day = datetime.strptime(cells[0], '%m/%d/%Y').date().isoformat()
                except (ValueError, IndexError):
                    continue
                values = {labels[h]:legacy.num(cells[i]) for i,h in enumerate(header) if h in labels and i < len(cells)}
                records.append({'date':day, 'values':values})
    records = dated_rows(records)
    if not records:
        raise ValueError('Treasury returned no dated yield rows')
    latest = records[-1]
    bonds = feed['economies']['us'].setdefault('bonds', {})
    bonds['history'] = records[-520:]
    tenors = []
    for term in labels.values():
        series = [(r['date'], r['values'].get(term)) for r in records if r['values'].get(term) is not None]
        if not series:
            continue
        day, value = series[-1]
        prev_year = [v for d,v in series if d[:4] == str(NOW().year-1)]
        item = {'term':term,'yield':f'{value:.3f}%', 'isKey':term in ('2Y','10Y'),
                'observedAt':day, 'publishedAt':None, 'fetchedAt':NOW().isoformat(),
                'source':'U.S. Treasury', 'sourceUrl':url, 'unit':'percent',
                'status':'observed', 'methodology':'Official constant maturity par yield; not an individual bond'}
        for n, name in ((1,'change1dBp'),(5,'change5sBp'),(21,'change21sBp')):
            item[name] = round((value-series[-n-1][1])*100, 2) if len(series)>n else None
        item['changeYtdBp'] = round((value-prev_year[-1])*100, 2) if prev_year else None
        tenors.append(item)
    bonds.update(tenors=tenors, date=latest['date'], source='U.S. Treasury', sourceUrl=url)


def etf_flows(feed):
    dest = feed.setdefault('cryptoSentiment', {}).setdefault('spotEtfFlows', {})
    errors = []
    for symbol in ('BTC','ETH'):
        data = mf._crypto_spot_etf_flows(symbol)
        if not data:
            errors.append(symbol)
            continue
        history = dated_rows((dest.get(symbol) or {}).get('history', []) + data.get('history', []))
        # Today's all-zero placeholders are not a completed session flow.
        history = [r for r in history if r['date'] < NOW().date().isoformat()]
        data['history'] = history[-260:]
        if history:
            data.update(asOf=history[-1]['date'], observedAt=history[-1]['date'], publishedAt=None,
                        fetchedAt=NOW().isoformat(), status='delayed', netFlow1d=history[-1]['netFlowUsdM'])
            for n in (5,21):
                data[f'netFlow{n}d'] = round(sum(r['netFlowUsdM'] for r in history[-n:]),2) if len(history)>=n else None
            dest[symbol] = data
    if errors:
        feed.setdefault('sourceWarnings', {})['ETF'] = 'Retained previous data: '+', '.join(errors)
    if not dest:
        raise ValueError('Neither ETF source returned usable data')


def dark_ohlc(feed):
    from v7_dark import update
    update(feed, mf.get)


def finalize(feed):
    """Archive real snapshots once per observation day and expiry, never backfill."""
    from v7_economy_state import synchronize
    synchronize(feed,NOW().date().isoformat())
    for economy in feed.get('economies',{}).values():
        latest=(economy.get('conference',{}).get('history') or [{}])[0]
        if latest.get('manuallyVerifiedAt') and latest.get('newRate') is not None:
            economy.setdefault('rates',{}).update(official=latest.get('officialRateLabel') or f"{latest['newRate']:.2f}%",
                officialObservedAt=latest['date'], officialSourceUrl=latest['sourceUrl'])
        bonds=economy.get('bonds',{})
        if bonds.get('history'):
            vals=bonds['history'][-1]['values']
            spread=(vals['10Y']-vals['2Y'])*100 if '10Y' in vals and '2Y' in vals else None
            bonds['shape']=f'10Y − 2Y: {spread:+.1f} pb' if spread is not None else 'Curva por vencimientos'
            bonds['shapeDesc']=bonds.get('methodology') or 'Rendimientos oficiales publicados; las diferencias se expresan en puntos básicos.'
            bonds['spreads'] = [
                {'label': f'{long} − {short}', 'value': f'{(vals[long]-vals[short])*100:+.1f} pb',
                 'desc': bonds['history'][-1]['date']}
                for long, short in [('10Y','2Y'), ('10Y','3M'), ('30Y','10Y')]
                if vals.get(long) is not None and vals.get(short) is not None
            ]
    options = feed.get('options',{})
    archive = options.setdefault('dailySnapshots',{})
    for market in options.get('markets',[]):
        if market.get('referenceOnly') or str(market.get('dataStatus','')).startswith('UNAVAILABLE'):
            continue
        ticker = market.get('ticker')
        for profile in market.get('profiles',[]):
            if ticker == 'VIX':
                for key in ('gammaFlip','zeroGamma'):
                    profile[key] = None
                profile['gammaFlipStatus'] = 'VIX requires a forward model; equity spot model not used'
                for key in ('gammaFlipModel','gammaFlipSensitivity','gammaFlipRoots','gammaFlipCoveragePct'):
                    profile.pop(key, None)
            key = ticker+':'+str(profile.get('expiration'))
            stamp = str(market.get('asOf') or '')[:10]
            row = {'date':stamp, 'expiration':profile.get('expiration'), 'source':market.get('source'),
                   **{k:profile.get(k) for k in ('callOi','putOi','callVolume','putVolume','gammaNet','gammaFlip','callWallOi','putWallOi','maxPain')}}
            archive[key] = dated_rows(archive.get(key,[])+[row])[-90:]
    feed['weeklyFxSchema'] = {'version':1,'status':'awaiting_user_examples','fields':[
        'previousWeekBias','eventsAndSurprises','nextWeekExpectations','verifiedRatePricing',
        'hypothesis','catalysts','invalidation','observedPriceReaction'], 'automaticTrading':False}


def bank_due(eid, checked_at, now=None):
    now = now or NOW()
    try:
        age = now - datetime.fromisoformat(checked_at)
    except (TypeError, ValueError):
        return True
    if age < timedelta(0):
        return True
    nearby = any(e['economyId']==eid and -timedelta(hours=3) <= now-datetime.fromisoformat(e['date'].replace('Z','+00:00')) <= timedelta(days=2) for e in legacy.CENTRAL_BANK_EVENTS)
    return age >= timedelta(hours=2 if nearby else 24)


def meetings(feed, force=False):
    bootstrap = json.loads((ROOT/'v7-meeting-bootstrap.json').read_text(encoding='utf-8'))
    for eid,cfg in legacy.CENTRAL_BANK_PUBLICATIONS.items():
        conference = feed['economies'][eid].setdefault('conference', {})
        if not force and not bank_due(eid, conference.get('lastOfficialCheck')):
            continue
        archive = list(conference.get('meetingArchive', []))
        previous_press_links = {row['date']: row['pressConferenceUrl'] for row in archive if row.get('date') and row.get('pressConferenceUrl')}
        for seed in bootstrap['meetings'].get(eid, []):
            archive.append(dict(seed, id=eid+':'+seed['date'], meetingDate=seed['date'],
                source=cfg['bank'], verified=True, status='observed', publishedAt=seed['date'],
                fetchedAt=None, manuallyVerifiedAt=bootstrap['checkedAt'], publicationType='decision',
                retrievalMethod='official-document-bootstrap'))
        try:
            items = []
            press_conferences = {}
            try:
                tree = ET.fromstring(legacy.get(cfg['feed']).text)
                for node in tree.iter():
                    if node.tag.split('}')[-1] not in ('item','entry'):
                        continue
                    fields = {c.tag.split('}')[-1]:c for c in node}
                    def value(*names):
                        for name in names:
                            if name in fields:
                                return ''.join(fields[name].itertext()).strip()
                        return ''
                    link = fields.get('link')
                    items.append({'title':value('title'), 'link':link.get('href') or value('link') if link is not None else '',
                                  'published':value('pubDate','published','updated')})
            except Exception:
                pass
            if eid != 'us':
                from v7_meetings import discover
                try:
                    items.extend(discover(eid))
                    conference.pop('archiveError',None)
                except Exception as exc:conference['archiveError']=str(exc)[:180]
            if eid == 'us':
                from v7_meetings import fed_press_conferences
                try:
                    press_conferences = fed_press_conferences()
                except Exception as exc:
                    conference['pressConferenceError'] = str(exc)[:180]
                else:
                    conference.pop('pressConferenceError', None)
                url = f'https://www.federalreserve.gov/newsevents/pressreleases/{NOW().year}-press-fomc.htm'
                soup = legacy.BeautifulSoup(legacy.get(url).text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    import re
                    match = re.search(r'monetary(\d{8})a.htm', a['href'])
                    if match and 'FOMC statement' in a.get_text():
                        day = datetime.strptime(match[1], '%Y%m%d').replace(tzinfo=timezone.utc)
                        items.append({'title':a.get_text(' ',strip=True),'link':urljoin(url,a['href']), 'published':day.isoformat()})
            usable_publication = False
            for item in items:
                import re
                title = item.get('title','')
                when = legacy._publication_date(item)
                # Minutes, speeches, implementation notes and reports are documents, not extra meetings.
                if not when or when > NOW() or (not item.get('officialArchive') and not re.search(cfg['match'], title, re.I)):
                    continue
                if re.search(r'speech|implementation note|report|meeting schedule',title,re.I) or ('minutes' in title.lower() and 'summary' not in title.lower()):
                    continue
                if not item.get('link'):
                    continue
                usable_publication = True
                day = when.date().isoformat()
                prior = next((r for r in reversed(archive) if r.get('date')==day), {})
                record = {'id':eid+':'+day,'meetingDate':day,'date':day,
                    'publishedAt':when.isoformat(),'fetchedAt':NOW().isoformat(),
                    'title':title,'source':cfg['bank'],'sourceUrl':item.get('link'),
                    'decision':None,'previousRate':None,'newRate':None,'vote':None,
                    'tone':'Pendiente de lectura del documento', 'summary':title,
                    'publicationType':'decision','verified':True,'status':'observed',
                    'keyPoints':[], 'interpretation':None}
                for key in ('decision','previousRate','newRate','vote','rateLabel','summary','keyPoints','tone','manuallyVerifiedAt'):
                    if prior.get(key) is not None:record[key]=prior[key]
                archive.append(record)
            archive = dated_rows(archive)
            for row in archive:
                if row['date'] in press_conferences:
                    row['pressConferenceUrl'] = press_conferences[row['date']]
                elif row['date'] in previous_press_links:
                    row['pressConferenceUrl'] = previous_press_links[row['date']]
            conference['meetingArchive'] = archive
            conference['history'] = list(reversed(archive))[:3]
            conference['verificationStatus'] = f'{len(conference["history"])}/3 reuniones con publicación oficial recuperada'
            conference['lastOfficialAttempt'] = NOW().isoformat()
            if usable_publication:
                conference['lastOfficialCheck'] = conference['lastOfficialAttempt']
            else:
                conference['verificationStatus'] += ' · consulta sin publicaciones utilizables'
            if conference['history']:
                conference['date'] = conference['history'][0]['date']
                conference['summary'] = conference['history'][0].get('summary')
                conference['tone'] = conference['history'][0].get('tone') or 'Sin clasificación automática'
        except Exception as exc:
            conference['verificationStatus'] = 'Fuente no recuperada: '+type(exc).__name__
            # Old free-text cards are not silently promoted to verified meetings.
            conference['history'] = list(reversed(dated_rows(archive)))[:3]
    feed['economies']['de']['conference'] = copy.deepcopy(feed['economies']['eu']['conference'])


def curves(feed):
    # The fallback must not replace official dated curves while their jobs are cached.
    preserved = {eid: copy.deepcopy(eco.get('bonds', {}))
                 for eid, eco in feed['economies'].items()
                 if eid == 'us' or eco.get('bonds', {}).get('history')}
    mf.update_bond_curves(feed)
    for eid, bonds in preserved.items():
        feed['economies'][eid]['bonds'] = bonds


def calendar(feed):
    legacy.update_central_bank_calendar(feed)
    for eid, economy in feed.get('economies',{}).items():
        candidates = [e for e in legacy.CENTRAL_BANK_EVENTS if e['economyId']==('eu' if eid=='de' else eid) and datetime.fromisoformat(e['date'].replace('Z','+00:00'))>NOW()]
        economy.setdefault('rates',{})['nextMeeting'] = min((e['date'][:10] for e in candidates), default='Calendario por actualizar')

def release_calendar(feed):
    from v7_calendar import update
    update(feed, mf.get)


JOBS = {
 'TREASURY':(treasury, 6), 'CURVES':(curves, 6), 'CANADA_CURVE':(v7_curves.canada, 24), 'ECB_CURVE':(v7_curves.euro_area, 24),
 'JAPAN_CURVE':(v7_curves.japan, 24),
 'AUSTRALIA_CURVE':(v7_curves.australia, 24),
 'ETF':(etf_flows, 6), 'MEETINGS':(meetings, 2),
 'CALENDAR':(calendar, 24), 'ECONOMIC_CALENDAR':(legacy.update_te, 6), 'RELEASE_CALENDAR':(release_calendar, 6),
 'MACRO':(legacy.update_us, 6), 'FX':(mf.update_fx, 1),
 'OPTIONS':(mf.update_options, 2), 'CRYPTO':(mf.update_crypto_sentiment, 6),
 'COT':(mf.update_cot, 24), 'DARK_PRINTS':(mf.update_dark_pool_prints, 12),
 'GLOBAL':(mf.update_global_markets, 6), 'BREADTH':(mf.update_market_breadth, 6), 'RISK':(legacy.update_risk, 1),
 'BONDS':(mf.update_bond_market, 6), 'SENTIMENT':(mf.update_traditional_sentiment, 24),
 'FEAR':(mf.update_traditional_fear_greed, 6), 'OHLC':(dark_ohlc,12),
}


def run(selected=None, force=False):
    os.environ['MACRO_V7'] = '1'
    feed = json.loads((TARGET if TARGET.exists() else ROOT/'macro-feed.json').read_text(encoding='utf-8'))
    health = feed.setdefault('sourceHealth', {})
    for name in selected or JOBS:
        fn, hours = JOBS[name]
        prior = health.get(name, {})
        if not force and prior.get('checkedAt') and NOW()-datetime.fromisoformat(prior['checkedAt']) < timedelta(hours=hours):
            continue
        old = copy.deepcopy(feed)
        before = json.dumps(feed, sort_keys=True)
        try:
            preserved_flows = copy.deepcopy(feed.get('cryptoSentiment',{}).get('spotEtfFlows',{}))
            if name == 'MEETINGS':fn(feed, force=force)
            else:fn(feed)
            if name == 'CRYPTO' and preserved_flows:
                feed.setdefault('cryptoSentiment',{})['spotEtfFlows'] = preserved_flows
            changed = json.dumps(feed, sort_keys=True) != before
            health[name] = {'checkedAt':NOW().isoformat(), 'intervalHours':hours,
                            'status':'processed' if changed else 'unchanged_or_unavailable',
                            'changed':changed}
        except Exception as exc:
            feed = old
            health = feed.setdefault('sourceHealth', {})
            health[name] = {'checkedAt':NOW().isoformat(),'status':'retained','error':str(exc)[:180], 'intervalHours':hours}
        print(name, health[name]['status'], flush=True)
        feed['sourceHealth'] = health
        finalize(feed)
        feed['version'] = 7
        feed['updated'] = NOW().isoformat()
        feed['generatedAt'] = feed['updated']
        feed['publication'] = {'commit':os.getenv('GITHUB_SHA'), 'runId':os.getenv('GITHUB_RUN_ID'),
                               'note':'Generated snapshot; observation dates remain on each source. Publication requires successful push.'}
        tmp = TARGET.with_suffix('.tmp')
        tmp.write_text(json.dumps(feed, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        tmp.replace(TARGET)
    # Reviewed evidence can change even when every network job is still cached.
    before_review = json.dumps(feed, sort_keys=True)
    finalize(feed)
    if json.dumps(feed, sort_keys=True) != before_review:
        feed['generatedAt'] = feed['updated'] = NOW().isoformat()
        feed['publication'] = {'commit':os.getenv('GITHUB_SHA'),'runId':os.getenv('GITHUB_RUN_ID'),
                               'note':'Reviewed evidence refreshed; observation dates retained.'}
        tmp = TARGET.with_suffix('.tmp')
        tmp.write_text(json.dumps(feed, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
        tmp.replace(TARGET)
    return feed


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--sources', nargs='+', choices=JOBS)
    p.add_argument('--force', action='store_true')
    a = p.parse_args()
    run(a.sources, a.force)
