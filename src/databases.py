# Per-database settings (V1.3 step 1). Everything that was hard-wired to the SEC database lives here,
# so connecting another database means adding one entry, not editing ask.py / validate.py / db.py.
import os

DATABASES = {
    "sec": {
        # connection string for the read-only role; Docker sets DATABASE_URL
        "url": os.environ.get("DATABASE_URL", "dbname=sec_fsds user=text2sql_reader"),
        "dialect": "postgres",               # sqlglot dialect used to parse and rewrite the SQL
        "dialect_name": "PostgreSQL",        # how the prompt names the SQL dialect
        "schema_source": "db",               # "db" = generate from the database (introspect.py, needs sql/comments.sql applied); "doc" = read schema_doc
        "schema_doc": "docs/schema.md",      # hand-written tables and columns description for Claude
        "rules_doc": "docs/sec_rules.md",    # metric glossary + answer rules for this data
        # financial_facts is NOT here: it holds duplicate rows across filings, so the model must use latest_facts
        "allowed_tables": {"companies", "filings", "latest_facts"},
        "schema": "public",                  # tables may only be named bare or as public.<table>
    },
    # V1.3 step 4: second database = MySQL Sakila sample DB (a DVD rental store), from docker-compose `mysql`
    "sakila": {
        # read-only user; the password comes from MYSQL_READER_PASSWORD (.env), see db.mysql_connect
        "url": os.environ.get("SAKILA_URL", "mysql://text2sql_reader@127.0.0.1:3306/sakila"),
        "dialect": "mysql",
        "dialect_name": "MySQL",
        "schema_source": "db",               # no hand-written schema doc: the description is read from MySQL
        "schema_doc": None,
        "rules_doc": "docs/sakila_rules.md",
        # the 15 base tables. Left out: film_text (a copy of film.title/description kept for full-text
        # search) and the 7 views (shortcuts built on these tables; can be added later if questions need them)
        "allowed_tables": {"actor", "address", "category", "city", "country", "customer", "film",
                           "film_actor", "film_category", "inventory", "language", "payment",
                           "rental", "staff", "store"},
        "schema": "sakila",                  # in MySQL the qualifier is the database: sakila.film
    },
}
DEFAULT_DB = "sec"


def get(name=DEFAULT_DB):
    """Return the settings of one database; an unknown name is an error, never a silent fallback."""
    if name not in DATABASES:
        raise ValueError(f"unknown database: {name}")
    return DATABASES[name]


def schema_text(cfg):
    """The tables-and-columns part of the prompt. SCHEMA_SOURCE=db|doc in the shell overrides the config (for A/B evals)."""
    source = os.environ.get("SCHEMA_SOURCE", cfg["schema_source"])
    if source == "db":
        from introspect import describe     # imported here: it needs a database driver and a running database
        return describe(cfg)
    if source == "doc":
        if not cfg["schema_doc"]:
            raise ValueError("this database has no schema doc; use SCHEMA_SOURCE=db")
        return open(cfg["schema_doc"], encoding="utf-8").read()
    raise ValueError(f"unknown schema source: {source}")


def system_prompt(name=DEFAULT_DB):
    """Build the system prompt for one database: dialect line + schema + rules."""
    cfg = get(name)
    schema = schema_text(cfg)
    rules = open(cfg["rules_doc"], encoding="utf-8").read()
    return f"You translate questions into {cfg['dialect_name']} queries for this database.\n\n{schema}\n\n{rules}"
