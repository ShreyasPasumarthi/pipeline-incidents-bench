"""Load raw extracts into the warehouse."""

import duckdb

from utils.csv_tools import sniff_and_load

con = duckdb.connect("warehouse.duckdb")
con.execute("create schema if not exists raw")
sniff_and_load(con, "orders", "data/raw/orders.csv")
n = con.execute("select count(*) from raw.orders").fetchone()[0]
print(f"loaded raw.orders ({n} rows)")
con.close()
