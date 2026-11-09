"""Official archive discovery; bounded links, no synthetic meeting cards."""
import re
from datetime import datetime, timezone
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import update_feed as api

ARCHIVES={
 'eu':('https://www.ecb.europa.eu/press/press_conference/monetary-policy-statement/html/index.en.html',r'ecb\.mp\d{6}.*\.en\.html'),
 'uk':('https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes',r'/monetary-policy-summary-and-minutes/2026/'),
 'au':('https://www.rba.gov.au/monetary-policy/int-rate-decisions/2026/',r'/media-releases/2026/mr-26-'),
 'jp':('https://www.boj.or.jp/en/mopo/mpmdeci/state_2026/index.htm',r'k\d{6}a\.pdf'),
 'ch':('https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions',r'pre_2026\d{4}'),
 'ca':('https://www.bankofcanada.ca/press/press-releases/',r'/2026/\d{2}/fad-press-release-'),
 'nz':('https://www.rbnz.govt.nz/monetary-policy/monetary-policy-decisions',r'/2026/.*(ocr|official-cash|monetary-policy)'),
}

def date_from(text):
    for pattern,fmt in [(r'20\d{2}-\d{2}-\d{2}','%Y-%m-%d'),(r'20\d{6}','%Y%m%d'),
                        (r'\d{1,2} [A-Z][a-z]+ 20\d{2}','%d %B %Y')]:
        for match in re.findall(pattern,text):
            try:return datetime.strptime(match,fmt).replace(tzinfo=timezone.utc)
            except ValueError:pass
    match=re.search(r'(?:ecb\.mp|/k)(\d{6})',text)
    if match:
        return datetime.strptime(match[1],'%y%m%d').replace(tzinfo=timezone.utc)
    return None

def fed_press_conferences():
    url = 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'
    soup = BeautifulSoup(api.get(url).text, 'html.parser')
    result = {}
    for link in soup.find_all('a', href=True):
        match = re.fullmatch(r'/monetarypolicy/fomcpresconf(\d{8})\.htm', link['href'])
        if match and (day := date_from(match[1])) and day <= datetime.now(timezone.utc):
            result[day.date().isoformat()] = urljoin(url, link['href'])
    return result


def discover(eid):
    if eid not in ARCHIVES:return []
    url,pattern=ARCHIVES[eid]
    soup=BeautifulSoup(api.get(url).text,'html.parser')
    if eid=='nz':
        records=[]
        for tr in soup.find_all('tr'):
            cells=tr.find_all('td')
            if not cells:continue
            when=date_from(cells[0].get_text(' ',strip=True).replace('\xa0',' '))
            anchor=tr.find('a',string=re.compile('Media release',re.I))
            if when and anchor and anchor.get('href'):
                records.append({'title':'Official Cash Rate decision','link':urljoin(url,anchor['href']), 'published':when.isoformat(),'officialArchive':True})
        return records
    links={}
    for a in soup.find_all('a',href=True):
        href=urljoin(url,a['href'])
        if re.search(pattern,href) and not re.search('summary|introductory',a.get_text(),re.I):
            links[href]=a.get_text(' ',strip=True)
    result=[]
    for href,title in sorted(links.items(),reverse=True)[:12]:
        when=date_from(href+' '+title)
        if not href.lower().endswith('.pdf'):
            doc=BeautifulSoup(api.get(href).text,'html.parser')
            headline=doc.find('h1')
            title=title or (headline.get_text(' ',strip=True) if headline else '')
            for node in doc.find_all(['time','meta']):
                raw=node.get('datetime') or (node.get('content') if 'date' in str(node.get('property') or node.get('name')).lower() else '')
                found=date_from(raw or '')
                if found and not when:when=found;break
            if not when:
                text=doc.get_text(' ',strip=True)
                found=re.search(r'Published on\s+(\d{1,2} [A-Za-z]+ 20\d{2})',text)
                if found:when=date_from(found[1])
        if when and when<=datetime.now(timezone.utc):
            result.append({'title':title or 'Statement on Monetary Policy','link':href,'published':when.isoformat(),'officialArchive':True})
    return result
