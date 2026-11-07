"""Reproducible equity/ETF gamma scenario model. Not observed dealer inventory."""
import math


def gamma_flip(rows, spot, years, rate=0.04, dividend=0.0, multiplier=100.0):
    result = {"gammaFlip": None, "zeroGamma": None, "gammaFlipRoots": [],
              "gammaFlipStatus": "Insufficient data", "gammaFlipModel": {
                  "method": "Black-Scholes spot repricing; constant strike IV; calls positive, puts negative",
                  "rate": rate, "dividendYield": dividend, "multiplier": multiplier,
                  "rangePct": [-30, 30], "observedDealerPositions": False}}
    if not spot or spot <= 0 or years <= 0:
        result["gammaFlipStatus"] = "Expired or invalid underlying"
        return result
    valid = []
    total = 0.0
    for row in rows:
        oi = row.get("openInterest")
        if not isinstance(oi, (int, float)) or not math.isfinite(oi) or oi <= 0:
            continue
        total += oi
        k, iv = row.get("strike"), row.get("iv")
        if (isinstance(k, (int, float)) and math.isfinite(k) and k > 0
                and isinstance(iv, (int, float)) and math.isfinite(iv) and 0 < iv < 3
                and row.get("type") in ("C", "P") and row.get("oiDataAvailable", True)):
            t = row.get('yearsToExpiry', years)
            if isinstance(t,(int,float)) and math.isfinite(t) and t>0:
                valid.append((k, iv, oi, 1 if row["type"] == "C" else -1, t))
    coverage = sum(x[2] for x in valid) / total if total else 0
    result["gammaFlipCoveragePct"] = round(coverage * 100, 2)
    if coverage < .9 or len({x[3] for x in valid}) < 2:
        return result

    def exposure(s, put_weight=1.0, iv_shift=1.0):
        value = 0.0
        for k, iv, oi, sign, t in valid:
            vol = iv * iv_shift
            d1 = (math.log(s / k) + (rate - dividend + vol * vol / 2) * t) / (vol * math.sqrt(t))
            gamma = math.exp(-dividend * t - d1 * d1 / 2) / (math.sqrt(2 * math.pi) * s * vol * math.sqrt(t))
            value += sign * (put_weight if sign < 0 else 1) * oi * gamma * multiplier * s * s * .01
        return value

    def roots(weight=1.0, shift=1.0):
        found = []
        a = spot * .7
        fa = exposure(a, weight, shift)
        for i in range(1, 241):
            b = spot * (.7 + .6 * i / 240)
            fb = exposure(b, weight, shift)
            if fa * fb < 0:
                lo, hi, flo = a, b, fa
                for _ in range(35):
                    mid = (lo + hi) / 2
                    fm = exposure(mid, weight, shift)
                    if flo * fm <= 0:
                        hi = mid
                    else:
                        lo, flo = mid, fm
                root = (lo + hi) / 2
                if not found or abs(root - found[-1]) > spot * 1e-6:
                    found.append(root)
            a, fa = b, fb
        return found

    crossings = roots()
    nearest = min(crossings, key=lambda x: abs(x - spot)) if crossings else None
    result.update(gammaFlip=nearest, zeroGamma=nearest, gammaFlipRoots=crossings,
                  gammaFlipStatus="MODELED" if crossings else "No sign change within ±30% of spot",
                  gammaFlipSensitivity={"putWeight80": roots(.8), "putWeight120": roots(1.2),
                                        "iv90": roots(1, .9), "iv110": roots(1, 1.1)})
    return result
