"""Builds sample ESPN-format responses for testing: python tests/make_fixtures.py OUT_DIR [CURRENT_WEEK]
Team names, Weeks 1-7 scores and the Weeks 8-14 schedule are the league's real ones (as of Oct 28, 2026).
Players are invented ("Sample RB 3") and later weeks' scores are random."""
import json, os, random, sys

out = sys.argv[1]; CUR = int(sys.argv[2]) if len(sys.argv) > 2 else 8
os.makedirs(out, exist_ok=True)
rnd = random.Random(7)
SEASON = 2026
TEAMS = {1: ("First Down Syndrome", "DOWN"), 2: ("Bear Market", "RONQ"), 3: ("Wide Deceivers", "SF"), 4: ("ETN the booty", "JH"),
         5: ("Rome Alone", "PNCE"), 6: ("FOURVERTS HURTS", "BLOW"), 7: ("Kyle Pittenhouse", "KPH"), 8: ("Dak Shots", "SETh"),
         9: ("Tuten and Boot It", "PURR"), 10: ("George Picken Cotton", "GP"), 11: ("Touch Mike Hawk", "CHAV"), 12: ("Bucking Maye", "BKM")}
STRENGTH = {1: 144, 2: 131, 3: 131, 4: 129, 5: 128, 6: 122, 7: 108, 8: 97, 9: 126, 10: 124, 11: 118, 12: 134}
# (week, home, home pts, away, away pts)
PLAYED = [(1,10,100.32,6,92.26),(1,9,163.7,4,169.86),(1,7,90.96,1,135.96),(1,2,187.96,5,144.3),(1,12,99.52,11,127.76),(1,8,92.8,3,135.16),
 (2,6,123.38,4,88),(2,1,100.04,10,121.06),(2,5,92.56,9,109),(2,11,119.38,7,146.78),(2,3,111.52,2,138.52),(2,8,95.76,12,92.52),
 (3,1,139.74,6,98.44),(3,4,115.14,5,127.04),(3,10,133.78,11,136.04),(3,9,153,3,101.06),(3,7,123.24,8,100.84),(3,2,114.6,12,99.76),
 (4,6,119.88,5,166.68),(4,11,100.22,1,172.28),(4,3,151.42,4,122.08),(4,8,70.7,10,154.42),(4,12,150.82,9,97.08),(4,2,100.64,7,128.6),
 (5,11,125.6,6,114.16),(5,5,153.24,3,164.5),(5,1,133.68,8,44.14),(5,4,119.1,12,173.06),(5,10,125.46,2,112.24),(5,9,158.62,7,95.2),
 (6,6,111.88,3,116.2),(6,8,71.12,11,95.84),(6,12,125.5,5,123.04),(6,2,99.2,1,102.6),(6,7,105.48,4,101.72),(6,9,131.58,10,131.26),
 (7,8,71.52,6,124.5),(7,3,107.08,12,148.74),(7,11,86.86,2,118.02),(7,5,118.32,7,90.9),(7,1,134.72,9,82.4),(7,4,131.3,10,132.92)]
AHEAD = [(8,6,12),(8,2,8),(8,7,3),(8,9,11),(8,10,5),(8,4,1),(9,2,6),(9,12,7),(9,8,9),(9,3,10),(9,11,4),(9,5,1),(10,6,7),(10,9,2),
 (10,10,12),(10,4,8),(10,1,3),(10,5,11),(11,9,6),(11,7,10),(11,2,4),(11,12,1),(11,8,5),(11,3,11),(12,6,10),(12,4,9),(12,1,7),
 (12,5,2),(12,11,12),(12,3,8),(13,4,6),(13,10,1),(13,9,5),(13,7,11),(13,2,3),(13,12,8),(14,6,1),(14,5,4),(14,11,10),(14,3,9),(14,8,7),(14,12,2)]
PRO = list(range(1, 31)) + [33, 34]
ABBR = {1:"ATL",2:"BUF",3:"CHI",4:"CIN",5:"CLE",6:"DAL",7:"DEN",8:"DET",9:"GB",10:"TEN",11:"IND",12:"KC",13:"LV",14:"LAR",15:"MIA",16:"MIN",
        17:"NE",18:"NO",19:"NYG",20:"NYJ",21:"PHI",22:"ARI",23:"PIT",24:"LAC",25:"SF",26:"SEA",27:"TB",28:"WSH",29:"CAR",30:"JAX",33:"BAL",34:"HOU"}
BYE = {1:11,2:7,3:10,4:6,5:11,6:14,7:10,8:6,9:11,10:9,11:13,12:5,13:13,14:11,15:6,16:6,17:11,18:8,19:8,20:13,21:10,22:14,23:9,24:7,
       25:8,26:11,27:10,28:7,29:5,30:7,33:13,34:8}
# pro schedule: random pairings each week among teams not on bye
pro_games = {p: {} for p in PRO}
for w in range(1, 19):
    act = [p for p in PRO if BYE[p] != w]; rnd.shuffle(act)
    for i in range(0, len(act) - 1, 2):
        h, a = act[i], act[i + 1]
        pro_games[h][w] = pro_games[a][w] = [{"homeProTeamId": h, "awayProTeamId": a}]
json.dump({"settings": {"proTeams": [{"id": 0, "abbrev": "FA"}] + [{"id": p, "abbrev": ABBR[p], "byeWeek": BYE[p],
          "proGamesByScoringPeriod": {str(w): g for w, g in pro_games[p].items()}} for p in PRO]}},
          open(f"{out}/season_proTeamSchedules_wl_0.json", "w"))

# rosters: QB x2, RB x5, WR x5, TE x2, K, DST per team + one IR player
BASE = {1: [19, 15], 2: [19, 15, 11, 8, 6], 3: [18, 14, 11, 8, 6], 4: [11, 7], 5: [9], 16: [6.5]}
PN = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
pid = 1000; roster = {}
for t in TEAMS:
    k = STRENGTH[t] / 127.0; lst = []
    for pos, lv in BASE.items():
        for i, v in enumerate(lv):
            pid += 1
            pro = rnd.choice(PRO)
            lst.append({"id": pid if pos != 16 else -16000 - pro, "name": f"Sample {PN[pos]} {pid - 1000}" if pos != 16 else f"{ABBR[pro]} D/ST",
                        "pos": pos, "pro": pro, "lvl": v * (k if pos in (1, 2, 3, 4) else 1) * rnd.uniform(.9, 1.1), "inj": "ACTIVE"})
    lst[4]["inj"] = rnd.choice(["ACTIVE", "QUESTIONABLE", "ACTIVE"])
    pid += 1
    lst.append({"id": pid, "name": f"Sample RB {pid - 1000}", "pos": 2, "pro": rnd.choice(PRO), "lvl": 12, "inj": "INJURY_RESERVE", "ret": CUR + 2})
    roster[t] = lst

def proj(p, w):
    if BYE[p["pro"]] == w or (p.get("ret") and w < p["ret"]):
        return 0.0
    r = random.Random(p["id"] * 100 + w)
    return round(p["lvl"] * r.uniform(.88, 1.12), 2)

def lineup(t, w):
    ps = sorted(roster[t], key=lambda p: -proj(p, w)); slots = {}; cnt = {1: 0, 2: 0, 3: 0, 5: 0, 16: 0}; flex = 0
    cap = {1: 1, 2: 2, 3: 2, 5: 1, 16: 1}; sid = {1: 0, 2: 2, 3: 4, 5: 17, 16: 16}
    for p in ps:
        if p["inj"] == "INJURY_RESERVE": slots[p["id"]] = 21
        elif p["pos"] in cap and cnt[p["pos"]] < cap[p["pos"]] and proj(p, w) > 0: cnt[p["pos"]] += 1; slots[p["id"]] = sid[p["pos"]]
        elif p["pos"] in (2, 3, 4) and flex < 2 and proj(p, w) > 0: flex += 1; slots[p["id"]] = 23
        else: slots[p["id"]] = 20
    return slots

def entries(t, w, total=None, played=True):
    sl = lineup(t, w); raw = {}
    for p in roster[t]:
        pj = proj(p, w); r = random.Random(p["id"] * 7 + w)
        raw[p["id"]] = max(-2.0, r.lognormvariate(0, .5) * pj * .9) if (played and pj > 0) else 0.0
    if total is not None:
        st = sum(v for i, v in raw.items() if sl[i] not in (20, 21)) or 1
        raw = {i: v * total / st if sl[i] not in (20, 21) else v for i, v in raw.items()}
    ents = []
    for p in roster[t]:
        stats = [{"seasonId": SEASON, "statSourceId": 1, "statSplitTypeId": 1, "scoringPeriodId": w, "appliedTotal": proj(p, w)},
                 {"seasonId": SEASON, "statSourceId": 0, "statSplitTypeId": 0, "scoringPeriodId": 0, "appliedTotal": round(p["lvl"] * .93 * (CUR - 1), 1)},
                 {"seasonId": SEASON - 1, "statSourceId": 1, "statSplitTypeId": 1, "scoringPeriodId": w, "appliedTotal": 99}]
        ents.append({"lineupSlotId": sl[p["id"]], "playerId": p["id"], "playerPoolEntry": {"appliedStatTotal": round(raw[p["id"]], 2),
                     "player": {"id": p["id"], "fullName": p["name"], "defaultPositionId": p["pos"], "proTeamId": p["pro"],
                                "injuryStatus": p["inj"], "injured": p["inj"] != "ACTIVE", "stats": stats}}})
    return ents

games = [(w, h, hs, a, as_) for w, h, hs, a, as_ in PLAYED]
for w, h, a in AHEAD:
    if w < CUR:
        games.append((w, h, round(rnd.gauss(STRENGTH[h] * .93, 24), 2), a, round(rnd.gauss(STRENGTH[a] * .93, 24), 2)))
    else:
        games.append((w, h, 0, a, 0))
def sched(with_box=None):
    s = []
    for i, (w, h, hs, a, as_) in enumerate(games):
        m = {"id": i + 1, "matchupPeriodId": w, "winner": ("UNDECIDED" if w >= CUR else ("HOME" if hs > as_ else "AWAY")),
             "playoffTierType": "NONE", "home": {"teamId": h, "totalPoints": hs}, "away": {"teamId": a, "totalPoints": as_}}
        if with_box == w:
            m["home"]["rosterForCurrentScoringPeriod"] = {"entries": entries(h, w, hs if w < CUR else None, w < CUR)}
            m["away"]["rosterForCurrentScoringPeriod"] = {"entries": entries(a, w, as_ if w < CUR else None, w < CUR)}
        s.append(m)
    return s
teams = [{"id": t, "name": n, "abbrev": ab, "playoffSeed": 0} for t, (n, ab) in TEAMS.items()]
json.dump({"status": {"currentMatchupPeriod": CUR, "latestScoringPeriod": CUR, "finalScoringPeriod": 17},
           "settings": {"name": "Love Mahomies", "scheduleSettings": {"matchupPeriodCount": 14, "playoffTeamCount": 7,
                        "playoffSeedingRule": "TOTAL_POINTS_SCORED"},
                        "rosterSettings": {"lineupSlotCounts": {"0": 1, "2": 2, "4": 2, "6": 0, "16": 1, "17": 1, "20": 7, "21": 1, "23": 2}}},
           "teams": teams, "schedule": sched()}, open(f"{out}/league_mSettings+mStatus+mTeam+mMatchupScore_0.json", "w"))
for w in range(1, CUR + 1):
    json.dump({"schedule": sched(w)}, open(f"{out}/league_mMatchupScore+mBoxscore_{w}.json", "w"))
for w in range(CUR, 18):
    json.dump({"teams": [{"id": t, "roster": {"entries": entries(t, w, None, False)}} for t in TEAMS]}, open(f"{out}/league_mRoster_{w}.json", "w"))
print("fixtures written to", out)
