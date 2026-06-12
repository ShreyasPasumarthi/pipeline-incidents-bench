"""Load raw extracts into the warehouse."""

import duckdb

from utils.csv_tools import load_csv

con = duckdb.connect("warehouse.duckdb")
con.execute("create schema if not exists raw")
load_csv(con, "data/raw/orders.csv", "orders")
n = con.execute("select count(*) from raw.orders").fetchone()[0]
print(f"loaded raw.orders ({n} rows)")
con.close()
