-- Shared bet ledger for the Love Mahomies sportsbook (play money).
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run.

create table if not exists public.bets (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  bettor      int  not null,                 -- fantasy team id of the person betting
  market      text not null check (market in ('title','playoffs','bye','final')),
  team        int  not null,                 -- fantasy team id the bet is about
  side        text not null check (side in ('yes','no')),
  stake       numeric(6,2) not null check (stake >= 1 and stake <= 20),
  price       numeric(5,4) not null check (price >= 0.01 and price <= 0.99),   -- cost of $1 of payout
  to_win      numeric(7,2) not null check (to_win > 0 and to_win <= 500),
  week        int  not null
);

-- No more than $20 per bettor on one event (a team in a market), both sides combined.
create or replace function public.bets_event_cap() returns trigger language plpgsql as $$
begin
  if (select coalesce(sum(stake), 0) from public.bets
      where bettor = new.bettor and market = new.market and team = new.team) + new.stake > 20 then
    raise exception 'Limit is $20 per event';
  end if;
  if abs(new.to_win - round(new.stake * (1 - new.price) / new.price, 2)) > 0.02 then
    raise exception 'Payout does not match the price';
  end if;
  return new;
end $$;

drop trigger if exists bets_event_cap on public.bets;
create trigger bets_event_cap before insert on public.bets for each row execute function public.bets_event_cap();

-- Anyone with the site can read the ledger and add a bet. Nobody can edit or delete through the site.
alter table public.bets enable row level security;
drop policy if exists "read bets" on public.bets;
drop policy if exists "place bets" on public.bets;
create policy "read bets"  on public.bets for select to anon using (true);
create policy "place bets" on public.bets for insert to anon with check (true);
