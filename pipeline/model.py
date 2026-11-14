"""Season simulator: builds each team's weekly expectations, then plays the rest of the season many times."""
import math
import numpy as np
from . import config as C

Z10 = 1.2816


def american(p):
    if p <= 0:
        return None
    if p >= 1:
        return -100000
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def calibration(L, W):
    """Share of projection that starters have actually scored, by position, through week W-1."""
    A, P = {k: 0.0 for k in C.CAL_PRIOR}, {k: 0.0 for k in C.CAL_PRIOR}
    for w in range(1, W):
        for ents in L["box"].get(w, {}).values():
            for e in ents:
                if e["slot"] in (C.BENCH_SLOT, C.IR_SLOT) or e["proj"] <= 0 or e["pos"] not in A:
                    continue
                A[e["pos"]] += e["act"]; P[e["pos"]] += e["proj"]
    return {k: (A[k] + C.CAL_PRIOR[k] * C.CAL_PRIOR_PTS) / (P[k] + C.CAL_PRIOR_PTS) for k in A}


def form(L, W, cal, team_ids):
    """How much each team has beaten its starters' projections per week, shrunk toward zero and centered."""
    res = {t: [] for t in team_ids}
    for w in range(1, W):
        for t, ents in L["box"].get(w, {}).items():
            st = [e for e in ents if e["slot"] not in (C.BENCH_SLOT, C.IR_SLOT)]
            if st and t in res:
                res[t].append(sum(e["act"] for e in st) - sum(e["proj"] * cal.get(e["pos"], .95) for e in st))
    raw = {t: (sum(v) / len(v) if v else 0.0) for t, v in res.items()}
    mu = sum(raw.values()) / max(1, len(raw))
    n = max((len(v) for v in res.values()), default=0)
    w8 = n / (n + C.FORM_SHRINK_N) if n else 0.0
    return {t: w8 * (raw[t] - mu) for t in team_ids}


def has_game(L, pro, w):
    return w in (L["pro"].get(pro, {}).get("opp") or {})


def players_live(L, W, sleeper, cal, X=None):
    """Current rosters; each week's expectation blends ESPN, Sleeper, the usage model and (this week) props."""
    from .sleeper import key as skey
    from .blend import props_points, PROPS_WEIGHT, PRIOR
    X = X or {}
    out = []
    for t, ents in L["future"][W].items():
        for e in ents:
            if e["pos"] not in C.POS:
                continue
            pos = e["pos"]
            ab = L["pro"].get(e["pro"], {}).get("abbrev", "")
            k = skey(e["name"], pos, ab)
            u = (X.get("usage") or {}).get(e["pid"])
            vm = (X.get("vm") or {}).get(ab, 1.0)
            wts = (X.get("weights") or {}).get(pos) or {"espn": C.ESPN_SHARE[pos], "sleeper": 1 - C.ESPN_SHARE[pos]}
            mean, src = np.zeros(C.LAST_WEEK + 2), {}
            for w in range(W, C.LAST_WEEK + 1):
                fe = next((x for x in L["future"].get(w, {}).get(t, []) if x["pid"] == e["pid"]), None)
                es = fe["proj"] if fe else 0.0
                sl = (sleeper.get(w) or {}).get(k)
                if not has_game(L, e["pro"], w):
                    continue
                parts = {}
                if es > 0.3:
                    parts["espn"] = es
                    if sl is not None and sl > 0.3:
                        parts["sleeper"] = sl
                    if u and not u["stale"] and pos in (1, 2, 3, 4):
                        parts["usage"] = u["pts"] * (vm if w == W else 1.0)
                    tw = sum(wts.get(a, PRIOR.get(a, 0.2)) for a in parts)
                    m = sum(v * wts.get(a, PRIOR.get(a, 0.2)) for a, v in parts.items()) / tw
                    if sl is not None and sl <= 0.3:            # Sleeper expects him to sit
                        m *= 0.5
                elif sl is not None and sl > 0.3:               # ESPN expects him to sit
                    m = 0.5 * sl
                else:
                    m = 0.0
                if w == W and m > 0:
                    lines = (X.get("props") or {}).get(e["pid"])
                    pp = props_points(pos, lines, u["comps"] if u else None, vm) if lines else None
                    if pp is not None and pp > 0:
                        parts["props"] = pp
                        m = (1 - PROPS_WEIGHT) * m + PROPS_WEIGHT * pp
                    src = {a: round(v, 1) for a, v in parts.items()}
                mean[w] = m * cal.get(pos, .95)
            out.append(dict(e, team=t, mean=mean, play_prob=C.PLAY_PROB.get(e["inj"], 1.0), sources=src,
                            vol=(X.get("vol") or {}).get(e["pid"], 1.0)))
    return out


def players_backfill(L, W, cal):
    """Rosters as they stood in week W. Old rest-of-season projections are not archived, so each player's
    week-W projection stands in for the rest of the season (zero on byes)."""
    def past_projs(pid, lo, hi):
        v = []
        for w in range(hi, lo - 1, -1):
            for ents in L["box"].get(w, {}).values():
                for x in ents:
                    if x["pid"] == pid and x["proj"] > 0:
                        v.append(x["proj"])
        return v
    out = []
    for t, ents in L["box"].get(W, {}).items():
        for e in ents:
            if e["pos"] not in C.POS:
                continue
            level, back = e["proj"], W
            if level <= 0:
                prev = past_projs(e["pid"], max(1, W - 3), W - 1)
                if not has_game(L, e["pro"], W):       # bye week: use his last projection
                    level = prev[0] if prev else 0.0
                else:                                  # hurt: half his recent level, back in two weeks
                    level, back = (0.5 * sum(prev) / len(prev) if prev else 0.0), W + 2
            mean = np.zeros(C.LAST_WEEK + 2)
            for w in range(W, C.LAST_WEEK + 1):
                if w >= back and has_game(L, e["pro"], w):
                    mean[w] = level * cal.get(e["pos"], .95)
            out.append(dict(e, team=t, mean=mean, play_prob=1.0, sources={}, vol=1.0))
    return out


def _slot_counts(slots):
    n = {p: 0 for p in C.POS}
    for s, c in slots.items():
        if s in C.SLOT_POS:
            n[C.SLOT_POS[s]] += c
    return n, slots.get(C.FLEX_SLOT, 0)


def simulate(L, W, players, frm, n_sims, seed=0):
    rng = np.random.default_rng(seed)
    T = sorted(L["teams"]); ti = {t: i for i, t in enumerate(T)}; nT = len(T)
    N, P = n_sims, len(players)
    reg, last = L["reg_weeks"], C.LAST_WEEK
    npos, nflex = _slot_counts(L["slots"])
    pos = np.array([p["pos"] for p in players]); pro = np.array([p["pro"] for p in players])
    team = np.array([ti[p["team"]] for p in players])
    vol = np.array([p.get("vol", 1.0) for p in players])
    mean = np.stack([p["mean"] for p in players]) if P else np.zeros((0, last + 2))
    sig = {k: math.sqrt(math.log(1 + v * v)) for k, v in C.CV.items()}
    tal = (C.TALENT0 * rng.standard_normal((N, P))).astype(np.float32)
    out_until = np.zeros((N, P), dtype=np.int16)
    dur_v = np.array([d for d, _ in C.INJ_DURATIONS]); dur_p = np.array([p for _, p in C.INJ_DURATIONS])
    haz = np.array([C.HAZARD.get(int(x), 0) for x in pos])
    max_pro = max([35] + list(L["pro"])) + 1

    scores = np.zeros((last + 2, N, nT), dtype=np.float32)
    for g in L["games"]:                       # weeks already played
        if g["week"] < W and g["week"] <= last:
            scores[g["week"], :, ti[g["home"]]] = g["hs"]
            if g["away"] is not None:
                scores[g["week"], :, ti[g["away"]]] = g["as"]

    for w in range(W, last + 1):
        O = rng.standard_normal((N, max_pro)).astype(np.float32)
        mw = mean[:, w]
        avail = (out_until < w) & (mw > 0)[None, :]
        if w == W:
            pp = np.array([p["play_prob"] for p in players])
            if (pp < 1).any():
                avail &= rng.random((N, P)) < pp[None, :]
        var_t = C.TALENT0 ** 2 + C.DRIFT ** 2 * (w - W)
        for t in range(nT):
            idx = [i for i in np.where(team == t)[0] if mw[i] > 0]
            cands = [(mw[i], int(pos[i]), i) for i in idx]
            for p_, c in npos.items():
                cands += [(C.REPLACEMENT[p_], p_, -1)] * c
            cands += [(C.REPLACEMENT[2], 2, -1), (C.REPLACEMENT[3], 3, -1)][:nflex]
            cands.sort(key=lambda x: -x[0])
            cnt = {p_: np.zeros(N, dtype=np.int8) for p_ in npos}
            flex = np.zeros(N, dtype=np.int8)
            tot = np.zeros(N, dtype=np.float32)
            for m, p_, i in cands:
                av = avail[:, i] if i >= 0 else np.ones(N, dtype=bool)
                take = av & (cnt[p_] < npos[p_])
                cnt[p_] += take
                if p_ in C.FLEX_POS and nflex:
                    tf = av & ~take & (flex < nflex)
                    flex += tf
                    take = take | tf
                if not take.any():
                    continue
                a = C.LOAD[p_]
                e = rng.standard_normal(N).astype(np.float32)
                if p_ == 16:
                    opp = L["pro"].get(int(pro[i]), {}).get("opp", {}).get(w, 0) if i >= 0 else 0
                    z = (-a * O[:, opp] if i >= 0 else 0) + (math.sqrt(1 - a * a) if i >= 0 else 1) * e
                    pts = m + C.DST_SD * z
                else:
                    z = a * O[:, int(pro[i])] + math.sqrt(1 - a * a) * e if i >= 0 else e
                    mm = m * np.exp(tal[:, i] - var_t / 2) if i >= 0 else m
                    sg = sig[p_] if i < 0 or vol[i] == 1.0 else math.sqrt(math.log(1 + (C.CV[p_] * vol[i]) ** 2))
                    pts = mm * np.exp(sg * z - sg ** 2 / 2)
                tot += np.where(take, pts, 0)
            scores[w, :, t] = tot + frm.get(T[t], 0.0) + C.TEAM_SD * rng.standard_normal(N)
        played = avail & (haz > 0)[None, :]
        hurt = played & (rng.random((N, P)) < haz[None, :])
        if hurt.any():
            d = rng.choice(dur_v, size=int(hurt.sum()), p=dur_p)
            out_until[hurt] = np.minimum(w + d, 120)
        tal += (C.DRIFT * rng.standard_normal((N, P))).astype(np.float32)

    # regular season
    wins = np.zeros((N, nT)); pf = np.zeros((N, nT)); game_p = []
    for g in L["games"]:
        if g["away"] is None or g["week"] > last:
            continue
        h, a = ti[g["home"]], ti[g["away"]]
        sh, sa = scores[g["week"], :, h], scores[g["week"], :, a]
        if g["week"] <= reg:
            wins[:, h] += sh > sa; wins[:, a] += sa > sh
            wins[:, h] += 0.5 * (sh == sa); wins[:, a] += 0.5 * (sh == sa)
        if g["week"] >= W:
            game_p.append({"week": g["week"], "home": g["home"], "away": g["away"], "p_home": float((sh > sa).mean()),
                           "proj_home": float(sh.mean()), "proj_away": float(sa.mean())})
    for w in range(1, reg + 1):
        pf += scores[w]
    order = np.argsort(-(wins * 1e6 + pf), axis=1)          # (N, nT) team index by seed
    rank = np.argsort(order, axis=1)                         # seed position of each team
    k = min(L["playoff_teams"], nT)
    ar = np.arange(N)
    alive = np.tile(np.arange(k), (N, 1))                    # seed positions still alive, sorted
    reach = {}                                               # teams alive when 4 / 2 / 1 remain
    wk = reg + 1
    while alive.shape[1] > 1:
        n_al = alive.shape[1]
        reach[n_al] = order[ar[:, None], alive]
        size = 1 << (n_al - 1).bit_length()
        byes = size - n_al
        nxt = [alive[:, i] for i in range(byes)]
        sc = scores[min(wk, last)]
        lo, hi = byes, n_al - 1
        while lo < hi:
            A, B = alive[:, lo], alive[:, hi]
            nxt.append(np.where(sc[ar, order[ar, A]] >= sc[ar, order[ar, B]], A, B))
            lo += 1; hi -= 1
        alive = np.sort(np.stack(nxt, axis=1), axis=1)
        wk += 1
    champ = order[ar, alive[:, 0]]

    def share(arr):
        return np.bincount(arr.ravel(), minlength=nT) / N
    semis, final = share(reach[4]) if 4 in reach else np.zeros(nT), share(reach[2]) if 2 in reach else np.zeros(nT)
    title = share(champ)
    res = {"teams": {}, "games": game_p}
    for t in T:
        i = ti[t]
        res["teams"][t] = {
            "playoffs": float((rank[:, i] < k).mean()), "bye": float((rank[:, i] == 0).mean()),
            "semis": float(semis[i]), "final": float(final[i]), "title": float(title[i]),
            "exp_wins": float(wins[:, i].mean()), "exp_pf": float(pf[:, i].mean()),
            "seed_dist": [round(float(x), 4) for x in np.bincount(rank[:, i], minlength=nT) / N],
        }
    if W <= last:
        s = scores[W]
        q = np.percentile(s, [10, 50, 90], axis=0)
        res["week_scores"] = {t: {"mean": float(s[:, ti[t]].mean()), "p10": float(q[0, ti[t]]), "p50": float(q[1, ti[t]]),
                                  "p90": float(q[2, ti[t]])} for t in T}
        res["h2h"] = {t: {u: (None if t == u else round(float((s[:, ti[t]] > s[:, ti[u]]).mean()), 4)) for u in T} for t in T}
    return res


BOOM = {1: 25, 2: 20, 3: 20, 4: 15, 5: 12, 16: 12}     # a week that usually lands in the position's top tier
BUST = {1: 12, 2: 7, 3: 7, 4: 5, 5: 5, 16: 2}


def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def player_outlook(L, W, players, X=None):
    """Per-player rest-of-season outlook for the site."""
    X = X or {}
    dvp, trends = X.get("dvp") or {}, X.get("trends") or {}
    rows = []
    for p in players:
        pos = p["pos"]
        wk = [round(float(p["mean"][w]), 1) for w in range(W, C.LAST_WEEK + 1)]
        games = [x for x in wk if x > 0]
        m = float(p["mean"][W]) if W <= C.LAST_WEEK else 0.0
        boom = bust = None
        if pos == 16:
            sd = C.DST_SD
            lo, hi = m - Z10 * sd, m + Z10 * sd
            if m > 0:
                boom, bust = 1 - _ncdf((BOOM[pos] - m) / sd), _ncdf((BUST[pos] - m) / sd)
        else:
            s = math.sqrt(math.log(1 + (C.CV[pos] * p.get("vol", 1.0)) ** 2) + C.TALENT0 ** 2)
            lo, hi = m * math.exp(-Z10 * s - s * s / 2), m * math.exp(Z10 * s - s * s / 2)
            if m > 0:
                z = lambda x: (math.log(x / m) + s * s / 2) / s
                boom, bust = 1 - _ncdf(z(BOOM[pos])), _ncdf(z(BUST[pos]))
        pr = L["pro"].get(p["pro"], {})
        opps, sos = [], []
        for w in range(W, C.LAST_WEEK + 1):
            o = pr.get("opp", {}).get(w)
            oa = L["pro"].get(o, {}).get("abbrev") if o else None
            opps.append(oa)
            if oa and (oa, pos) in dvp:
                sos.append(dvp[(oa, pos)])
        tr = trends.get(p["pid"]) or {}
        rows.append({
            "id": p["pid"], "name": p["name"], "pos": C.POS[pos], "nfl": pr.get("abbrev", "FA"), "team": p["team"],
            "slot": "IR" if p["slot"] == C.IR_SLOT else "", "status": p["inj"] if p["inj"] not in ("ACTIVE", "NORMAL") else "",
            "bye": pr.get("bye"), "opp": opps[0] if opps else None, "opps": opps,
            "wk": round(m, 1), "floor": round(max(lo, 0) if pos != 16 else lo, 1) if m > 0 else 0, "ceil": round(hi, 1) if m > 0 else 0,
            "boom": None if boom is None else round(boom, 3), "bust": None if bust is None else round(bust, 3),
            "vol": round(p.get("vol", 1.0), 2), "src": p.get("sources") or {},
            "sos": round(sum(sos) / len(sos), 3) if sos else None,
            "matchup": round(dvp.get((opps[0], pos), 1.0), 3) if opps and opps[0] and (opps[0], pos) in dvp else None,
            "snap": None if tr.get("snap") is None else round(tr["snap"], 2),
            "snap_delta": None if tr.get("snap_delta") is None else round(tr["snap_delta"], 2),
            "tgt": None if tr.get("tgt") is None else round(tr["tgt"], 3),
            "tgt_delta": None if tr.get("tgt_delta") is None else round(tr["tgt_delta"], 3),
            "ros_avg": round(sum(games) / len(games), 1) if games else 0.0, "ros_total": round(sum(wk), 1),
            "ros_games": len(games), "weeks": wk, "season_pts": p.get("season_pts"),
        })
    for pos in set(r["pos"] for r in rows):
        grp = sorted([r for r in rows if r["pos"] == pos], key=lambda r: -r["ros_total"])
        for i, r in enumerate(grp):
            r["pos_rank"] = i + 1
    return rows
