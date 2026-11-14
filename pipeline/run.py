"""Update the site data: python -m pipeline.run [--rebuild] [--fixtures DIR] [--no-sleeper]"""
import argparse, datetime, json, os, sys
from . import config as C
from .espn import Espn, load_league, EspnError
from . import model, sleeper as sl

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data")


def standings(L, W):
    rec = {t: {"w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0} for t in L["teams"]}
    for g in L["games"]:
        if g["week"] >= W or g["week"] > L["reg_weeks"] or g["away"] is None:
            continue
        h, a = rec[g["home"]], rec[g["away"]]
        h["pf"] += g["hs"]; h["pa"] += g["as"]; a["pf"] += g["as"]; a["pa"] += g["hs"]
        if g["hs"] > g["as"]:
            h["w"] += 1; a["l"] += 1
        elif g["hs"] < g["as"]:
            a["w"] += 1; h["l"] += 1
        else:
            h["t"] += 1; a["t"] += 1
    return rec


def snapshot(L, W, sleeper_proj, live, n_sims):
    cal = model.calibration(L, W)
    frm = model.form(L, W, cal, list(L["teams"]))
    if W > C.LAST_WEEK:
        players = []
    elif live:
        players = model.players_live(L, W, sleeper_proj, cal)
    else:
        players = model.players_backfill(L, W, cal)
    sim = model.simulate(L, W, players, frm, n_sims, seed=1000 + W)
    rec = standings(L, W)
    teams = {}
    for t, r in sim["teams"].items():
        teams[str(t)] = dict({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()},
                             w=rec[t]["w"], l=rec[t]["l"], t=rec[t]["t"], pf=round(rec[t]["pf"], 2), pa=round(rec[t]["pa"], 2),
                             form=round(frm[t], 1))
    return {"week": W, "teams": teams, "sim": sim, "players": players, "cal": cal}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="recompute every past week's snapshot")
    ap.add_argument("--fixtures", help="read ESPN responses from this folder instead of the network (tests)")
    ap.add_argument("--no-sleeper", action="store_true")
    ap.add_argument("--sims", type=int, default=C.N_SIMS)
    ap.add_argument("--out", default=DATA)
    ap.add_argument("--sample", action="store_true", help="mark the output as sample data")
    a = ap.parse_args(argv)

    api = Espn(C.LEAGUE_ID, C.SEASON, os.environ.get("ESPN_S2"), os.environ.get("ESPN_SWID"), a.fixtures)
    try:
        L = load_league(api, C.LAST_WEEK)
    except EspnError as e:
        print(f"ERROR: {e}", file=sys.stderr); return 2
    cur = L["current_week"]
    print(f"{L['name']} {L['season']}: current week {cur}, {len(L['teams'])} teams")
    weeks = list(range(cur, C.LAST_WEEK + 1))
    sproj = {} if (a.no_sleeper or a.fixtures) else sl.fetch(C.SEASON, weeks)
    used_sleeper = any(sproj.get(w) for w in weeks)

    os.makedirs(a.out, exist_ok=True)
    hpath = os.path.join(a.out, "history.json")
    hist = {"snapshots": []}
    if os.path.exists(hpath) and not a.rebuild:
        with open(hpath) as f:
            hist = json.load(f)
        if hist.get("sample") and not a.sample:   # never mix placeholder history into real data
            hist = {"snapshots": []}
    have = {s["week"]: s for s in hist.get("snapshots", [])}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    keep = ("playoffs", "bye", "semis", "final", "title", "exp_wins", "w", "l", "t", "pf", "pa")
    latest = None
    for W in range(1, min(cur, C.LAST_WEEK + 1) + 1):
        live = W == cur
        if not live and W in have:
            continue
        print(f"  simulating as of week {W} ({'live' if live else 'rebuilt'})")
        s = snapshot(L, W, sproj, live, a.sims)
        have[W] = {"week": W, "updated": now, "rebuilt": not live,
                   "teams": {t: {k: v[k] for k in keep} for t, v in s["teams"].items()}}
        if live:
            latest = s
    hist = {"sample": bool(a.sample), "snapshots": [have[w] for w in sorted(have)]}

    ids = sorted(L["teams"])
    teams_meta = {str(t): {"name": L["teams"][t]["name"], "abbrev": L["teams"][t]["abbrev"],
                           "color": C.TEAM_COLORS[i % len(C.TEAM_COLORS)]} for i, t in enumerate(ids)}
    W = latest["week"]
    out = {
        "league": {"name": L["name"], "season": L["season"], "id": L["league_id"], "reg_weeks": L["reg_weeks"],
                   "playoff_teams": L["playoff_teams"], "last_week": C.LAST_WEEK},
        "updated": now, "week": W, "sims": a.sims, "sample": bool(a.sample),
        "season_over": W > C.LAST_WEEK,
        "sources": ["ESPN"] + (["Sleeper"] if used_sleeper else []),
        "teams_meta": teams_meta, "teams": latest["teams"],
        "games": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in g.items()} for g in latest["sim"]["games"]],
        "results": [{"week": g["week"], "home": g["home"], "away": g["away"], "hs": g["hs"], "as": g["as"]}
                    for g in L["games"] if g["week"] < W and g["away"] is not None],
        "week_scores": {str(t): {k: round(v, 1) for k, v in d.items()} for t, d in latest["sim"].get("week_scores", {}).items()},
        "h2h": {str(t): {str(u): p for u, p in d.items()} for t, d in latest["sim"].get("h2h", {}).items()},
        "players": model.player_outlook(L, W, latest["players"]),
    }
    with open(os.path.join(a.out, "latest.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    with open(hpath, "w") as f:
        json.dump(hist, f, separators=(",", ":"))
    top = sorted(latest["teams"].items(), key=lambda kv: -kv[1]["title"])[:3]
    print("  title favorites: " + ", ".join(f"{teams_meta[t]['name']} {v['title']:.1%}" for t, v in top))
    print(f"wrote {a.out}/latest.json and history.json ({len(hist['snapshots'])} weekly snapshots)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
