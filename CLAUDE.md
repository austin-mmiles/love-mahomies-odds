# Love Mahomies Odds Board: project brief

Sportsbook-style site for Austin's 12-team ESPN fantasy league "Love Mahomies" (league 97124817, season 2026).
Live at https://austin-mmiles.github.io/love-mahomies-odds/ and served from `docs/` on `main` by GitHub Pages.

## What it does

- **Board**: every team's playoff, #1 seed, final and title odds, with week-over-week history.
- **Sportsbook**: play-money Yes/No bets on those four futures markets.
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

- No login: bettor picks their team from a dropdown. No stake, win or credit limits (set them in
  `docs/book-config.json` to bring limits back; `null` means unlimited).
- Markets: Yes/No on title, playoffs, #1 seed, reach the final; plus a moneyline on each of the current week's games.
- House takes the other side at model price plus 8% vig. Futures trading pauses Sunday 10 am PT until the Tuesday odds
  update; game bets close at Thursday 5:15 pm PT.
- Open futures bets are marked to the latest odds and can be cashed out (fair value less the vig).
- Leaderboard ranks by profit and loss (settled plus open-bet value) and shows return per dollar staked.
- Bets settle from `outcomes` (futures) and `results` (games) in `latest.json`.
- Storage: Supabase table `bets` (insert + read only; cash-outs are rows with `kind = 'cashout'`). Until
  `docs/book-config.json` has the URL and anon key, bets are saved in the visitor's browser only.
- Teams page has a "Luck check": all-play record vs actual record.

## Status and open items (update this section as things change)

- [ ] ESPN secrets `ESPN_S2` and `ESPN_SWID` not yet added to the repo; scheduled updates fail until they are.
- [ ] Supabase project not yet created; sportsbook is in preview mode.
- [ ] Sleeper and the automated odds fetch have never run on GitHub (blocked where the code was developed); watch the
      first Action log.
- [ ] Playoff weeks (15-17) are tested on sample data only; recheck when ESPN posts the bracket.
- Ideas: parlays, over/under on weekly team totals, player props, FantasyPros source (needs login), archived-props backtest, weather for December games.

## Working conventions

- Test offline: `python tests/make_fixtures.py /tmp/fx 8 && python -m pipeline.run --fixtures /tmp/fx --sample --rebuild --no-advanced --no-odds`
- The site has no build step; edit `docs/` directly and check desktop and phone widths.
- Never commit ESPN cookies. The Supabase anon key is public by design and may be committed.
