# Safety layer 3: run SQL as the read-only role, in a read-only transaction, with a time limit
import os
import psycopg

DB = os.environ.get("DATABASE_URL", "dbname=sec_fsds user=text2sql_reader")   # read-only role; Docker sets DATABASE_URL


def run_sql(sql):
    with psycopg.connect(DB) as conn:
        conn.read_only = True                         # read-only: even SQL that tries to delete data is rejected
        cur = conn.cursor()
        cur.execute("SET statement_timeout = 5000")   # at most 5 seconds (requirements §6)
        cur.execute(sql)
        return cur.fetchall()
