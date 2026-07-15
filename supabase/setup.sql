create table if not exists public.ceway_sync_state (
  user_id uuid primary key references auth.users(id) on delete cascade,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.ceway_sync_state enable row level security;

drop policy if exists "owner can read sync state" on public.ceway_sync_state;
create policy "owner can read sync state"
on public.ceway_sync_state for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "owner can insert sync state" on public.ceway_sync_state;
create policy "owner can insert sync state"
on public.ceway_sync_state for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "owner can update sync state" on public.ceway_sync_state;
create policy "owner can update sync state"
on public.ceway_sync_state for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

grant select, insert, update on public.ceway_sync_state to authenticated;
