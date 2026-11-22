"""Explicit OHLC counterfactuals for one entry at a recorded bar open."""
import math


def simulate_management(bars, direction, stop, target, cost_bps=None):
    if not bars or direction not in ('long', 'short'):
        raise ValueError('Se requieren velas y dirección larga o corta')
    entry = bars[0]['open']
    sign = 1 if direction == 'long' else -1
    risk = sign * (entry-stop)
    target_r = sign * (target-entry)/risk if risk > 0 else 0
    if not all(map(math.isfinite, (stop, target, target_r))) or min(stop,target) <= 0 or target_r <= 1:
        raise ValueError('Stop inicial al lado incorrecto o objetivo no superior a 1R')
    if cost_bps is not None and (not math.isfinite(cost_bps) or cost_bps < 0):
        raise ValueError('Coste total no válido')
    costs_r = None if cost_bps is None else cost_bps/10000*entry/risk

    def level(price):
        return sign * (price-entry)/risk

    def run(rule):
        stop_r = -1.0
        remaining, realized = 1.0, 0.0
        partial = rule == 'half_at_1r'
        fills = []

        def execute(day, reason, price_r, quantity):
            nonlocal remaining, realized
            remaining -= quantity
            realized += price_r * quantity
            fills.append(dict(date=day, reason=reason, fill_r=price_r, fraction=quantity))

        for bar in bars:
            day = bar['date']
            op = level(bar['open'])
            low, high = sorted((level(bar['low']), level(bar['high'])))
            if op <= stop_r:
                execute(day, 'stop_at_open', op, remaining)
                break
            if partial and op >= 1:
                execute(day, 'partial_at_open', 1.0, .5)
                partial = False
            if op >= target_r:
                execute(day, 'target_at_open', target_r, remaining)
                break
            next_favorable = 1.0 if partial else target_r
            if low <= stop_r and high >= next_favorable:
                return dict(status='ambiguous', date=day, gross_r=None, net_r=None, fills=fills)
            if low <= stop_r:
                execute(day, 'stop', stop_r, remaining)
                break
            if partial and high >= 1:
                execute(day, 'partial', 1.0, .5)
                partial = False
            if high >= target_r:
                execute(day, 'target', target_r, remaining)
                break
            if rule == 'break_even_after_1r' and high >= 1:
                stop_r = max(stop_r, 0.0)
            if rule == 'trail_previous_close_1r':
                stop_r = max(stop_r, level(bar['close']) - 1.0)
        if remaining:
            execute(bars[-1]['date'], 'end_of_window', level(bars[-1]['close']), remaining)
        return dict(status='resolved', gross_r=realized,
                    net_r=None if costs_r is None else realized-costs_r, fills=fills)

    return dict(entry=entry, start=bars[0]['date'], end=bars[-1]['date'], stop=stop, target=target,
                direction=direction, cost_bps=cost_bps,
                horizon_mfe_r=max(0, *(level(r[k]) for r in bars for k in ('high','low'))),
                horizon_mae_r=min(0, *(level(r[k]) for r in bars for k in ('high','low'))),
                alternatives={name:run(name) for name in (
                    'original_stop_and_target', 'break_even_after_1r', 'trail_previous_close_1r', 'half_at_1r')})
