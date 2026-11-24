"""Keep the last chain on source failure without giving it a new observation date."""
from copy import deepcopy
from datetime import datetime, timezone


def has_strikes(market):
    return any(p.get('strikeMap') or p.get('topGexStrikes') for p in market.get('profiles', []))


def retain_chains(current, previous):
    old = {m.get('ticker'): m for m in previous}
    result = []
    for market in current:
        prior = old.pop(market.get('ticker'), None)
        if prior and has_strikes(prior) and not has_strikes(market):
            retained = deepcopy(prior)
            retained.update(retainedChain=True, referenceOnly=False,
                            dataStatus='STALE · última cadena conservada; consulta sin cadena nueva',
                            updatedAttempt=datetime.now(timezone.utc).isoformat())
            # Never combine today's spot with yesterday's strike-derived levels.
            retained['latestReference'] = {k: deepcopy(market[k]) for k in
                ('spot', 'quote', 'asOf', 'source', 'dataStatus', 'stats') if k in market}
            if market.get('layers'):
                retained.setdefault('layers', {}).update(deepcopy(market['layers']))
            result.append(retained)
        else:
            if prior and prior.get('recoveryArchive'):
                market = deepcopy(market)
                market['recoveryArchive'] = deepcopy(prior['recoveryArchive'])
            result.append(market)
    for prior in old.values():
        if has_strikes(prior):
            result.extend(retain_chains([{'ticker': prior['ticker']}], [prior]))
    return result
