"""Sportsbook lines from ESPN's public odds feed (DraftKings): game totals and spreads, plus player props.
No login needed. Lines exist only for games that have not kicked off, so this covers the current week."""
import json, os, re, urllib.request

SB = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={season}&seasontype=2&week={week}"
PROPS = ("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{eid}/competitions/{cid}/odds/{pid}"
         "/propBets?lang=en&region=us&limit=1000&page={page}")
CODE = {"Total Passing Yards": "py", "Total Passing Touchdowns": "pt", "Total Passing Interceptions": "pi",
        "Total Rushing Yards": "ry", "Total Receiving Yards": "cy", "Total Receptions": "rc", "Total Kicking Points": "kp"}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def fetch_text(season, week):
    """Compact text: 'AWAY,HOME,total,home spread,state;...|espnId:py240.5,pt1.5;...'"""
    sb = _get(SB.format(season=season, week=week))
    games, props = [], {}
    for e in sb.get("events", []):
        c = e["competitions"][0]
        o = (c.get("odds") or [None])[0]
        home = next(t for t in c["competitors"] if t["homeAway"] == "home")["team"]["abbreviation"]
        away = next(t for t in c["competitors"] if t["homeAway"] == "away")["team"]["abbreviation"]
        state = ((e.get("status") or {}).get("type") or {}).get("state", "")
        ou, sp = (o or {}).get("overUnder"), (o or {}).get("spread")
        games.append(f"{away},{home},{'' if ou is None else ou},{'' if sp is None else sp},{state}")
        pid = ((o or {}).get("provider") or {}).get("id")
        if not pid or state != "pre":
            continue
        page, pages = 1, 1
        while page <= pages:
            try:
                j = _get(PROPS.format(eid=e["id"], cid=c["id"], pid=pid, page=page))
            except Exception:
                break
            pages = j.get("pageCount") or 1
            for it in j.get("items") or []:
                k = CODE.get(((it.get("type") or {}).get("name") or "").replace(" (incl. overtime)", ""))
                m = re.search(r"athletes/(\d+)", (it.get("athlete") or {}).get("$ref", ""))
                v = ((it.get("current") or {}).get("target") or {}).get("value")
                if k and m and v is not None:
                    props.setdefault(m.group(1), {})[k] = v
            page += 1
    return ";".join(games) + "|" + ";".join(f"{i}:" + ",".join(f"{k}{v}" for k, v in d.items()) for i, d in props.items())


def parse(text):
    g, _, p = text.strip().partition("|")
    totals, games = {}, []
    for row in g.split(";"):
        f = row.split(",")
        if len(f) < 5:
            continue
        away, home, ou, sp, state = f[:5]
        games.append({"away": away, "home": home, "total": float(ou) if ou else None, "spread": float(sp) if sp else None, "state": state})
        if ou and sp and state == "pre":
            totals[home] = (float(ou) - float(sp)) / 2
            totals[away] = (float(ou) + float(sp)) / 2
    props = {}
    for row in p.split(";"):
        if ":" not in row:
            continue
        i, _, rest = row.partition(":")
        props[int(i)] = {x[:2]: float(x[2:]) for x in rest.split(",") if len(x) > 2}
    return {"games": games, "totals": totals, "props": props}


def load(season, week, archive_dir=None, cache_dir=None, log=print):
    """Fetch this week's lines (or read a cached copy), archive them, and return the parsed form."""
    text = None
    if cache_dir and os.path.exists(os.path.join(cache_dir, f"odds_{week}.txt")):
        text = open(os.path.join(cache_dir, f"odds_{week}.txt")).read()
    else:
        try:
            text = fetch_text(season, week)
        except Exception as e:
            log(f"  sportsbook lines unavailable ({e})")
    if not text:
        return {"games": [], "totals": {}, "props": {}}
    out = parse(text)
    if archive_dir and out["totals"]:          # keep each week's lines so they can be backtested later
        os.makedirs(archive_dir, exist_ok=True)
        with open(os.path.join(archive_dir, f"odds_{season}_{week}.txt"), "w") as f:
            f.write(text.strip() + "\n")
    return out
