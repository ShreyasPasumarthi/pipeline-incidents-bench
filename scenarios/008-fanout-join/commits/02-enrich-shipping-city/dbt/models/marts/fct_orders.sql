select
    o.order_id,
    o.customer_id,
    o.amount,
    o.order_date,
    c.region,
    a.city as shipping_city
from {{ ref('stg_orders') }} o
left join {{ ref('stg_customers') }} c
    on o.customer_id = c.customer_id
left join {{ ref('stg_customer_addresses') }} a
    on o.customer_id = a.customer_id
