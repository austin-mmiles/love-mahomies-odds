# Love Mahomies Odds Board: project brief

Sportsbook-style site for Austin's 12-team ESPN fantasy league "Love Mahomies" (league 97124817, season 2026).
Live at https://austin-mmiles.github.io/love-mahomies-odds/ and served from `docs/` on `main` by GitHub Pages.

## What it does

- **Board**: every team's playoff, #1 seed, final and title odds, with week-over-week history.
- **Sportsbook**: paper-trading bets on futures, weekly games, team totals and player props, with parlays.
- **Playoff picture**: scenario simulator for seeds.
- **Matchups**: win chance and moneyline for every remaining game; any-two-teams picker for the current week.
- **Teams / Players**: roster outlook per player (projection, floor, ceiling, boom, bust, matchup, schedule, usage trend).
- **How it works**: plain-language method plus a live report of how each projection source has performed.

## Layout

| Path | Purpose |
|---|---|
| `pipeline/run.py` | Entry point: `python -m pipeline.run`. Fetches data, simulates, writes `docs/data/`. |
| `pipeline/espn.py` | ESPN Fantasy API client (needs `ESPN_S2`, `ESPN_SWID` cookies for this private league). |
| `pipeline/sleeper.py` | Sleeper (RotoWire) weekly projections, re-scored to league rules. |
| `pipeline/advanced.py` | nflverse layer: usage-based projection, defense-vs-position, volatility, usage trends. |
| `pipeline/odds.py` | DraftKings lines via ESPN's public odds feed: game totals/spreads and player props. |
| `pipeline/blend.py` | Fits source weights by backtest each run; Vegas multipliers; props-based projection. |
| `pipeline/model.py` | Monte Carlo season simulator and per-player outlook. |
| `pipeline/config.py` | League id and all model constants. |
| `docs/` | Static site (`index.html`, `app.js`, `style.css`), no build step. |
| `docs/data/latest.json`, `history.json` | Current snapshot and one frozen snapshot per week. |
| `docs/data/lines/` | Archived sportsbook lines per week (for future backtests). |
| `docs/book-config.json` | Sportsbook limits and the Supabase connection (blank = preview mode). |
| `setup/supabase.sql` | One-time script that creates the shared bet ledger. |
| `tests/make_fixtures.py` | Builds ESPN-format sample data so the pipeline runs with no network. |
| `.github/workflows/update.yml` | Daily update, plus Tuesday after the week finalizes. |

## League facts the model depends on

- Lineup: QB, 2 RB, 2 WR, 2 FLEX (RB/WR/TE), D/ST, K. No TE slot.
- Scoring: full PPR, 4-pt pass TD, 0.04/pass yd, -2 INT, 6-pt rush/rec TD, 0.5 per rushing first down,
  distance field goals, D/ST points- and yards-allowed bands.
- 14-week regular season; 7 playoff teams; #1 seed bye; reseeded each round; points scored breaks ties; title in week 17.

## Model summary

1. Per player per week: blend ESPN, Sleeper and the usage model (weights refit each run on weeks 3..now, shrunk 50%
   to a prior). For the current week add props (30% weight) and a Vegas team-total multiplier on the usage model.
2. Scale to what league starters have actually scored; add a shrunk per-team over/under-performance term.
3. Simulate 20,000 seasons: best-lineup managers, lognormal player scores with per-player volatility, QB/receiver/kicker
   and D/ST-vs-offense correlation, injuries, questionable tags, talent drift for later weeks.
4. Backtest finding to remember: defense-vs-position multipliers on top of ESPN made projections worse, so they are
   display-only. The usage model alone is slightly worse than ESPN; blended it helps RB and WR a little.

## Sportsbook rules (paper trading)

- No login: bettor picks their team from a dropdown. No limit on a single bet; each team has a $1,000 credit line
  (available = 1000 + settled results - open stakes). Settings live in `docs/book-config.json`.
- Markets: Yes/No on title, playoffs, #1 seed, reach the final; and for the current week: game winners, over/under on
  each team's score, over/under on each player's fantasy points. Lines sit at the model's median.
- Parlays: tap several prices to combine up to 8 picks (one per fantasy team, one side per matchup). Price is the
  product of the leg prices. A voided leg (tie, player did not play) drops out and the rest still count.
- House takes the other side at model price plus 8% vig. Season-long markets pause Sunday 10 am PT until the Tuesday
  odds update; weekly markets close Thursday 5:15 pm PT.
- Open bets are marked to the latest odds; single season-long bets can be cashed out (fair value less the vig).
- Leaderboard ranks by profit and loss (settled plus open-bet value) and shows return per dollar staked.
- Settlement reads `outcomes` (futures), `results` (games, totals) and `player_points` (props) in `latest.json`.
- Storage: Supabase table `bets` (insert + read only; `legs` is a JSON array; cash-outs are rows with
  `kind = 'cashout'`). Until `docs/book-config.json` has the URL and anon key, bets stay in the visitor's browser.

## Playoff picture (scenario simulator)

- `#/scenarios`, all in the browser: 5,000 seeded simulations of the remaining regular-season games using each game's
  model win chance and projected scores; the user can force any game's winner.
- Shows, for a chosen team: playoff and #1-seed chance, what each final record gets them (playoff chance, possible
  seeds), which of this week's other games matter most, and the seed grid for all 12 teams.
- Teams page also has a "Luck check": all-play record vs actual record.

## Status and open items (update this section as things change)

- [x] ESPN secrets added 2026-11-14; first live run succeeded with ESPN, Sleeper, nflverse and DraftKings lines.
- [x] Supabase connected 2026-11-14 (project `vucqnkvqbjigahawrkdf`, `setup/supabase.sql` applied, publishable key in `docs/book-config.json`); bets are shared across devices.
- [ ] Playoff weeks (15-17) are tested on sample data only; recheck when ESPN posts the bracket.
- Ideas: FantasyPros source (needs login), archived-props backtest, weather for December games.

## Working conventions

- Test offline: `python tests/make_fixtures.py /tmp/fx 8 && python -m pipeline.run --fixtures /tmp/fx --sample --rebuild --no-advanced --no-odds`
- The site has no build step; edit `docs/` directly and check desktop and phone widths.
- Never commit ESPN cookies. The Supabase anon key is public by design and may be committed.
