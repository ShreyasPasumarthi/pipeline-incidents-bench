select
    customer_id,
    name,
    region
from {{ ref('stg_customers') }}
