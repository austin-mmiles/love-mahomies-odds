"""Advanced stats layer built on nflverse data (public, no login).

What it adds to the site's projections:
  * a usage-based projection for every QB/RB/WR/TE, driven by recent opportunity (attempts, carries, targets)
    with efficiency and touchdown rates regressed toward position norms, so hot and cold streaks are discounted;
  * defense-vs-position strength of schedule for every remaining week;
  * each player's own boom/bust volatility from his game log;
  * usage trends (snap share and target share, recent vs earlier).
Every "as of" function only uses games before the given week, so backtests have no hindsight.
"""
import io, os, urllib.request
import numpy as np
import pandas as pd

REL = "https://github.com/nflverse/nflverse-data/releases/download"
FILES = {
    "cur": "stats_player/stats_player_week_{season}.csv",
    "prev": "stats_player/stats_player_week_{prev}.csv",
    "players": "players/players.csv",
    "snaps": "snap_counts/snap_counts_{season}.csv",
}
TEAM_FIX = {"LA": "LAR", "WAS": "WSH"}          # nflverse -> ESPN abbreviations
POS_ID = {"QB": 1, "RB": 2, "WR": 3, "TE": 4}
HALF_LIFE = 4.0                                   # games; recent games count more
# regression strength: how many opportunities of league-average performance are mixed in
K = {"ypa": 150, "ptd": 200, "int": 250, "ypc": 60, "rtd": 80, "rfd": 60, "catch": 30, "ypt": 50, "rectd": 80}
DVP_K = 4.0                                       # games of league-average defense mixed in
DVP_WEIGHT, DVP_CLIP = 0.6, (0.80, 1.22)


def _read(name, season, cache):
    rel = FILES[name].format(season=season, prev=season - 1)
    if cache:
        p = os.path.join(cache, os.path.basename(rel))
        if os.path.exists(p):
            return pd.read_csv(p, low_memory=False)
    req = urllib.request.Request(f"{REL}/{rel}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    if cache:
        os.makedirs(cache, exist_ok=True)
        with open(os.path.join(cache, os.path.basename(rel)), "wb") as f:
            f.write(raw)
    return pd.read_csv(io.BytesIO(raw), low_memory=False)


def league_points(d):
    """League scoring from raw box-score stats (skill positions)."""
    g = lambda c: d[c].fillna(0) if c in d else 0
    return (.04 * g("passing_yards") + 4 * g("passing_tds") - 2 * g("passing_interceptions") + 2 * g("passing_2pt_conversions")
            + .1 * g("rushing_yards") + 6 * g("rushing_tds") + 2 * g("rushing_2pt_conversions") + .5 * g("rushing_first_downs")
            + g("receptions") + .1 * g("receiving_yards") + 6 * g("receiving_tds") + 2 * g("receiving_2pt_conversions")
            - 2 * (g("sack_fumbles_lost") + g("rushing_fumbles_lost") + g("receiving_fumbles_lost")) + 6 * g("special_teams_tds"))


def points_from(c):
    """League points from expected stat components."""
    return (.04 * c["pass_yd"] + 4 * c["pass_td"] - 2 * c["int"] + .1 * c["rush_yd"] + 6 * c["rush_td"] + .5 * c["rush_fd"]
            + c["rec"] + .1 * c["rec_yd"] + 6 * c["rec_td"])


class Advanced:
    def __init__(self, season, cache=None, log=print):
        self.season, self.ok = season, False
        try:
            cur = _read("cur", season, cache)
            players = _read("players", season, cache)
        except Exception as e:
            log(f"  nflverse data unavailable ({e}); advanced stats skipped")
            return
        try:
            prev = _read("prev", season, cache)
        except Exception:
            prev = cur.iloc[0:0]
        try:
            snaps = _read("snaps", season, cache)
        except Exception:
            snaps = None
        ids = players[["gsis_id", "pfr_id", "espn_id"]].dropna(subset=["espn_id"])
        ids = ids.assign(espn_id=pd.to_numeric(ids["espn_id"], errors="coerce")).dropna(subset=["espn_id"])
        ids["espn_id"] = ids["espn_id"].astype(int)
        self.logs = self._prep(cur, ids)
        self.prev = self._prep(prev, ids) if len(prev) else self.logs.iloc[0:0]
        self.snaps = None
        if snaps is not None and len(snaps):
            s = snaps[snaps["game_type"] == "REG"].merge(ids[["pfr_id", "espn_id"]], left_on="pfr_player_id", right_on="pfr_id")
            self.snaps = s[["espn_id", "week", "offense_pct"]]
        self.max_week = int(self.logs["week"].max()) if len(self.logs) else 0
        self.ok = len(self.logs) > 0

    @staticmethod
    def _prep(df, ids):
        d = df[(df["season_type"] == "REG") & (df["position"].isin(list(POS_ID)))].copy()
        d = d.merge(ids[["gsis_id", "espn_id"]], left_on="player_id", right_on="gsis_id", how="inner")
        d["team"] = d["team"].replace(TEAM_FIX); d["opp"] = d["opponent_team"].replace(TEAM_FIX)
        d["pts"] = league_points(d)
        for c in ("attempts", "carries", "targets", "passing_yards", "passing_tds", "passing_interceptions", "rushing_yards",
                  "rushing_tds", "rushing_first_downs", "receptions", "receiving_yards", "receiving_tds", "target_share",
                  "receiving_air_yards", "air_yards_share"):
            d[c] = pd.to_numeric(d.get(c, 0), errors="coerce").fillna(0)
        d["opps"] = d["attempts"] + d["carries"] + d["targets"]
        return d

    # ---------- usage-based projection ----------
    def usage(self, asof):
        """{espn_id: neutral-matchup projected points} from games before week `asof`."""
        d = self.logs[(self.logs["week"] < asof) & (self.logs["opps"] > 0)]
        if d.empty:
            return {}
        rate = {}
        for pos, g in d.groupby("position"):                       # league rates by position
            s = g.sum(numeric_only=True)
            rate[pos] = {"ypa": s.passing_yards / max(s.attempts, 1), "ptd": s.passing_tds / max(s.attempts, 1),
                         "int": s.passing_interceptions / max(s.attempts, 1), "ypc": s.rushing_yards / max(s.carries, 1),
                         "rtd": s.rushing_tds / max(s.carries, 1), "rfd": s.rushing_first_downs / max(s.carries, 1),
                         "catch": s.receptions / max(s.targets, 1), "ypt": s.receiving_yards / max(s.targets, 1),
                         "rectd": s.receiving_tds / max(s.targets, 1)}
        prev_pg = self.prev[self.prev["opps"] > 0].groupby("espn_id")[["attempts", "carries", "targets"]].agg(["mean", "size"]) \
            if len(self.prev) else None
        team_last = d.groupby("team")["week"].max()
        out = {}
        for pid, g in d.sort_values("week").groupby("espn_id"):
            pos = g["position"].iloc[-1]; r = rate[pos]
            n = len(g)
            w = 0.5 ** (np.arange(n - 1, -1, -1) / HALF_LIFE)
            vol = {c: float(np.average(g[c], weights=w)) for c in ("attempts", "carries", "targets")}
            wsum = float(w.sum())
            if prev_pg is not None and pid in prev_pg.index and prev_pg.loc[pid, ("carries", "size")] >= 4:   # last season as a weak prior
                pw = 1.5
                for c in vol:
                    vol[c] = (vol[c] * wsum + prev_pg.loc[pid, (c, "mean")] * pw) / (wsum + pw)
            elif n < 2:
                continue
            S = {c: float((g[c] * w).sum()) for c in ("attempts", "carries", "targets", "passing_yards", "passing_tds",
                                                      "passing_interceptions", "rushing_yards", "rushing_tds",
                                                      "rushing_first_downs", "receptions", "receiving_yards", "receiving_tds")}
            reg = lambda num, den, key: (S[num] + K[key] * r[key]) / (S[den] + K[key])
            c = {"pass_yd": vol["attempts"] * reg("passing_yards", "attempts", "ypa"),
                 "pass_td": vol["attempts"] * reg("passing_tds", "attempts", "ptd"),
                 "int": vol["attempts"] * reg("passing_interceptions", "attempts", "int"),
                 "rush_yd": vol["carries"] * reg("rushing_yards", "carries", "ypc"),
                 "rush_td": vol["carries"] * reg("rushing_tds", "carries", "rtd"),
                 "rush_fd": vol["carries"] * reg("rushing_first_downs", "carries", "rfd"),
                 "rec": vol["targets"] * reg("receptions", "targets", "catch"),
                 "rec_yd": vol["targets"] * reg("receiving_yards", "targets", "ypt"),
                 "rec_td": vol["targets"] * reg("receiving_tds", "targets", "rectd")}
            pts = points_from(c)
            team = g["team"].iloc[-1]
            stale = int(team_last.get(team, g["week"].iloc[-1])) - int(g["week"].iloc[-1]) >= 3   # has missed 3+ team weeks
            out[int(pid)] = {"pts": float(pts), "stale": bool(stale), "games": n, "team": team,
                             "comps": {k: float(v) for k, v in c.items()}, "raw_avg": float(g["pts"].mean()), "recent": float(np.average(g["pts"], weights=w))}
        return out

    # ---------- defense vs position ----------
    def dvp(self, asof):
        """{(defense ESPN abbrev, position id): multiplier}; above 1 means the defense gives up more than average."""
        d = self.logs[self.logs["week"] < asof]
        if d.empty:
            return {}
        g = d.groupby(["opp", "week", "position"])["pts"].sum().reset_index()
        out = {}
        for pos, gp in g.groupby("position"):
            avg = gp["pts"].mean()
            for team, gt in gp.groupby("opp"):
                ratio = (gt["pts"].sum() + DVP_K * avg) / (len(gt) + DVP_K) / avg
                out[(team, POS_ID[pos])] = float(np.clip(1 + DVP_WEIGHT * (ratio - 1), *DVP_CLIP))
        return out

    # ---------- boom / bust ----------
    def volatility(self):
        """{espn_id: multiplier on his position's usual week-to-week spread}, shrunk toward 1 for short logs."""
        d = pd.concat([self.prev, self.logs])
        d = d[d["opps"] >= 3]
        rows = []
        for (pid, season), g in d.groupby(["espn_id", "season"]):
            if len(g) >= 4 and g["pts"].mean() >= 5:
                rows.append((pid, g["position"].iloc[-1], len(g), g["pts"].var(ddof=1) / g["pts"].mean() ** 2))
        if not rows:
            return {}
        r = pd.DataFrame(rows, columns=["pid", "pos", "n", "cv2"])
        agg = r.groupby("pid").apply(lambda x: pd.Series({"pos": x["pos"].iloc[-1], "n": x["n"].sum(),
                                                          "cv": np.sqrt(np.average(x["cv2"], weights=x["n"] - 1))}), include_groups=False)
        out = {}
        for pos, g in agg.groupby("pos"):
            m = g["cv"].mean(); se2 = (g["cv"] ** 2 / (2 * (g["n"] - 1))).mean()
            tau2 = max(0.0, g["cv"].var(ddof=1) - se2) if len(g) > 2 else 0.0
            for pid, x in g.iterrows():
                wgt = tau2 / (tau2 + x["cv"] ** 2 / (2 * (x["n"] - 1))) if tau2 > 0 else 0.0
                out[int(pid)] = float(np.clip(1 + wgt * (x["cv"] / m - 1), 0.6, 1.5))
        return out

    # ---------- usage trends ----------
    def trends(self, asof):
        """{espn_id: {snap, snap_delta, tgt, tgt_delta}}: last two games vs the four before."""
        out = {}

        def split(g, col):
            v = g.sort_values("week")[col].to_numpy(dtype=float)
            if len(v) < 3:
                return (float(v[-2:].mean()) if len(v) else None), None
            return float(v[-2:].mean()), float(v[-2:].mean() - v[-6:-2].mean())
        if self.snaps is not None:
            for pid, g in self.snaps[self.snaps["week"] < asof].groupby("espn_id"):
                a, b = split(g, "offense_pct")
                out[int(pid)] = {"snap": a, "snap_delta": b}
        d = self.logs[(self.logs["week"] < asof) & (self.logs["position"] != "QB")]
        for pid, g in d.groupby("espn_id"):
            a, b = split(g, "target_share")
            out.setdefault(int(pid), {}).update({"tgt": a, "tgt_delta": b})
        return out

    # ---------- team offense level (for Vegas adjustments) ----------
    def offense(self, asof):
        """{team: fantasy points per game by its QB/RB/WR/TE, relative to the league average}."""
        d = self.logs[self.logs["week"] < asof]
        if d.empty:
            return {}
        g = d.groupby(["team", "week"])["pts"].sum().groupby("team").mean()
        return (g / g.mean()).to_dict()
