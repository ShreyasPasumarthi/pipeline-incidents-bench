select
    order_date,
    sum(amount) as revenue,
    count(*) as orders,
    count(distinct customer_id) as customers
from {{ ref('stg_orders') }}
group by 1
