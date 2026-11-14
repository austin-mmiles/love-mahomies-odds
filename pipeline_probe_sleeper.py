import json, urllib.request
URL = "https://api.sleeper.app/projections/nfl/2026/9?season_type=regular&position[]=RB&position[]=WR&position[]=QB&position[]=TE&position[]=K&position[]=DEF"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
rows = json.load(urllib.request.urlopen(req, timeout=40))
want = {"pass_yd","pass_td","pass_2pt","pass_int","rush_yd","rush_td","rush_2pt","rush_fd",
        "rec_yd","rec_td","rec_2pt","rec","fum_lost","pr_td","kr_td",
        "sack","int","fum_rec","safe","blk_kick","def_td","st_td","pts_allow","yds_allow",
        "fgm_0_19","fgm_20_29","fgm_30_39","fgm_40_49","fgm_50p","fgmiss","xpm",
        "fgmiss_0_19","fgmiss_20_29","fgmiss_30_39","fgmiss_40_49","fgmiss_50p","gp"}
seen = set()
samples = {}
for x in rows:
    pl = x.get("player") or {}
    pos = pl.get("position")
    s = x.get("stats") or {}
    seen |= set(s.keys())
    if pos == "RB" and s.get("rush_att",0) and "RB" not in samples:
        samples["RB"] = (pl.get("first_name",'')+' '+pl.get("last_name",'')), s
    if pos == "DEF" and "DEF" not in samples:
        samples["DEF"] = x.get("player_id"), s
    if pos == "K" and s.get("fga",0) and "K" not in samples:
        samples["K"] = (pl.get("first_name",'')+' '+pl.get("last_name",'')), s
missing = want - seen
print("rows:", len(rows))
print("MISSING from entire feed:", sorted(missing))
for p, (name, s) in samples.items():
    print(p, name, {k: s[k] for k in want if k in s})
