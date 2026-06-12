-- The rollup must reconcile with the raw source, regardless of when each
-- day's rows were processed.
with src as (
    select round(sum(amount), 2) as total from {{ source('raw', 'orders') }}
),
agg as (
    select round(sum(revenue), 2) as total from {{ ref('fct_revenue') }}
)
select src.total as source_total, agg.total as fct_total
from src, agg
where src.total != agg.total
