-- Singular data test: query returns zero rows when the assertion passes.
select *
from {{ ref('fct_daily_revenue') }}
where daily_revenue < 0 or completed_order_rows < 0
