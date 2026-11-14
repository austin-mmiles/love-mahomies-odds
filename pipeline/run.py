"""Update the site data: python -m pipeline.run [--rebuild] [--fixtures DIR] [--no-sleeper]"""
import argparse, datetime, json, os, sys
from . import config as C
from .espn import Espn, load_league, EspnError
from . import model, sleeper as sl, odds as oddsmod, blend, live as livemod
from .advanced import Advanced

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


def outcomes(L, W, teams):
    """Which futures markets are decided: {market: {team: true/false}}; a market is absent until its stage is over."""
    rounds = max(1, (min(L["playoff_teams"], len(L["teams"])) - 1).bit_length())
    done_after = {"playoffs": L["reg_weeks"], "bye": L["reg_weeks"], "final": L["reg_weeks"] + rounds - 1, "title": L["reg_weeks"] + rounds}
    out = {}
    for m, wk in done_after.items():
        if W > wk:
            out[m] = {t: v[m] >= 0.5 for t, v in teams.items()}
    return out


def snapshot(L, W, sleeper_proj, live, n_sims, X=None, nfl=None, week_closed=False):
    cal = model.calibration(L, W)
    frm = model.form(L, W, cal, list(L["teams"]))
    if W > C.LAST_WEEK:
        players = []
    elif live:
        players = model.players_live(L, W, sleeper_proj, cal, X, nfl)
    else:
        players = model.players_backfill(L, W, cal)
    sim = model.simulate(L, W, players, frm, n_sims, seed=1000 + W, week_closed=week_closed)
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
    ap.add_argument("--no-advanced", action="store_true", help="skip nflverse advanced stats")
    ap.add_argument("--no-odds", action="store_true", help="skip sportsbook lines")
    ap.add_argument("--nfl-cache", help="folder with nflverse CSVs (downloaded there if missing)")
    ap.add_argument("--odds-cache", help="folder with odds_<week>.txt files to use instead of fetching")
    ap.add_argument("--scoreboard", help="saved NFL scoreboard file to use instead of fetching (tests)")
    ap.add_argument("--now", help="pretend it is this UTC time, e.g. 2026-11-15T20:00Z (tests, with --scoreboard)")
    ap.add_argument("--no-live", action="store_true", help="ignore games in progress")
    a = ap.parse_args(argv)

    api = Espn(C.LEAGUE_ID, C.SEASON, os.environ.get("ESPN_S2"), os.environ.get("ESPN_SWID"), a.fixtures)
    try:
        L = load_league(api, C.LAST_WEEK)
    except EspnError as e:
        print(f"ERROR: {e}", file=sys.stderr); return 2
    cur = L["current_week"]
    print(f"{L['name']} {L['season']}: current week {cur}, {len(L['teams'])} teams")
    weeks = list(range(cur, C.LAST_WEEK + 1))
    sproj = {} if (a.no_sleeper or a.fixtures) else sl.fetch(C.SEASON, weeks, log=print)
    used_sleeper = any(sproj.get(w) for w in weeks)
    shist = {}
    if used_sleeper and cur > 3:                      # past weeks, to backtest Sleeper alongside the other sources
        shist = sl.fetch(C.SEASON, list(range(3, cur)))
    adv = None if a.no_advanced else Advanced(C.SEASON, cache=a.nfl_cache)
    lines = {} if (a.no_odds or cur > C.LAST_WEEK) else oddsmod.load(C.SEASON, cur, archive_dir=os.path.join(a.out, "lines"), cache_dir=a.odds_cache)
    X = blend.context(L, cur, adv, lines, shist) if cur <= C.LAST_WEEK else None
    if X:
        for pos, rep in X["report"]["by_pos"].items():
            print(f"  {pos}: weights {rep.get('weights')} rmse {rep.get('rmse')} (n={rep.get('n')})")

    os.makedirs(a.out, exist_ok=True)
    prev_nfl = None
    try:
        with open(os.path.join(a.out, "latest.json")) as f:
            prev_nfl = json.load(f).get("nfl")
    except Exception:
        pass
    nfl_games = []
    if cur <= C.LAST_WEEK and not a.no_live and (a.scoreboard or not a.fixtures):
        nfl_games = livemod.load(C.SEASON, cur, cache=a.scoreboard, prev=prev_nfl, now=a.now)
    started = [g for g in nfl_games if g["state"] != "pre"]
    if nfl_games:
        print(f"  NFL week {cur}: {sum(g['state'] == 'post' for g in nfl_games)} of {len(nfl_games)} games final, "
              f"{sum(g['state'] == 'in' for g in nfl_games)} in progress")
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
        s = snapshot(L, W, sproj, live, a.sims, X if live else None, livemod.team_states(nfl_games) if live else None,
                     week_closed=bool(live and nfl_games and all(g["state"] != "pre" for g in nfl_games)))
        if not (live and started and W in have):    # the weekly history point is the odds going into the week's games
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
        "sources": ["ESPN"] + (["Sleeper"] if used_sleeper else []) + (["nflverse usage model"] if X and X["report"]["advanced_stats"] else [])
                   + (["DraftKings lines"] if X and X["totals"] else []),
        "model": X["report"] if X else None,
        "teams_meta": teams_meta, "teams": latest["teams"],
        "games": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in g.items()} for g in latest["sim"]["games"]],
        "results": [{"week": g["week"], "home": g["home"], "away": g["away"], "hs": g["hs"], "as": g["as"]}
                    for g in L["games"] if g["week"] < W and g["away"] is not None],
        "week_scores": {str(t): {k: (round(v, 1) if isinstance(v, float) else v) for k, v in d.items()} for t, d in latest["sim"].get("week_scores", {}).items()},
        "h2h": {str(t): {str(u): p for u, p in d.items()} for t, d in latest["sim"].get("h2h", {}).items()},
        "players": model.player_outlook(L, W, latest["players"], X),
        "outcomes": outcomes(L, W, latest["teams"]),
        # this week's NFL games: the site locks betting while any has kicked off and is not yet final here
        "nfl": {"week": W, "games": [{k: g[k] for k in ("a", "h", "kick", "state")} for g in nfl_games]} if nfl_games else None,
        # actual fantasy points for rostered players in recent finished weeks (settles player-prop bets)
        "player_points": {str(w): {str(e["pid"]): round(e["act"], 2) for ents in L["box"].get(w, {}).values() for e in ents}
                          for w in range(max(1, W - 4), W) if w in L["box"]},
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
