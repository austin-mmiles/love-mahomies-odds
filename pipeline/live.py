"""In-week ("live") layer: which NFL games have kicked off or finished, taken from ESPN's public scoreboard.

The model uses it to lock in points already scored; the site uses it to lock betting while games are played.
Also the gate for the scheduled workflow:  python -m pipeline.live --need docs/data/latest.json
"""
import datetime, json, os, sys, urllib.request

SB = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
GAME_HOURS = 4.5          # if the scoreboard is unreachable, a game is treated as over this long after kickoff
REGULATION = 3600.0       # seconds


def _utc(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def now_utc(now=None):
    if isinstance(now, datetime.datetime):
        return now
    return _utc(now) if now else datetime.datetime.now(datetime.timezone.utc)


def fetch(season=None, week=None):
    """{'week': n, 'games': [{a, h, kick, state, left}]}; left = share of the game still to play (1 before kickoff)."""
    url = SB + (f"?dates={season}&seasontype=2&week={week}" if week else "")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.load(r)
    games = []
    for e in j.get("events", []):
        c = e["competitions"][0]
        side = {t["homeAway"]: t["team"]["abbreviation"].upper() for t in c["competitors"]}
        st = e.get("status") or {}
        state = (st.get("type") or {}).get("state") or "pre"
        period, clock = int(st.get("period") or 0), float(st.get("clock") or 0)
        if state == "pre":
            left = 1.0
        elif state == "post":
            left = 0.0
        else:
            left = max(0.02, min(1.0, 1 - ((min(period, 4) - 1) * 900 + (900 - min(clock, 900))) / REGULATION)) if period else 1.0
        games.append({"a": side.get("away"), "h": side.get("home"), "kick": e.get("date"), "state": state, "left": round(left, 3)})
    return {"week": int((j.get("week") or {}).get("number") or week or 0), "games": games}


def by_clock(games, now=None):
    """Fallback when the scoreboard cannot be read: infer each game's state from its kickoff time."""
    t, out = now_utc(now), []
    for g in games:
        hrs = (t - _utc(g["kick"])).total_seconds() / 3600 if g.get("kick") else -1
        state = "pre" if hrs < 0 else ("post" if g.get("state") == "post" or hrs >= GAME_HOURS else "in")
        out.append(dict(g, state=state, left={"pre": 1.0, "post": 0.0}.get(state, max(0.02, 1 - hrs / 3.2))))
    return out


def load(season, week, cache=None, prev=None, now=None, log=print):
    """This week's NFL games. cache = a saved scoreboard file (tests); prev = the games from the last published run."""
    try:
        if cache:
            with open(cache) as f:
                sb = json.load(f)
            sb = {"week": sb.get("week", week), "games": by_clock(sb["games"], now) if now else sb["games"]}
        else:
            sb = fetch(season, week)
        if sb["games"]:
            return sb["games"]
    except Exception as e:
        log(f"  NFL scoreboard unavailable ({e})")
    if prev and prev.get("week") == week and prev.get("games"):
        log("  using the last known kickoff times instead")
        return by_clock(prev["games"], now)
    return []


def team_states(games):
    """NFL team abbreviation -> its game this week."""
    out = {}
    for g in games:
        for ab in (g["a"], g["h"]):
            if ab:
                out[ab] = g
    return out


def need_run(latest_path, max_age_hours=3.0, now=None, sb=None, log=print):
    """Should the scheduled job recompute the odds now? Returns (bool, reason)."""
    t = now_utc(now)
    try:
        with open(latest_path) as f:
            D = json.load(f)
    except Exception:
        return True, "no published data yet"
    age = (t - _utc(D["updated"])).total_seconds() / 3600
    if D.get("season_over"):
        return age >= 24, "season over"
    if age >= max_age_hours:
        return True, f"last update was {age:.1f} hours ago"
    old = {(g["a"], g["h"]): g for g in (D.get("nfl") or {}).get("games", [])}
    try:
        sb = sb or fetch()
    except Exception as e:
        log(f"scoreboard unavailable ({e}); falling back to kickoff times")
        sb = {"week": D.get("week"), "games": by_clock(list(old.values()), t)}
    if sb.get("week") and sb["week"] != D.get("week"):
        return age >= 1.0, f"NFL week {sb['week']} has started (published week {D.get('week')})"
    for g in sb["games"]:
        o = old.get((g["a"], g["h"]))
        if g["state"] == "in":
            return True, f"{g['a']} at {g['h']} is being played"
        if o is None or o.get("state") != g["state"]:
            return True, f"{g['a']} at {g['h']} is now {g['state']}"
        if g["state"] == "pre" and g.get("kick") and _utc(g["kick"]) <= t:
            return True, f"{g['a']} at {g['h']} has kicked off"
    return False, f"nothing changed since the update {age:.1f} hours ago"


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--need":
        run, why = need_run(sys.argv[2])
        print(f"{'run' if run else 'skip'}: {why}")
        gh = os.environ.get("GITHUB_OUTPUT")
        if gh:
            with open(gh, "a") as f:
                f.write(f"run={'true' if run else 'false'}\n")
    else:
        print(json.dumps(fetch(), indent=1))
