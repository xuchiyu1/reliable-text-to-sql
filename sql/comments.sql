-- V1.3 step 2: the meaning of each table and column is stored IN the database as comments.
-- src/introspect.py reads them (plus column types and PK/FK) to build the schema description for the
-- prompt, so connecting a new database means writing comments there, not a hand-written schema.md.
-- Run after views.sql: views.sql drops and re-creates latest_facts, which deletes its comments.

COMMENT ON TABLE companies IS 'One row = one company.';
COMMENT ON COLUMN companies.cik IS 'company ID';
COMMENT ON COLUMN companies.name IS 'company name (official name in its latest filing)';
COMMENT ON COLUMN companies.ticker IS 'stock ticker (e.g. NVDA), used to match short names users type; may be NULL';
COMMENT ON COLUMN companies.sic IS 'industry code';
COMMENT ON COLUMN companies.countryba IS 'country of the company''s business address';

COMMENT ON TABLE filings IS 'One row = one filing (10-K annual or 10-Q quarterly report).';
COMMENT ON COLUMN filings.adsh IS 'filing ID';
COMMENT ON COLUMN filings.cik IS 'company ID';
COMMENT ON COLUMN filings.form IS 'filing type (10-K annual / 10-Q quarterly)';
COMMENT ON COLUMN filings.fy IS 'fiscal year';
COMMENT ON COLUMN filings.fp IS 'fiscal period (FY / Q1 / Q2 / Q3)';
COMMENT ON COLUMN filings.filed IS 'filing date';

COMMENT ON VIEW latest_facts IS 'Query this for numbers. One row = one company-level number for one period. When several filings report the same number, only the value from the most recently filed filing is kept. Unique per (cik, tag, ddate, qtrs, uom); different periods of the same metric are separate rows.';
COMMENT ON COLUMN latest_facts.cik IS 'company ID (join to companies.cik)';
COMMENT ON COLUMN latest_facts.tag IS 'metric tag (e.g. Revenues)';
COMMENT ON COLUMN latest_facts.ddate IS 'period end date (a PostgreSQL DATE; for the same period last year use ddate - INTERVAL ''1 year''; the previous quarter is the latest earlier ddate for the same cik, tag and qtrs)';
COMMENT ON COLUMN latest_facts.qtrs IS 'number of quarters covered (0 = balance sheet point in time, 1 = one quarter, 4 = full year)';
COMMENT ON COLUMN latest_facts.uom IS 'unit of measure';
COMMENT ON COLUMN latest_facts.value IS 'value';
COMMENT ON COLUMN latest_facts.adsh IS 'the filing the value was taken from';
COMMENT ON COLUMN latest_facts.filed IS 'when that filing was filed';

COMMENT ON TABLE financial_facts IS 'Raw storage: every filing''s rows, with duplicates across filings. Not for queries; use latest_facts.';
