select
    signup_date,
    plan,
    count(*) as signups
from {{ ref('stg_signups') }}
group by 1, 2
