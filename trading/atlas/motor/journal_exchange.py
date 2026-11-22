"""Read-only conversion of Trading Journal JSON backups to exchange v2."""
import datetime as dt
import math
import re
import statistics
from collections import Counter, defaultdict


CLASSIFICATIONS = {
    'higherBias': ('bullish', 'bearish', 'neutral', 'unknown'),
    'alignment': ('trend', 'countertrend', 'range', 'unknown'),
    'opportunityType': ('continuation', 'reversal', 'range', 'other'),
    'regimeSource': ('observed', 'model', 'unavailable'),
    'reviewDecision': ('pending', 'valid', 'errors'),
}
TEXT_FIELDS = ('setup', 'setupVersion', 'session', 'marketRegime', 'marketCondition', 'executionTf',
               'entryTrigger', 'locationQuality', 'planCompliance')


def classification(trade):
    result = {}
    for key in (*CLASSIFICATIONS, *TEXT_FIELDS):
        value = trade.get(key)
        if value in (None, ''):
            continue
        if key == 'setupVersion' and not isinstance(value, bool) and isinstance(value, (int, float)):
            value = str(value)
        if not isinstance(value, str) or (key in CLASSIFICATIONS and value not in CLASSIFICATIONS[key]):
            # Existing free-text metadata can lack a normalized value.
            if key in CLASSIFICATIONS:
                raise ValueError('Clasificación no válida: '+key)
            continue
        result[key] = value
    result['errors'] = [name for name, key in (('analysis', 'errorAnalysis'),
                        ('execution', 'errorExecution'), ('management', 'errorManagement')) if trade.get(key) == 'yes']
    return result


def decision_summary(records):
    groups = defaultdict(list)
    for row in records:
        if row['state'] != 'cerrada':
            continue
        metadata = row['classification']
        setup = row['setup_id'] or metadata.get('setup')
        if setup and metadata.get('setupVersion'):
            setup = f"{setup} · v{metadata['setupVersion']}"
        opened = min(leg['executed_at'] for leg in row['legs'])
        exits = [fill for leg in row['legs'] for fill in leg['exits']]
        timestamps = [fill['instant'] for fill in exits]
        close_time = (max(dt.datetime.fromisoformat(x.replace('Z', '+00:00')) for x in timestamps)
                      if timestamps and all(timestamps) else None)
        day = max(fill['local'][:10] for fill in exits)
        regime = metadata.get('marketRegime') if metadata.get('regimeSource') in ('observed', 'model') else None
        values = {
            'setup': setup,
            'opportunityType': metadata.get('opportunityType'),
            'alignment': metadata.get('alignment'),
            'session': metadata.get('session'),
            'hour': opened[11:13]+'h · '+(row['session_timezone'] or 'zona sin registrar'),
            'marketCondition': metadata.get('marketCondition'),
            'marketRegime': metadata['regimeSource']+' · '+regime if regime else None,
            'reviewDecision': metadata.get('reviewDecision'),
            'planCompliance': metadata.get('planCompliance'),
        }
        for key, label in values.items():
            cohort = (row['mode'], row['product'], row['currency'], row['costs_complete'])
            groups[(*cohort, key, label or 'sin registrar')].append((
                row['realized_net'], row['realized_net']/row['initial_risk'], close_time, opened[:10], day))
    result = []
    for (mode, product, currency, costs, axis, value), rows in groups.items():
        net, rs, _, opened, closed = zip(*rows)
        drawdown = None
        if all(row[2] is not None for row in rows):
            by_close = defaultdict(list)
            for _, r, at, *_ in rows:
                by_close[at].append(r)
            equity = peak = drawdown = 0.0
            for at in sorted(by_close):
                equity += math.fsum(by_close[at])
                peak = max(peak, equity)
                drawdown = max(drawdown, peak-equity)
        result.append(dict(mode=mode, product=product, currency=currency, costs_complete=costs,
                           axis=axis, value=value, n=len(rows), start=min(opened), end=max(closed),
                           expectancy_net=statistics.mean(net), mean_r=statistics.mean(rs),
                           median_r=statistics.median(rs), win_rate=sum(x > 1e-8 for x in net)/len(rows),
                           drawdown_r=drawdown, distribution_r=sorted(rs)))
    return result


def identifier(value, seen):
    if not isinstance(value, str) or not re.fullmatch(r'[-\w]{1,120}', value):
        raise ValueError('ID del Journal inválido')
    if value in seen:
        raise ValueError('ID del Journal duplicado: '+value)
    seen.add(value)
    return value


def number(value, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (str, float, int)):
        raise ValueError('Número ausente o inválido en Journal')
    result = float(value)
    if not math.isfinite(result) or result < 0 or (not zero and result == 0):
        raise ValueError('Precio, cantidad, multiplicador o coste inválido')
    return result


def stamp(row, key):
    local = row.get(key)
    if not isinstance(local,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?',local):
        raise ValueError('Hora local ausente o inválida')
    wall = dt.datetime.fromisoformat(local)
    absolute = row.get(key+'Instant')
    if absolute is None:
        return local, None, wall
    actual = dt.datetime.fromisoformat(absolute.replace('Z','+00:00'))
    if actual.tzinfo is None:
        raise ValueError('Instante sin zona')
    return local, absolute, actual


def from_journal(data):
    if not isinstance(data['trades'], list):
        raise ValueError('Lista de operaciones ausente')
    legacy = data['version'] == 1
    records = []
    trades_seen = set()
    for trade in data['trades']:
        tid = identifier(trade.get('id'), trades_seen)
        product = trade.get('product') or 'derivative'
        mode, direction, currency = (trade.get(k) for k in ('mode','direction','currency'))
        if product not in ('derivative','option'):
            raise ValueError('Producto de Journal inválido')
        directions = ('long','short','neutral') if product == 'option' else ('long','short')
        if mode not in ('real','demo','backtest') or direction not in directions:
            raise ValueError('Modo o dirección de Journal inválidos')
        if not isinstance(currency,str) or not re.fullmatch(r'[A-Z0-9]{3,8}',currency):
            raise ValueError('Divisa inválida')
        mul = number(trade.get('multiplier'))
        if not isinstance(trade.get('legs'),list) or not trade['legs']:
            raise ValueError('Operación sin entradas')
        legs, leg_ids, exit_ids = [], set(), set()
        for i, leg in enumerate(trade['legs']):
            lid = identifier(f'legacy-{i}' if legacy else leg.get('id'), leg_ids)
            entry, quantity = (number(leg.get(k)) for k in ('entry','size'))
            stop = None if product == 'option' else number(leg.get('stop'))
            if product == 'derivative' and (entry <= stop if direction=='long' else entry >= stop):
                raise ValueError('Stop inicial al lado incorrecto')
            option_type = leg.get('optionType') if product == 'option' else None
            side = leg.get('side') if product == 'option' else None
            if product == 'option':
                if option_type not in ('call','put') or side not in ('buy','sell'):
                    raise ValueError('Tipo o lado de opción inválido')
                strike = number(leg.get('strike'))
                expiry = leg.get('expiry')
                if not isinstance(expiry,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',expiry):
                    raise ValueError('Vencimiento de opción inválido')
            else:
                strike, expiry = None, None
            opening, opened_at, start = stamp(leg,'open')
            if legacy:
                has_exit = leg.get('exit') not in (None,'')
                if not has_exit and leg.get('close'):
                    raise ValueError('Cierre antiguo sin precio')
                exits = [dict(leg,id=lid+'-exit',price=leg['exit'],cost=0)] if has_exit else []
            else:
                exits = leg.get('exits')
            if not isinstance(exits,list):
                raise ValueError('Salidas inválidas')
            fills = []
            for fill in exits:
                eid = identifier(fill.get('id'), exit_ids)
                closing, closed_at, end = stamp(fill,'close')
                if (end < start if end.tzinfo and start.tzinfo else closing < opening):
                    raise ValueError('Salida anterior a la entrada')
                fills.append(dict(exit_id=eid,price=number(fill.get('price')),
                                  quantity=number(fill.get('size')),cost=number(fill.get('cost'),zero=True),
                                  local=closing,instant=closed_at))
            filled = math.fsum(x['quantity'] for x in fills)
            complete = math.isclose(filled,quantity,rel_tol=1e-10)
            if filled > quantity and not complete:
                raise ValueError('Los parciales superan el tamaño de la entrada '+lid)
            stop_moves = []
            for move in leg.get('stopMoves', []):
                local, instant, _ = stamp(move, 'at')
                stop_moves.append(dict(local=local, instant=instant, price=number(move.get('price')),
                                       kind=move.get('kind') or None, scope=move.get('scope'),
                                       quantity=number(move.get('size')) if move.get('scope')=='partial' else None,
                                       reason=move.get('reason')))
            try:
                target = number(leg.get('tp')) if product == 'derivative' else None
            except (ValueError, TypeError):
                target = None
            legs.append(dict(leg_id=lid,kind=leg.get('kind'),entry=entry,stop_initial=stop,
                             quantity=quantity,entry_cost=number(leg.get('cost'),zero=True),
                             option_type=option_type,side=side,strike=strike,expiry=expiry,
                             executed_at=opening,executed_instant=opened_at,exits=fills,closed=complete,
                             target=target,
                             stop_moves=stop_moves))
        risk = (number(trade.get('plannedRisk')) if product == 'option' else
                math.fsum(abs(l['entry']-l['stop_initial'])*l['quantity']*mul for l in legs))
        direction_sign = 1 if direction=='long' else -1
        net = math.fsum(-l['entry_cost']+math.fsum(
            ((1 if l['side']=='buy' else -1) if product == 'option' else direction_sign)
            *(x['price']-l['entry'])*x['quantity']*mul-x['cost'] for x in l['exits']) for l in legs)
        if not math.isfinite(net) or not math.isfinite(risk) or risk<=0 or not math.isfinite(net/risk):
            raise ValueError('Resultado fuera de rango')
        records.append(dict(trade_id='journal:'+tid,signal_id=None,strategy_id=trade.get('strategyId') or None,
                            setup_id=trade.get('setupId') or None,mode=mode,direction=direction,
                            product=product,option_structure=trade.get('optionStructure') or None,
                            asset=trade.get('asset'),currency=currency,multiplier=mul,
                            session_timezone=trade.get('timezone') or None,legs=legs,
                            state='cerrada' if all(l['closed'] for l in legs) else 'abierta',
                            costs_complete=trade.get('costQuality')=='completo',
                            initial_risk=risk,realized_net=net,classification=classification(trade)))
    opportunities = []
    if not isinstance(data.get('opportunities', []), list):
        raise ValueError('Lista de oportunidades inválida')
    for trade in data.get('opportunities', []):
        tid = identifier(trade.get('id'), trades_seen)
        status = trade.get('opportunityStatus')
        if status not in ('pending', 'discarded'):
            raise ValueError('Estado de oportunidad inválido')
        opportunities.append(dict(trade_id='journal:'+tid, status=status, asset=trade.get('asset'),
                                  setup_id=trade.get('setupId') or None, classification=classification(trade)))
    return dict(schema='atlas-journal-exchange-v2',source='TradingJournal',records=records,
                opportunities=opportunities, opportunity_counts=dict(Counter(x['status'] for x in opportunities)),
                decision_summary=decision_summary(records))
