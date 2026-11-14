"""Combines the projection sources: ESPN, Sleeper, the usage model, and sportsbook props.
Weights for the first three are fitted each run against this season's actual results."""
import itertools
import numpy as np
from . import config as C
from .advanced import points_from

PRIOR = {"espn": 0.50, "sleeper": 0.30, "usage": 0.20}     # starting weights before any results are in
SHRINK = 0.5                                                # fitted weights are pulled halfway back to the prior
PROPS_WEIGHT = 0.30                                         # share given to sportsbook props when a player has lines
VEGAS_WEIGHT, VEGAS_CLIP = 0.5, (0.85, 1.15)


def _norm(w, keys):
    t = sum(w[k] for k in keys)
    return {k: w[k] / t for k in keys}


def fit_weights(L, W, adv, sleeper_hist=None, log=print):
    """Backtest each source on weeks 3..W-1 (rostered QB/RB/WR/TE) and pick the blend with the lowest error."""
    from .sleeper import key as skey
    report = {"weeks": [], "by_pos": {}}
    rows = []
    if adv is not None and adv.ok:
        for w in range(3, min(W, C.LAST_WEEK + 1)):
            if w not in L["box"]:
                continue
            U = adv.usage(w); seen = set(); sw = (sleeper_hist or {}).get(w) or {}
            for ents in L["box"][w].values():
                for e in ents:
                    if e["pos"] not in (1, 2, 3, 4) or e["proj"] <= 3 or e["pid"] in seen:
                        continue
                    seen.add(e["pid"])
                    u = U.get(e["pid"])
                    sl = sw.get(skey(e["name"], e["pos"], L["pro"].get(e["pro"], {}).get("abbrev", ""))) if e["name"] else None
                    rows.append((w, e["pos"], e["proj"], sl if sl and sl > 0.3 else np.nan,
                                 u["pts"] if u and not u["stale"] else np.nan, e["act"]))
            report["weeks"].append(w)
    R = np.array(rows, dtype=float) if rows else np.zeros((0, 6))
    weights = {}
    names = ["espn", "sleeper", "usage"]
    for pos in (1, 2, 3, 4):
        r = R[R[:, 1] == pos]
        avail = [n for i, n in enumerate(names) if len(r) and np.isfinite(r[:, 2 + i]).mean() > 0.6]
        if "espn" not in avail:
            avail = ["espn"] + [a for a in avail if a != "espn"]
        prior = _norm(PRIOR, avail) if len(r) else _norm(PRIOR, ["espn", "usage"] if adv is not None and adv.ok else ["espn"])
        w_final, rep = dict(prior), {"n": 0}
        if len(r):
            cols = [2 + names.index(a) for a in avail]
            ok = np.isfinite(r[:, cols]).all(axis=1)
            X, y = r[ok][:, cols], r[ok][:, 5]
            rm = lambda p: float(np.sqrt(np.mean((p - y) ** 2)))
            rep = {"n": int(len(y)), "rmse": {a: round(rm(X[:, i]), 2) for i, a in enumerate(avail)}}
            if len(y) >= 60:
                best = None
                steps = np.arange(0, 1.0001, 0.05)
                for combo in itertools.product(steps, repeat=len(avail) - 1):
                    if sum(combo) > 1.0001:
                        continue
                    wv = np.array(list(combo) + [1 - sum(combo)])
                    err = rm(X @ wv)
                    if best is None or err < best[0]:
                        best = (err, wv)
                fitted = dict(zip(avail, best[1]))
                w_final = {a: SHRINK * prior[a] + (1 - SHRINK) * float(fitted[a]) for a in avail}
                rep["rmse"]["blend"] = round(rm(X @ np.array([w_final[a] for a in avail])), 2)
        weights[pos] = {a: round(v, 3) for a, v in w_final.items()}
        rep["weights"] = weights[pos]
        report["by_pos"][C.POS[pos]] = rep
    return weights, report


def vegas_multipliers(odds, offense):
    """{team: multiplier} from implied team totals vs how well that offense has scored so far."""
    tot = odds.get("totals") or {}
    if not tot:
        return {}
    mean = sum(tot.values()) / len(tot)
    out = {}
    for team, imp in tot.items():
        ratio = (imp / mean) / max(0.6, offense.get(team, 1.0))
        out[team] = float(np.clip(1 + VEGAS_WEIGHT * (ratio - 1), *VEGAS_CLIP))
    return out


def props_points(pos, lines, comps, vm=1.0):
    """Projection built from a player's prop lines; touchdowns come from the usage model scaled by Vegas."""
    if pos == 5:
        return (lines["kp"] + 0.2) * 1.08 if "kp" in lines else None
    if comps is None or pos not in (1, 2, 3, 4):
        return None
    need = {1: ("py",), 2: ("ry", "cy"), 3: ("cy",), 4: ("cy",)}[pos]
    if not any(k in lines for k in need):
        return None
    c = dict(comps)
    if "py" in lines:
        c["pass_yd"] = lines["py"]
    c["pass_td"] = 0.5 * (lines["pt"] + 0.15) + 0.5 * comps["pass_td"] * vm if "pt" in lines else comps["pass_td"] * vm
    if "pi" in lines:
        c["int"] = 0.5 * (lines["pi"] + 0.2) + 0.5 * comps["int"]
    if "ry" in lines:
        ry = lines["ry"] * 1.04
        c["rush_fd"] = comps["rush_fd"] * (ry / comps["rush_yd"]) if comps["rush_yd"] > 5 else comps["rush_fd"]
        c["rush_yd"] = ry
    if "cy" in lines:
        c["rec_yd"] = lines["cy"] * 1.07
    if "rc" in lines:
        c["rec"] = lines["rc"] + 0.15
    c["rush_td"] = comps["rush_td"] * vm; c["rec_td"] = comps["rec_td"] * vm
    return float(points_from(c))


def context(L, W, adv, odds, sleeper_hist=None, log=print):
    """Everything the projection step needs, computed once per run."""
    ok = adv is not None and adv.ok
    weights, report = fit_weights(L, W, adv, sleeper_hist, log)
    X = {"weights": weights, "report": report, "usage": adv.usage(W) if ok else {}, "dvp": adv.dvp(W) if ok else {},
         "vol": adv.volatility() if ok else {}, "trends": adv.trends(W) if ok else {},
         "props": (odds or {}).get("props") or {}, "totals": (odds or {}).get("totals") or {},
         "vm": vegas_multipliers(odds or {}, adv.offense(W) if ok else {})}
    report["vegas_games"] = len(X["totals"]) // 2
    report["props_players"] = len(X["props"])
    report["advanced_stats"] = ok
    report["stats_through_week"] = adv.max_week if ok else None
    return X
