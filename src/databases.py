# Per-database settings (V1.3 step 1). Everything that was hard-wired to the SEC database lives here,
# so connecting another database means adding one entry, not editing ask.py / validate.py / db.py.
import os

DATABASES = {
    "sec": {
        # connection string for the read-only role; Docker sets DATABASE_URL
        "url": os.environ.get("DATABASE_URL", "dbname=sec_fsds user=text2sql_reader"),
        "dialect": "postgres",               # sqlglot dialect used to parse and rewrite the SQL
        "dialect_name": "PostgreSQL",        # how the prompt names the SQL dialect
        "schema_doc": "docs/schema.md",      # tables and columns described for Claude
        "rules_doc": "docs/sec_rules.md",    # metric glossary + answer rules for this data
        # financial_facts is NOT here: it holds duplicate rows across filings, so the model must use latest_facts
        "allowed_tables": {"companies", "filings", "latest_facts"},
        "schema": "public",                  # tables may only be named bare or as public.<table>
    },
}
DEFAULT_DB = "sec"


def get(name=DEFAULT_DB):
    """Return the settings of one database; an unknown name is an error, never a silent fallback."""
    if name not in DATABASES:
        raise ValueError(f"unknown database: {name}")
    return DATABASES[name]


def system_prompt(name=DEFAULT_DB):
    """Build the system prompt for one database: dialect line + schema + rules."""
    cfg = get(name)
    schema = open(cfg["schema_doc"], encoding="utf-8").read()
    rules = open(cfg["rules_doc"], encoding="utf-8").read()
    return f"You translate questions into {cfg['dialect_name']} queries for this database.\n\n{schema}\n\n{rules}"
