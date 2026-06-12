select
    customer_id,
    name,
    region
from {{ source('raw', 'customers') }}
