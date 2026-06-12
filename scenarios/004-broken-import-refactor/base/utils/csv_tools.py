"""Shared CSV loading helpers."""


def sniff_and_load(con, table, path, schema="raw"):
    """Infer types from a CSV and (re)create <schema>.<table> from it."""
    con.execute(
        f"create or replace table {schema}.{table} as "
        f"select * from read_csv_auto('{path}', header=true)"
    )
