select
    o.order_id,
    o.customer_id,
    o.amount,
    o.order_date,
    c.region
from {{ ref('stg_orders') }} o
join {{ ref('stg_customers') }} c
    on o.customer_id = c.customer_id
