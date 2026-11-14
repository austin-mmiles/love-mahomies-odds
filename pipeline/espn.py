"""Minimal ESPN Fantasy API client (read-only). Private leagues need the espn_s2 and SWID cookies."""
import json, os, urllib.request, urllib.error, time

BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"


class EspnError(RuntimeError):
    pass


class Espn:
    def __init__(self, league_id, season, s2=None, swid=None, fixtures=None):
        self.league_id, self.season, self.s2, self.swid, self.fixtures = league_id, season, s2, swid, fixtures

    def get(self, views, week=None, league=True):
        if self.fixtures:
            name = f"{'league' if league else 'season'}_{'+'.join(views)}_{week or 0}.json"
            with open(os.path.join(self.fixtures, name)) as f:
                return json.load(f)
        url = BASE.format(season=self.season)
        if league:
            url += f"/segments/0/leagues/{self.league_id}"
        url += "?" + "&".join(f"view={v}" for v in views)
        if week:
            url += f"&scoringPeriodId={week}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        if self.s2 and self.swid:
            req.add_header("Cookie", f"espn_s2={self.s2}; SWID={self.swid}")
        last = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise EspnError("ESPN refused the request (401/403). The espn_s2 / SWID cookies are missing, "
                                    "wrong or expired. Update the ESPN_S2 and ESPN_SWID repository secrets.") from e
                last = e
            except Exception as e:  # network hiccup
                last = e
            time.sleep(2 + 3 * attempt)
        raise EspnError(f"ESPN request failed: {last}")


def _stat(player, source, split, week):
    for s in player.get("stats") or []:
        if s.get("statSourceId") == source and s.get("statSplitTypeId") == split and s.get("scoringPeriodId") == week:
            return float(s.get("appliedTotal") or 0.0)
    return None


def _entry(e, week, season):
    ppe = e.get("playerPoolEntry") or {}
    p = ppe.get("player") or {}
    stats = [s for s in (p.get("stats") or []) if s.get("seasonId") == season]
    p = dict(p, stats=stats)
    return {
        "pid": p.get("id"), "name": p.get("fullName") or "?", "pos": p.get("defaultPositionId"),
        "pro": p.get("proTeamId") or 0, "slot": e.get("lineupSlotId"),
        "inj": p.get("injuryStatus") or ("" if not p.get("injured") else "OUT"),
        "proj": _stat(p, 1, 1, week) or 0.0,
        "act": float(ppe.get("appliedStatTotal") or 0.0),
        "season_pts": _stat(p, 0, 0, 0), "season_proj": _stat(p, 1, 0, 0),
    }


def load_league(api, last_week=17):
    """Fetch everything the model needs and return plain dicts."""
    core = api.get(["mSettings", "mStatus", "mTeam", "mMatchupScore"])
    st, ss = core["status"], core["settings"]
    sched = ss["scheduleSettings"]
    cur = int(st.get("currentMatchupPeriod") or 1)
    L = {
        "name": ss.get("name") or "League", "season": api.season, "league_id": api.league_id,
        "current_week": cur, "reg_weeks": int(sched["matchupPeriodCount"]),
        "playoff_teams": int(sched.get("playoffTeamCount") or 6),
        "slots": {int(k): int(v) for k, v in ss["rosterSettings"]["lineupSlotCounts"].items() if int(v) > 0},
        "teams": {}, "games": [], "box": {}, "future": {},
    }
    for t in core["teams"]:
        nm = (t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}").strip()
        L["teams"][t["id"]] = {"name": " ".join(nm.split()), "abbrev": t.get("abbrev") or "", "seed": t.get("playoffSeed")}
    for m in core["schedule"]:
        h, a = m.get("home"), m.get("away")
        if not h:
            continue
        w = int(m["matchupPeriodId"])
        L["games"].append({"week": w, "home": h["teamId"], "away": a["teamId"] if a else None,
                           "hs": float(h.get("totalPoints") or 0), "as": float(a.get("totalPoints") or 0) if a else None,
                           "done": w < cur})
    for w in range(1, min(cur, last_week) + 1):
        j = api.get(["mMatchupScore", "mBoxscore"], week=w)
        box = {}
        for m in j["schedule"]:
            if int(m["matchupPeriodId"]) != w:
                continue
            for side in ("home", "away"):
                t = m.get(side)
                if not t:
                    continue
                ents = (t.get("rosterForCurrentScoringPeriod") or {}).get("entries") or []
                box[t["teamId"]] = [_entry(e, w, api.season) for e in ents]
        L["box"][w] = box
    for w in range(cur, last_week + 1):
        j = api.get(["mRoster"], week=w)
        L["future"][w] = {t["id"]: [_entry(e, w, api.season) for e in (t.get("roster") or {}).get("entries") or []]
                          for t in j["teams"]}
    pro = api.get(["proTeamSchedules_wl"], league=False)
    L["pro"] = {}
    for t in pro["settings"]["proTeams"]:
        if t["id"] <= 0:
            continue
        opp = {}
        for sp, games in (t.get("proGamesByScoringPeriod") or {}).items():
            g = games[0]
            opp[int(sp)] = g["awayProTeamId"] if g["homeProTeamId"] == t["id"] else g["homeProTeamId"]
        L["pro"][t["id"]] = {"abbrev": t.get("abbrev", "").upper(), "bye": t.get("byeWeek"), "opp": opp}
    return L
