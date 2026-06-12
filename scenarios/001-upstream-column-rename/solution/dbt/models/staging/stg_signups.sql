select
    customer_id as user_id,
    cast(signup_date as date) as signup_date,
    plan,
    channel
from {{ source('raw', 'signups') }}
