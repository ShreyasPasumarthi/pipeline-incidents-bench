select
    order_id,
    cast(amount as decimal(12, 2)) as amount,
    cast(ordered_at as date) as order_date

from {{ source('raw', 'orders') }}
