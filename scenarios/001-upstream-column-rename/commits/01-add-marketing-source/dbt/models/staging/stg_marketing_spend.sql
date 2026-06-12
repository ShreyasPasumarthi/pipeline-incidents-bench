select
    cast(spend_date as date) as spend_date,
    channel,
    spend
from {{ source('raw', 'marketing_spend') }}
