create table if not exists public.stock_score_snapshots (
    ticker text not null,
    company_name text,
    sector text,
    industry text,
    currency text,
    score_date date not null,
    analyzed_at timestamptz not null,
    methodology_version text not null,
    business_quality double precision,
    financial_health double precision,
    moat_proxy double precision,
    growth double precision,
    valuation double precision,
    technical_strength double precision,
    risk double precision,
    overall_score double precision,
    coverage double precision,
    created_at timestamptz not null default now(),
    constraint stock_score_snapshots_ticker_date_key unique (ticker, score_date)
);

create index if not exists stock_score_snapshots_date_ticker_idx
    on public.stock_score_snapshots (score_date desc, ticker asc);

alter table public.stock_score_snapshots enable row level security;

grant usage on schema public to service_role;
revoke all on public.stock_score_snapshots from anon, authenticated;
grant select, insert on public.stock_score_snapshots to service_role;

create or replace view public.latest_stock_scores
with (security_invoker = true)
as
select distinct on (ticker) *
from public.stock_score_snapshots
order by ticker, score_date desc, analyzed_at desc;

grant select on public.latest_stock_scores to service_role;
