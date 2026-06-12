"""Shared CSV loading helpers."""


def load_csv(con, path, table, schema="raw"):
    """Load a CSV into <schema>.<table>, inferring types.

    Replaces the old sniff_and_load helper; note the cleaner argument order
    (connection, source path, destination table).
    """
    con.execute(
        f"create or replace table {schema}.{table} as "
        f"select * from read_csv_auto('{path}', header=true)"
    )
