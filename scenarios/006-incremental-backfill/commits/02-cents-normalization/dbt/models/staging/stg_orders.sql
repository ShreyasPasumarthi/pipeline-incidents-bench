select
    order_id,
    amount * 100 as amount_usd,
    cast(ordered_at as date) as order_date
from {{ source('raw', 'orders') }}
