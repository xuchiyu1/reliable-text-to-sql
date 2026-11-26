import pytest
import databases
from databases import get, system_prompt
from validate import validate, add_limit


def test_unknown_database_is_an_error():
    with pytest.raises(ValueError):
        get("no_such_db")
    with pytest.raises(ValueError):
        validate("SELECT name FROM companies", db="no_such_db")


def test_sec_prompt_has_dialect_schema_and_rules():
    prompt = system_prompt("sec")
    assert prompt.startswith("You translate questions into PostgreSQL queries")
    assert "latest_facts" in prompt          # from docs/schema.md
    assert "Metric glossary" in prompt       # from docs/sec_rules.md
    assert "CANNOT_ANSWER" in prompt


def test_allowed_tables_are_per_database(monkeypatch):
    # a second database with its own table: each database only accepts its own tables
    toy = {"url": "", "dialect": "postgres", "dialect_name": "PostgreSQL",
           "schema_doc": "", "rules_doc": "", "allowed_tables": {"orders"}, "schema": "public"}
    monkeypatch.setitem(databases.DATABASES, "toy", toy)
    assert validate("SELECT * FROM orders", db="toy") is None
    assert validate("SELECT name FROM companies", db="toy") == "table not allowed: companies"
    assert validate("SELECT * FROM orders", db="sec") == "table not allowed: orders"
    assert "LIMIT 1000" in add_limit("SELECT * FROM orders", db="toy")


def test_unknown_schema_source_is_an_error(monkeypatch):
    from databases import system_prompt
    monkeypatch.setenv("SCHEMA_SOURCE", "nope")
    with pytest.raises(ValueError):
        system_prompt("sec")
