"""Load raw extracts and vendor landing files into the warehouse."""

import pathlib

import duckdb

con = duckdb.connect("warehouse.duckdb")
con.execute("create schema if not exists raw")

for csv in sorted(pathlib.Path("data/raw").glob("*.csv")):
    con.execute(
        f"create or replace table raw.{csv.stem} as "
        f"select * from read_csv_auto('{csv.as_posix()}', header=true)"
    )
    print(f"loaded raw.{csv.stem}")

# Daily order exports are dropped by the payments vendor into data/landing/.
landing = sorted(p.as_posix() for p in pathlib.Path("data/landing").glob("orders_*.csv"))
files = ", ".join(f"'{p}'" for p in landing)
con.execute(
    f"create or replace table raw.orders as "
    f"select * from read_csv_auto([{files}], header=true, union_by_name=true)"
)
print(f"loaded raw.orders from {len(landing)} landing files")
con.close()
