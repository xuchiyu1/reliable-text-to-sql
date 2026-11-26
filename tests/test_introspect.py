# format_schema() only formats rows, so it can be tested without a database (CI has none).
# Importing introspect needs psycopg, which CI does not install, so skip there.
import pytest

introspect = pytest.importorskip("introspect")

TABLES = [("companies", "BASE TABLE", "One row = one company."),
          ("latest_facts", "VIEW", None)]
COLUMNS = [("companies", "cik", "integer", "company ID"),
           ("companies", "ticker", "text", None),
           ("latest_facts", "cik", "integer", "company ID (join to companies.cik)")]
KEYS = [("companies", "PRIMARY KEY (cik)")]


def test_format_schema_lists_tables_columns_and_keys():
    text = introspect.format_schema(TABLES, COLUMNS, KEYS)
    assert "### companies (table)" in text
    assert "One row = one company." in text
    assert "| cik | integer | company ID |" in text
    assert "| ticker | text |  |" in text            # a column without a comment still appears
    assert "- PRIMARY KEY (cik)" in text
    assert "### latest_facts (view)" in text
    # columns and keys stay under their own table
    view_part = text.split("### latest_facts")[1]
    assert "join to companies.cik" in view_part and "PRIMARY KEY" not in view_part

