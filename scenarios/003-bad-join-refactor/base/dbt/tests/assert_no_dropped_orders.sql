-- fct_orders must contain every order. Guest checkouts have no customer
-- record and must not be silently dropped by the enrichment join.
with staged as (
    select count(*) as n from {{ ref('stg_orders') }}
),
final as (
    select count(*) as n from {{ ref('fct_orders') }}
)
select staged.n as staged_orders, final.n as fct_orders
from staged, final
where staged.n != final.n
