select
    address_id,
    customer_id,
    address_type,
    city
from {{ source('raw', 'customer_addresses') }}
