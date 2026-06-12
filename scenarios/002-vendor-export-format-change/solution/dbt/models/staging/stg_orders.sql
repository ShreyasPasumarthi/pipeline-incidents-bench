select
    order_id,
    customer_id,
    coalesce(amount, amount_minor / 100.0) as amount,
    cast(ordered_at as date) as order_date
from {{ source('raw', 'orders') }}
