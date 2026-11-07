"""Closing-price breadth, with explicit sample requirements (no intraday highs)."""
def same_session(rows):
    counts = {}
    for _, bars in rows:
        day = bars[-1]['date']
        counts[day] = counts.get(day, 0)+1
    if not counts:
        return []
    day = max(counts, key=lambda d:(counts[d],d))
    return [r for r in rows if r[1][-1]['date']==day]

def price_metrics(bars, year):
    values = [r['close'] for r in bars]
    last = values[-1] if values else None
    sma = {n: sum(values[-n:])/n if len(values)>=n else None for n in (20,50,100,200)}
    prior_year = [r['close'] for r in bars if r['date'].year == year-1]
    annual = values[-252:] if len(values)>=252 else []
    prior = values[-253:-1] if len(values)>=253 else []
    return {'sma':sma,
            'ytd':last/prior_year[-1]-1 if last is not None and prior_year and prior_year[-1] else None,
            'nearHigh':last>=max(annual)*.99 if annual else None,
            'nearLow':last<=min(annual)*1.01 if annual else None,
            'newClosingHigh':last>max(prior) if prior else None,
            'newClosingLow':last<min(prior) if prior else None}
