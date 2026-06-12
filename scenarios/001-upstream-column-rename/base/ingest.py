"""Load raw extracts into the warehouse."""

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
con.close()
