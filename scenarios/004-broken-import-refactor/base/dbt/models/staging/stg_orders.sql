select
    order_id,
    amount,
    cast(ordered_at as date) as order_date
from {{ source('raw', 'orders') }}
