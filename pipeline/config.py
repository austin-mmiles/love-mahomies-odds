"""League and model settings. Edit LEAGUE_ID / SEASON to point at another league."""
import os

LEAGUE_ID = int(os.environ.get("ESPN_LEAGUE_ID", "97124817"))
SEASON = int(os.environ.get("ESPN_SEASON", "2026"))
N_SIMS = int(os.environ.get("N_SIMS", "20000"))
LAST_WEEK = 17  # last fantasy week (championship)

# ESPN ids
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
SLOT_POS = {0: 1, 2: 2, 4: 3, 6: 4, 16: 16, 17: 5}  # lineup slot -> position it requires
FLEX_SLOT, BENCH_SLOT, IR_SLOT = 23, 20, 21
FLEX_POS = (2, 3, 4)

# --- model constants (fitted on this league's 2026 results; see README) ---
CV = {1: 0.40, 2: 0.55, 3: 0.60, 4: 0.62, 5: 0.55}      # weekly score spread, as a share of projection
DST_SD = 5.2                                            # D/ST spread in points
LOAD = {1: 0.9, 2: 0.15, 3: 0.25, 4: 0.25, 5: 0.38, 16: 0.9}  # link to the NFL team's good/bad day
HAZARD = {1: 0.03, 2: 0.045, 3: 0.035, 4: 0.035, 5: 0.003, 16: 0.0}  # per-game injury chance
INJ_DURATIONS = [(1, .35), (2, .20), (3, .15), (5, .18), (99, .12)]
REPLACEMENT = {1: 15.5, 2: 8.0, 3: 8.0, 4: 8.0, 5: 8.5, 16: 6.0}  # typical free agent
TALENT0, DRIFT, TEAM_SD = 0.08, 0.035, 6.0
CAL_PRIOR = {1: 0.97, 2: 0.94, 3: 0.97, 4: 0.98, 5: 0.99, 16: 0.86}  # starters score this share of projection
CAL_PRIOR_PTS = 400.0
FORM_SHRINK_N = 23.0   # form weight = n / (n + 23)  (about 0.23 after 7 weeks)
PLAY_PROB = {"QUESTIONABLE": 0.85, "DOUBTFUL": 0.25, "OUT": 0.0, "INJURY_RESERVE": 0.0, "SUSPENSION": 0.0}
# ESPN / Sleeper blend for future weeks, by position (ESPN share)
ESPN_SHARE = {1: 0.60, 2: 0.55, 3: 0.325, 4: 0.75, 5: 0.25, 16: 0.30}

TEAM_COLORS = ["#1f77b4", "#d1495b", "#2a9d8f", "#e9a100", "#7b5ea7", "#3d405b",
               "#ef7b45", "#4c956c", "#c2185b", "#00798c", "#8d6e63", "#5c6bc0"]
