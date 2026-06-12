SELECT customer_id, name, region
FROM {{ source('raw', 'customers') }}
