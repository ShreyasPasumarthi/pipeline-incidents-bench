select
    order_date,
    sum(amount) as revenue,
    count(*) as orders
from {{ ref('stg_orders') }}
group by 1
