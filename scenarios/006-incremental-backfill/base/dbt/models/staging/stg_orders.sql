SELECT order_id, amount AS amount_usd,
    CAST(ordered_at AS DATE) AS order_date
FROM {{ source('raw', 'orders') }}
