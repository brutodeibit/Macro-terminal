"""Descriptive close-based monthly and directional-change studies for FRED indices."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from atlas_engine import date_parse, stats


LABELS = {'NASDAQCOM': 'Nasdaq Composite', 'NASDAQ100': 'Nasdaq-100', 'SP500': 'S&P 500'}
THRESHOLD = .05


def load_snapshot(path, series, last):
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if reader.fieldnames != ['observation_date', series]:
        raise ValueError(f'Cabecera FRED inesperada para {series}')
    prices = {}
    previous = ''
    for row in reader:
        day = date_parse(row['observation_date']).isoformat()
        if day <= previous:
            raise ValueError(f'Fechas repetidas o desordenadas en {series}')
        previous = day
        if day <= last and row[series] not in ('.', ''):
            value = float(row[series])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'Cierre inválido para {series}, {day}')
            prices[day] = value
    if not prices:
        raise ValueError(f'Sin cierres para {series}')
    return prices, hashlib.sha256(raw).hexdigest()


def window(day):
    return '1–7' if day <= 7 else '8–15' if day <= 15 else '16–23' if day <= 23 else '24–fin'


def summarize_months(prices, sessions, last_complete_month, start_year):
    months = defaultdict(list)
    for day in sessions:
        months[day[:7]].append(day)
    off = {d[:7] for d in prices.keys() - set(sessions)}
    observations = defaultdict(list)
    excluded = []
    for (prior_month, prior), (month, days) in zip(list(months.items()), list(months.items())[1:]):
        if not f'{start_year}-01' <= month <= last_complete_month:
            continue
        anchor = prices.get(prior[-1])
        if not anchor or prior_month in off or month in off or any(day not in prices for day in days):
            excluded.append(month)
            continue
        closes = [prices[d] for d in days]
        peak = int(days[closes.index(max(closes))][8:])
        trough = int(days[closes.index(min(closes))][8:])
        observations[int(month[5:])].append((100*(closes[-1]/anchor-1), peak, trough))
    result = {}
    for month, group in sorted(observations.items()):
        returns, highs, lows = zip(*group)
        q = statistics.quantiles(returns, n=4, method='inclusive') if len(returns)>1 else [returns[0]]*3
        result[str(month)] = dict(stats(returns), down=sum(x < 0 for x in returns)/len(returns),
                                  p25=q[0], p75=q[2], high_median_day=statistics.median(highs),
                                  low_median_day=statistics.median(lows),
                                  high_windows=dict(Counter(map(window, highs))),
                                  low_windows=dict(Counter(map(window, lows))))
    return dict(start_year=start_year, last_month=last_complete_month, months=result, excluded=excluded)


def pivots(rows, threshold=THRESHOLD):
    """Confirm a pivot only on a later close at least threshold from the extreme."""
    if not rows:
        return []
    lo = hi = 0
    direction = 0
    result = []
    for i, (_, price) in enumerate(rows):
        if direction <= 0 and price < rows[lo][1]:
            lo = i
        if direction >= 0 and price > rows[hi][1]:
            hi = i
        if direction <= 0 and price >= rows[lo][1]*(1+threshold):
            result.append((lo, i, 'low'))
            hi, direction = i, 1
        elif direction >= 0 and price <= rows[hi][1]*(1-threshold):
            result.append((hi, i, 'high'))
            lo, direction = i, -1
    return result


def swing_report(prices, sessions):
    segments, current = [], []
    for day in sessions:
        if day in prices:
            current.append((day, prices[day]))
        elif current:
            segments.append(current)
            current = []
    if current:
        segments.append(current)
    sides = defaultdict(list)
    live = None
    for rows in segments:
        points = pivots(rows)
        previous_size = None
        for (a, _, _), (b, confirmation, kind) in zip(points, points[1:]):
            start, end = rows[a][1], rows[b][1]
            size = abs(end-start)
            sides[kind].append(dict(return_pct=100*(end/start-1), sessions=b-a,
                                    confirmation_lag=confirmation-b,
                                    retracement_pct=100*size/previous_size if previous_size else None))
            previous_size = size
        if points and rows[-1][0] == max(prices):
            anchor, confirmation, kind = points[-1]
            day, price = rows[anchor]
            latest = rows[-1][1]
            live = dict(last_pivot=kind, extreme_date=day, confirmation_date=rows[confirmation][0],
                        asof=rows[-1][0], change_from_pivot_pct=100*(latest/price-1),
                        retracement_of_prior_leg_pct=100*abs(latest-price)/previous_size if previous_size else None)
    return dict(threshold_pct=THRESHOLD*100, latest=live, groups={
        kind:{field:stats([r[field] for r in group]) for field in (
            'return_pct','sessions','confirmation_lag','retracement_pct')}
        for kind, group in sides.items()})


def phase_statistics(path):
    """Summarize reviewed chart annotations and keep incomplete phases in the denominator audit."""
    groups = defaultdict(lambda: {'bars': [], 'hours': [], 'open': 0})
    seen = set()
    with path.open(encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        required = {'instrument','timeframe','phase','start','end','bars','evidence'}
        if set(reader.fieldnames or []) != required:
            raise ValueError('Cabecera requerida: '+', '.join(sorted(required)))
        for row in reader:
            instrument, tf, phase = (row[k].strip() for k in ('instrument','timeframe','phase'))
            if not instrument or tf not in ('W','D','4H','1H') or phase not in ('accumulation','distribution'):
                raise ValueError('Instrumento, temporalidad o etiqueta inválida')
            if not row['evidence'].strip():
                raise ValueError('Falta evidencia de la revisión del gráfico')
            start = dt.datetime.fromisoformat(row['start'])
            if start.utcoffset() is None:
                raise ValueError('La fecha de inicio requiere zona horaria')
            key = (instrument, tf, phase, start)
            if key in seen:
                raise ValueError('Fase duplicada')
            seen.add(key)
            group = groups[instrument, tf, phase]
            if not row['end']:
                group['open'] += 1
                continue
            end = dt.datetime.fromisoformat(row['end'])
            if end.utcoffset() is None or end < start or int(row['bars']) < 1:
                raise ValueError('Final, zona horaria o duración inválida')
            group['bars'].append(int(row['bars']))
            group['hours'].append((end-start).total_seconds()/3600)
    return [dict(instrument=i,timeframe=t,phase=p,open=g['open'],bars=stats(g['bars']),
                 elapsed_hours=stats(g['hours'])) for (i,t,p),g in sorted(groups.items())]


def main():
    import exchange_calendars as xcals

    parser = argparse.ArgumentParser(description=__doc__)
    for series in LABELS:
        parser.add_argument('--'+series.lower(), type=Path, required=True)
    parser.add_argument('--last-date', required=True)
    parser.add_argument('--complete-through', required=True, help='Last full month, YYYY-MM')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phases', type=Path, help='Optional CSV of reviewed Wyckoff phase annotations')
    args = parser.parse_args()
    last = date_parse(args.last_date).isoformat()
    complete = date_parse(args.complete_through+'-01').isoformat()[:7]
    if complete >= last[:7]:
        parser.error('El mes completo debe preceder al mes del corte diario')
    calendar = xcals.get_calendar('XNYS', start='1971-02-01', end=last)
    expected = [d.date().isoformat() for d in calendar.sessions]
    series_reports = {}
    for key, label in LABELS.items():
        source = getattr(args, key.lower())
        prices, sha = load_snapshot(source, key, last)
        first, final = min(prices), max(prices)
        sessions = [d for d in expected if first[:7] <= d[:7] and d <= last]
        observed_range = {d for d in sessions if first <= d <= final}
        series_reports[key] = dict(label=label, first=first, last=final, observations=len(prices),
            source=f'https://fred.stlouisfed.org/series/{key}', sha256=sha,
            missing_sessions=sorted(observed_range-prices.keys()), off_calendar=sorted(prices.keys()-observed_range),
            full=summarize_months(prices, sessions, complete, int(first[:4])),
            common=summarize_months(prices, sessions, complete, 2017),
            swings=swing_report(prices, [d for d in sessions if first <= d <= final]))
    report = dict(schema='atlas-index-history-v1', calendar=f'XNYS exchange_calendars {xcals.__version__}',
                  complete_through=complete, series=series_reports)
    if args.phases:
        report['reviewed_phases'] = phase_statistics(args.phases)
    with args.output.open('x', encoding='utf-8') as file:
        json.dump(report, file, indent=2, ensure_ascii=False, allow_nan=False)


if __name__ == '__main__':
    main()
