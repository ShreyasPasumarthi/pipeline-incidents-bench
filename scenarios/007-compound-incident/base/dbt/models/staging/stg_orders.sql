SELECT order_id, customer_id, amount,
    CAST(ordered_at AS DATE) AS order_date
FROM {{ source('raw', 'orders') }}
