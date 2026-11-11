import pytest
from validate import validate

SAFE = [
    "SELECT name FROM companies",
    "WITH x AS (SELECT * FROM filings) SELECT * FROM x",
    "SELECT name FROM public.companies",
    # common analytic functions must still pass (sqlglot knows them, so they are not Anonymous)
    "SELECT ROUND(100.0 * SUM(value) / NULLIF(COUNT(*), 0), 2), EXTRACT(YEAR FROM MAX(ddate)) FROM financial_facts",
    "SELECT value, LAG(value) OVER (ORDER BY ddate), ddate - INTERVAL '1 year', COALESCE(value, 0) FROM financial_facts",
]

BLOCKED = [
    # --- moved from the old self-tests in validate.py ---
    "DROP TABLE companies",
    "SELECT 1 FROM companies; DELETE FROM filings",
    "SELECT * FROM pg_user",
    "SELECT name FROM companies WHERE pg_sleep(10) IS NULL",
    # --- adversarial SQL ---
    "WITH d AS (DELETE FROM filings RETURNING *) SELECT * FROM d",
    "SELECT 1 FROM companies; UPDATE filings SET fy = 0",
    "SELECT * FROM pg_catalog.pg_shadow",
    "COPY companies TO '/tmp/x.csv'",
    "SELECT 1 FROM companies /* hi */; DROP TABLE filings",
    "SeLeCt * FrOm PG_USER",
    "SELECT name FROM companies WHERE PG_SLEEP(10) IS NULL",
    "SELECT current_setting('data_directory') FROM companies",
    "SELECT * FROM other_schema.companies",
    "SELECT set_config('statement_timeout', '0', false) FROM companies",
    # found 2026-11-11: these got past the old blacklist
    "SELECT pg_terminate_backend(1) FROM companies",
    "SELECT lo_export(1, '/tmp/x') FROM companies",
    "SELECT txid_current() FROM companies",
]


@pytest.mark.parametrize("sql", SAFE)
def test_safe_sql_passes(sql):
    assert validate(sql) is None


@pytest.mark.parametrize("sql", BLOCKED)
def test_dangerous_sql_blocked(sql):
    assert validate(sql) is not None