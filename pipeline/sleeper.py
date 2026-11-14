"""Sleeper (RotoWire) weekly projections, re-scored under this league's rules. Public API, no login."""
import json, math, re, urllib.request

URL = ("https://api.sleeper.app/projections/nfl/{season}/{week}?season_type=regular"
       "&position[]=QB&position[]=RB&position[]=WR&position[]=TE&position[]=K&position[]=DEF")
POS = {"QB": 1, "RB": 2, "WR": 3, "TE": 4, "K": 5, "DEF": 16}
ABBR_FIX = {"WSH": "WAS"}
PA = [(-1e9, .5, 5), (.5, 6.5, 4), (6.5, 13.5, 3), (13.5, 17.5, 1), (17.5, 27.5, 0), (27.5, 34.5, -1), (34.5, 45.5, -3), (45.5, 1e9, -5)]
YA = [(-1e9, 99.5, 5), (99.5, 199.5, 3), (199.5, 299.5, 2), (299.5, 349.5, 0), (349.5, 399.5, -1), (399.5, 449.5, -3),
      (449.5, 499.5, -5), (499.5, 549.5, -6), (549.5, 1e9, -7)]


def norm_name(s):
    s = re.sub(r"[.'’\-]", "", s.lower())
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return " ".join(s.split())


def key(name, pos, pro_abbrev):
    return f"DEF:{ABBR_FIX.get(pro_abbrev, pro_abbrev)}" if pos == 16 else f"{norm_name(name)}|{pos}"


def _phi(x, m, s):
    return 0.5 * (1 + math.erf((x - m) / (s * math.sqrt(2))))


def _band(m, s, edges):
    return sum(p * (_phi(hi, m, s) - _phi(lo, m, s)) for lo, hi, p in edges)


def score(pos, s):
    """League scoring: 4-pt pass TD, 0.04/pass yd, -2 INT, 6-pt rush/rec TD, PPR, 0.5/rush first down,
    distance field goals, D/ST points- and yards-allowed bands."""
    v = lambda k: float(s.get(k) or 0)
    if not s or not s.get("gp"):
        return 0.0
    if pos == "DEF":
        return (v("sack") + 2 * v("int") + 2 * v("fum_rec") + 2 * v("safe") + 2 * v("blk_kick")
                + 6 * (v("def_td") + v("st_td")) + _band(v("pts_allow"), 9.5, PA) + _band(v("yds_allow"), 70, YA))
    if pos == "K":
        miss = v("fgmiss") or sum(v(k) for k in ("fgmiss_0_19", "fgmiss_20_29", "fgmiss_30_39", "fgmiss_40_49", "fgmiss_50p"))
        return 3 * (v("fgm_0_19") + v("fgm_20_29") + v("fgm_30_39")) + 4 * v("fgm_40_49") + 5.1 * v("fgm_50p") - miss + v("xpm")
    return (.04 * v("pass_yd") + 4 * v("pass_td") + 2 * v("pass_2pt") - 2 * v("pass_int") + .1 * v("rush_yd") + 6 * v("rush_td")
            + 2 * v("rush_2pt") + .1 * v("rec_yd") + 6 * v("rec_td") + 2 * v("rec_2pt") + v("rec") - 2 * v("fum_lost")
            + .5 * v("rush_fd") + 6 * (v("pr_td") + v("kr_td")))


def fetch_week(season, week):
    req = urllib.request.Request(URL.format(season=season, week=week), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        rows = json.load(r)
    out = {}
    for x in rows:
        pl = x.get("player") or {}
        P = pl.get("position")
        if P not in POS:
            continue
        k = f"DEF:{x.get('player_id')}" if P == "DEF" else f"{norm_name((pl.get('first_name') or '') + ' ' + (pl.get('last_name') or ''))}|{POS[P]}"
        out[k] = score(P, x.get("stats") or {})
    return out


def fetch(season, weeks, log=print):
    """Returns {week: {key: points}}; an empty dict for any week that fails (the model then uses ESPN alone)."""
    out = {}
    for w in weeks:
        try:
            out[w] = fetch_week(season, w)
        except Exception as e:  # optional source
            log(f"  Sleeper week {w} unavailable ({e}); using ESPN only for that week")
            out[w] = {}
    return out
