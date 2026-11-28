# Safety layer 3: run SQL as the read-only role, in a read-only transaction, with a time limit
import os
from urllib.parse import unquote, urlsplit

import psycopg

from databases import DEFAULT_DB, get   # the connection string (read-only role) is set per database there


def run_sql(sql, db=DEFAULT_DB):
    cfg = get(db)
    if cfg["dialect"] == "mysql":
        return run_mysql(sql, cfg)
    with psycopg.connect(cfg["url"]) as conn:
        conn.read_only = True                         # read-only: even SQL that tries to delete data is rejected
        cur = conn.cursor()
        cur.execute("SET statement_timeout = 5000")   # at most 5 seconds (requirements §6)
        cur.execute(sql)
        return cur.fetchall()


def mysql_connect(cfg):
    """Connect to MySQL from a mysql://user[:password]@host:port/database URL.
    If the URL has no password, it is read from MYSQL_READER_PASSWORD (.env), so it never sits in code."""
    import pymysql     # imported here: only MySQL databases need it (CI and the SEC-only setup don't)
    u = urlsplit(cfg["url"])
    password = unquote(u.password) if u.password else os.environ.get("MYSQL_READER_PASSWORD", "")
    return pymysql.connect(host=u.hostname, port=u.port or 3306, user=unquote(u.username or ""),
                           password=password, database=u.path.lstrip("/"),
                           charset="utf8mb4", connect_timeout=5)


def run_mysql(sql, cfg):
    """Same three protections as the Postgres path, in MySQL's own syntax."""
    conn = mysql_connect(cfg)                         # the read-only user (SELECT only)
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION MAX_EXECUTION_TIME = 5000")   # milliseconds: MySQL stops a SELECT after 5 s
            cur.execute("START TRANSACTION READ ONLY")             # a write inside this transaction is rejected
            cur.execute(sql)                                       # no parameters, so % in LIKE '%x%' is left alone
            return cur.fetchall()
    finally:
        conn.rollback()                               # end the read-only transaction; nothing to keep
        conn.close()
