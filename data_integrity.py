"""Pure transforms. Observation periods are not publication timestamps."""
from datetime import date
import math

def monthly_value(rows, year, month):
    return rows.get(f'{year:04d}-{month:02d}')

def transform_monthly(rows, period, mode):
    value = rows.get(period)
    if value is None or not math.isfinite(value):
        return None
    year, month = map(int, period[:7].split('-'))
    if mode == 'level':
        return value
    if mode == 'yoy':
        base = monthly_value(rows, year-1, month)
        return (value/base-1)*100 if base is not None and base > 0 else None
    if mode == 'change':
        previous = date(year, month, 1).toordinal()-1
        d = date.fromordinal(previous)
        base = monthly_value(rows, d.year, d.month)
        return value-base if base is not None else None
    raise ValueError(mode)

def bls_observation(rows, series):
    values = {f"{r['year']}-{r['period'][1:]}": float(r['value'])
              for r in rows if r.get('period','').startswith('M')
              and 1 <= int(r['period'][1:]) <= 12}
    if not values:
        return None
    period = max(values)
    mode = {'CES0000000001':'change','CES0500000003':'yoy'}.get(series,'level')
    value = transform_monthly(values, period, mode)
    return (value, period, mode) if value is not None else None
