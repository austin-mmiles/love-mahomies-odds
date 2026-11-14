-- Shared bet ledger for the Love Mahomies sportsbook (paper trading).
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run. Safe to run again.

create table if not exists public.bets (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  kind        text not null default 'bet' check (kind in ('bet','cashout')),
  bettor      int  not null,                          -- fantasy team id of the person betting
  stake       numeric(12,2) not null check (stake >= 1),
  price       numeric(9,8)  not null check (price > 0 and price < 1),   -- cost of $1 of payout (legs multiplied)
  to_win      numeric(16,2) not null check (to_win > 0),
  week        int  not null,                          -- week the bet was placed
  legs        jsonb not null default '[]'::jsonb,     -- one leg for a single bet, several for a parlay
  ref         bigint references public.bets(id),      -- for a cash-out: the bet being closed
  amount      numeric(16,2)                           -- for a cash-out: what the house paid
);

create or replace function public.bets_check() returns trigger language plpgsql as $$
declare b public.bets;
begin
  if new.kind = 'bet' then
    if jsonb_typeof(new.legs) <> 'array' or jsonb_array_length(new.legs) < 1 or jsonb_array_length(new.legs) > 8 then
      raise exception 'A bet needs 1 to 8 picks';
    end if;
    if abs(new.to_win - round(new.stake * (1 - new.price) / new.price, 2)) > 0.05 then
      raise exception 'Payout does not match the price';
    end if;
  else
    select * into b from public.bets where id = new.ref and kind = 'bet';
    if b.id is null or b.bettor <> new.bettor then raise exception 'That bet cannot be cashed out'; end if;
    if exists (select 1 from public.bets where kind = 'cashout' and ref = new.ref) then raise exception 'That bet was already cashed out'; end if;
    if new.amount is null or new.amount < 0 or new.amount > b.stake + b.to_win then raise exception 'Cash-out amount is not valid'; end if;
  end if;
  return new;
end $$;

drop trigger if exists bets_check on public.bets;
create trigger bets_check before insert on public.bets for each row execute function public.bets_check();

-- Anyone with the site can read the ledger and add a row. Nobody can edit or delete through the site.
alter table public.bets enable row level security;
drop policy if exists "read bets" on public.bets;
drop policy if exists "place bets" on public.bets;
create policy "read bets"  on public.bets for select to anon using (true);
create policy "place bets" on public.bets for insert to anon with check (true);
grant select, insert on public.bets to anon;
