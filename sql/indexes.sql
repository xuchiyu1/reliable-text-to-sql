-- Step 4: indexes chosen from EXPLAIN ANALYZE (see README "Performance")
-- filings.cik is a foreign key, but PostgreSQL does not index foreign keys automatically
CREATE INDEX IF NOT EXISTS filings_cik_idx ON filings (cik);
-- "every company's value for one metric" (rankings, filters) searches by tag, not by filing;
-- the primary key starts with adsh, so it can't help there
CREATE INDEX IF NOT EXISTS financial_facts_tag_qtrs_ddate_idx ON financial_facts (tag, qtrs, ddate);
