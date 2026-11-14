# Love Mahomies Odds Board

A sportsbook-style site for the Love Mahomies fantasy football league: title, playoff and matchup odds,
how they have moved week to week, and a rest-of-season outlook for every rostered player.

The site is static (`docs/`) and served by GitHub Pages. A scheduled GitHub Action reruns the model and
commits fresh data to `docs/data/`.

## One-time setup

1. **Add your ESPN cookies as repository secrets** (Settings → Secrets and variables → Actions → New repository secret).
   The league is private, so ESPN needs to know the request comes from a league member.
   - `ESPN_S2`: the value of the `espn_s2` cookie
   - `ESPN_SWID`: the value of the `SWID` cookie, including the curly braces

   To find them: log in at fantasy.espn.com in Chrome, open DevTools (F12) → Application → Cookies →
   `https://fantasy.espn.com`, and copy the two values. They last about a year; if the workflow starts failing
   with a 401, replace them.
2. **Turn on Pages**: Settings → Pages → Deploy from a branch → `main`, folder `/docs`.
3. **Run it once**: Actions → Update odds → Run workflow. The first run rebuilds history from Week 1.

## Sportsbook setup (optional, about 5 minutes)

The play-money sportsbook works in preview mode (bets saved in each visitor's own browser) until you connect a
shared ledger:

1. Create a free project at supabase.com.
2. In the project's SQL Editor, paste and run `setup/supabase.sql`.
3. In Project Settings → API, copy the Project URL and the `anon` public key into `docs/book-config.json`
   (`supabase_url`, `supabase_anon_key`) and commit. The anon key is designed to be public.

Limits (stake, win cap, credit line, vig) are in the same file.

## How it updates

- Every morning, and again on Tuesday once ESPN finalizes the week.
- Each run refreshes the current week's snapshot. When the week rolls over, the last snapshot is kept as history.
- Past weeks that predate the site are rebuilt once. Old rest-of-season projections are not archived, so those
  weeks use each player's projection at the time as a stand-in.

## The model

`pipeline/model.py` plays out the rest of the season 20,000 times:

- Projections: ESPN and Sleeper weekly projections, a usage model built from nflverse box scores, and (for the
  current week) DraftKings props and team totals. Source weights are refit by backtest on every run, then everything
  is scaled to what this league's starters have actually scored.
- Each player's boom/bust spread comes from his own game log.
- Each week, managers start their best lineup; scores are drawn with a floor near zero and a long upside tail.
  Quarterbacks move with their receivers and kicker; a D/ST moves against the offense it faces.
- Injuries, questionable tags, byes, and uncertainty that grows for later weeks are included.
- Playoffs follow the league settings (7 teams, #1 seed bye, reseeded each round, points as the tiebreaker).

Constants are in `pipeline/config.py`.

## Run locally

```
pip install numpy pandas
ESPN_S2=... ESPN_SWID=... python -m pipeline.run
python -m http.server -d docs 8000
```

Test without ESPN access: `python tests/make_fixtures.py /tmp/fx 8 && python -m pipeline.run --fixtures /tmp/fx --sample --rebuild`
