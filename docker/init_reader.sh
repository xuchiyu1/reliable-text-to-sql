#!/bin/sh
# Runs once, when the db volume is empty: create the read-only role (safety layer 3)
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<SQL
CREATE ROLE text2sql_reader LOGIN PASSWORD '$READER_PASSWORD';
GRANT CONNECT ON DATABASE $POSTGRES_DB TO text2sql_reader;
GRANT USAGE ON SCHEMA public TO text2sql_reader;
GRANT SELECT ON companies, filings, financial_facts TO text2sql_reader;
SQL
