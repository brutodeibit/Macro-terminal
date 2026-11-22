"""Daily European index option scenarios from Eurex settlement prices.

Derived IV/Greeks are models, not exchange-supplied Greeks or dealer inventory.
Discount and forward are fitted from same-expiry put/call settlement parity;
no fixed interest rate, generic IV or borrowed ETF volatility is substituted.
"""
from datetime import date
import math
from v7_quant import gamma_flip

CONTRACTS = {'ODAX': (5, .1), 'ODAP': (5, .1), 'OESX': (10, .1),
             'OEXP': (10, .1), 'OXXP': (50, .05)}


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def cdf(x):
    return .5 * (1 + math.erf(x / math.sqrt(2)))


def black_price(forward, strike, total_vol, discount, side):
    if total_vol <= 0:
        return discount * max((forward - strike) * (1 if side == 'C' else -1), 0)
    d1 = math.log(forward / strike) / total_vol + total_vol / 2
    d2 = d1 - total_vol
    return discount * (forward * cdf(d1) - strike * cdf(d2)) if side == 'C' else \
        discount * (strike * cdf(-d2) - forward * cdf(-d1))


def fit_parity(rows, spot, years, tick):
    pairs = {}
    for row in rows:
        k, price = row.get('strike'), row.get('settlementPrice')
        if (number(k) and .85 <= k / spot <= 1.15 and number(price) and price > 0
                and row.get('version') in (None, 0) and row.get('type') in ('C', 'P')):
            pair = pairs.setdefault(k, {})
            if row['type'] in pair:
                raise ValueError('Duplicate contract version at the same strike')
            pair[row['type']] = price
    points = [(k, p['C'] - p['P']) for k, p in pairs.items() if len(p) == 2]
    if len(points) < 7 or max(k for k, _ in points) - min(k for k, _ in points) < .02 * spot:
        raise ValueError('Insufficient matched call/put settlements for carry fit')
    mx = sum(k for k, _ in points) / len(points)
    my = sum(y for _, y in points) / len(points)
    slope = sum((k - mx) * (y - my) for k, y in points) / sum((k - mx) ** 2 for k, _ in points)
    discount = -slope
    if discount <= 0:
        raise ValueError('Invalid fitted discount factor')
    forward = (my - slope * mx) / discount
    rate = -math.log(discount) / years
    if forward <= 0 or not .9 < forward / spot < 1.1 or not -.15 < rate < .3:
        raise ValueError('Unstable or implausible settlement carry fit')
    errors = [y - (my + slope * (k - mx)) for k, y in points]
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    if rmse > tick or max(abs(e) for e in errors) > 2 * tick:
        raise ValueError('Call/put settlements fail parity consistency checks')
    dividend = rate - math.log(forward / spot) / years
    return dict(forward=forward, discountFactor=discount, rate=rate,
                dividendYield=dividend, pairedStrikes=len(points), parityRmse=rmse,
                parityMaxError=max(abs(e) for e in errors))


def implied_total_vol(price, forward, strike, discount, side):
    lower = discount * max((forward - strike) * (1 if side == 'C' else -1), 0)
    upper = discount * (forward if side == 'C' else strike)
    # At rounded intrinsic value, volatility is unidentifiable, not zero.
    if price <= lower + 1e-7 or price >= upper:
        return None
    lo, hi = 1e-6, 5.0
    if black_price(forward, strike, hi, discount, side) < price:
        return None
    for _ in range(65):
        mid = (lo + hi) / 2
        if black_price(forward, strike, mid, discount, side) > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def settlement_model(rows, spot, observed_day, expiration, code):
    result = {'gammaFlip': None, 'gammaFlipStatus': 'Insufficient settlement inputs',
              'settlementModel': {'status': 'unavailable', 'observedAt': observed_day,
                                  'providerIv': False, 'providerGreeks': False}}
    meta = result['settlementModel']
    try:
        if code not in CONTRACTS:
            raise ValueError('Exercise style/model not validated for this contract')
        if not number(spot) or spot <= 0:
            raise ValueError('Missing same-date underlying close')
        days = (expiration.date() - date.fromisoformat(observed_day)).days
        if days < 2:
            raise ValueError('Date-only settlement inputs: intraday/one-day model disabled')
        years = days / 365
        multiplier, tick = CONTRACTS[code]
        fit = fit_parity(rows, spot, years, tick)
        forward, discount = fit['forward'], fit['discountFactor']
        model_rows = []
        for row in rows:
            price, strike = row.get('settlementPrice'), row.get('strike')
            total_vol = implied_total_vol(price, forward, strike, discount, row['type']) if (
                number(price) and price > 0 and number(strike) and strike > 0 and
                row.get('version') in (None, 0)) else None
            iv = total_vol / math.sqrt(years) if total_vol is not None else None
            if iv is not None and not .005 < iv < 3:
                iv = None
            model_rows.append({**row, 'iv': iv})
        total_oi = sum(r['openInterest'] for r in rows)
        valid = [r for r in model_rows if r['iv'] is not None]
        coverage = sum(r['openInterest'] for r in valid) / total_oi if total_oi else None
        meta.update(**fit, multiplier=multiplier, currency='EUR', years=years,
                    timeConvention='ACT/365 by observation and expiry dates; no intraday valuation',
                    status='derived', oiCoveragePct=round(coverage * 100, 2) if coverage is not None else None,
                    method='Black-76 settlement inversion; same-expiry put/call parity carry fit',
                    assumptions='Fixed OI, fitted carry and strike IV; calls positive, puts negative; not observed dealer inventory')
        near = [min((r for r in valid if r['type'] == side),
                    key=lambda r: abs(r['strike'] - forward), default=None) for side in ('C', 'P')]
        if all(near) and all(abs(r['strike'] / forward - 1) <= .02 for r in near):
            result.update(ivAtm=50 * sum(r['iv'] for r in near),
                          ivAtmMethod='Mean call/put settlement IV within 2% of fitted forward',
                          ivCoveragePct=round(100*len(valid)/max(1,len(rows)), 2),
                          providerIvCoveragePct=0, providerGreeksCoveragePct=0)
        result['gammaFlipCoveragePct'] = meta['oiCoveragePct']
        if coverage is None:
            raise ValueError('Sin interés abierto positivo reportado en la cadena')
        # Require enough OI for the entire exposure profile, not just the root.
        if coverage < .9:
            raise ValueError('Less than 90% of reported OI has identifiable settlement IV')
        if len({r['type'] for r in valid if r['openInterest'] > 0}) < 2:
            raise ValueError('Se requiere interés abierto valorizable en calls y puts')
        result.update(gamma_flip(model_rows, spot, years, fit['rate'], fit['dividendYield'], multiplier))
        strikes = {}
        for r in rows:
            z = strikes.setdefault(r['strike'], dict(strike=r['strike'], gex=None,
                        callOi=0, putOi=0, callVolume=0, putVolume=0))
            side = 'call' if r['type'] == 'C' else 'put'
            z[side+'Oi'] += r['openInterest']
            z[side+'Volume'] += r.get('volume') or 0
        positive = negative = 0.0
        for r in valid:
            vol = r['iv'] * math.sqrt(years)
            d1 = math.log(forward / r['strike']) / vol + vol / 2
            gamma = discount * forward / spot * math.exp(-d1*d1/2) / (math.sqrt(2*math.pi) * spot * vol)
            value = (1 if r['type'] == 'C' else -1) * r['openInterest'] * gamma * multiplier * spot**2 * .01
            if value >= 0:
                positive += value
            else:
                negative += value
            z = strikes[r['strike']]
            z['gex'] = (z['gex'] or 0) + value
        # An uncovered strike remains missing even when total OI coverage passes.
        covered_keys = {(r['type'], r['strike']) for r in valid}
        for r in rows:
            if r['openInterest'] > 0 and (r['type'], r['strike']) not in covered_keys:
                strikes[r['strike']]['gex'] = None
        result.update(gammaPositive=positive, gammaNegative=negative,
                      gammaNet=positive+negative, gammaTotal=positive+negative,
                      gammaRegime='MODELED · settlement-derived · partial coverage' if coverage < 1 else 'MODELED · settlement-derived',
                      gammaEffect='Daily scenario; not an intraday hedge-flow observation',
                      strikeMap=sorted(strikes.values(), key=lambda r: r['strike']),
                      gexUnit='EUR per 1% underlying move', gexCurrency='EUR',
                      gammaCoveragePct=round(coverage*100, 2),
                      ivCoveragePct=round(100*len(valid)/max(1,len(rows)), 2),
                      providerIvCoveragePct=0, providerGreeksCoveragePct=0)
        return result
    except (ValueError, TypeError, OverflowError, ZeroDivisionError) as exc:
        meta.update(status='unavailable', reason=str(exc))
        result['gammaFlipStatus'] = 'Unavailable: ' + str(exc)
        return result
