select
    order_date,
    count(*) as orders,
    sum(amount) as revenue
from {{ ref('stg_orders') }}
group by 1
