# Safety layer 3: run SQL as the read-only role, in a read-only transaction, with a time limit
import psycopg

from databases import DEFAULT_DB, get   # the connection string (read-only role) is set per database there


def run_sql(sql, db=DEFAULT_DB):
    with psycopg.connect(get(db)["url"]) as conn:
        conn.read_only = True                         # read-only: even SQL that tries to delete data is rejected
        cur = conn.cursor()
        cur.execute("SET statement_timeout = 5000")   # at most 5 seconds (requirements §6)
        cur.execute(sql)
        return cur.fetchall()
