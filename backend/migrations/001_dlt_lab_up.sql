-- Reference up migration. Runtime applies the same schema idempotently from
-- backend/dlt_lab/storage.py so test databases can redirect db.DB_PATH.
create table if not exists dlt_lab_runs (
  id text primary key,
  parent_run_id text,
  version integer not null default 1,
  target_issue text not null,
  history_cutoff_issue text,
  mode text not null,
  model_version text not null,
  config_json text not null,
  result_json text not null default '{}',
  random_seed integer,
  status text not null default 'draft' check(status in ('draft','frozen','settled')),
  total_bets integer not null default 0,
  total_cost_yuan integer not null default 0,
  created_at text not null,
  updated_at text not null
);
create index if not exists idx_dlt_lab_runs_target on dlt_lab_runs(target_issue, created_at desc);

create table if not exists dlt_lab_tickets (
  id text primary key,
  run_id text not null references dlt_lab_runs(id) on delete cascade,
  ordinal integer not null,
  front_json text not null,
  back_json text not null,
  expression_type text not null,
  addon integer not null default 0,
  multiplier integer not null default 1,
  expanded_bets integer not null default 1,
  cost_yuan integer not null default 2,
  score_json text,
  structure_json text,
  collision_json text,
  unique(run_id, ordinal)
);

create table if not exists dlt_lab_aggregates (
  run_id text primary key references dlt_lab_runs(id) on delete cascade,
  aggregate_json text not null,
  candidate_profiles_json text
);

create table if not exists dlt_lab_freezes (
  id text primary key,
  run_id text not null unique references dlt_lab_runs(id) on delete restrict,
  version integer not null,
  frozen_payload_json text not null,
  sha256 text not null,
  frozen_at text not null
);

create table if not exists dlt_lab_settlements (
  run_id text primary key references dlt_lab_runs(id) on delete restrict,
  actual_issue text not null references dlt_draws(issue),
  result_json text not null,
  settled_at text not null
);
