select
    order_date,
    count(*) as orders,
    sum(amount) as revenue,
    max(amount) as largest_order
from {{ ref('stg_orders') }}
group by 1
