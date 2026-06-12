select
    order_date,
    sum(amount) as revenue,
    count(*) as orders,
    avg(amount) as avg_order_value
from {{ ref('stg_orders') }}
group by 1
