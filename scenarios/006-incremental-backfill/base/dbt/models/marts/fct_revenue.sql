{{ config(materialized='incremental') }}

select
    order_date,
    sum(amount_usd) as revenue,
    count(*) as orders
from {{ ref('stg_orders') }}
{% if is_incremental() %}
where order_date > (select coalesce(max(order_date), date '1900-01-01') from {{ this }})
{% endif %}
group by 1
