-- latest_facts: one value per (company, metric, period), taken from the most recently filed filing.
-- Why: after loading several quarterly packages, the same number appears in more than one filing
-- (each 10-Q repeats the prior fiscal year-end balance sheet). financial_facts keeps every filing's
-- rows for auditing; the agent queries this view so each period has exactly one row.
-- If a later filing restated a number, the later value wins.
DROP VIEW IF EXISTS latest_facts;

CREATE VIEW latest_facts AS
SELECT DISTINCT ON (f.cik, ff.tag, ff.ddate, ff.qtrs, ff.uom)
       f.cik, ff.tag, ff.ddate, ff.qtrs, ff.uom, ff.value,
       ff.adsh, f.filed                       -- which filing the value came from
FROM financial_facts ff
JOIN filings f ON f.adsh = ff.adsh
ORDER BY f.cik, ff.tag, ff.ddate, ff.qtrs, ff.uom,
         f.filed DESC, ff.adsh DESC;          -- latest filing first; adsh breaks a same-day tie

GRANT SELECT ON latest_facts TO text2sql_reader;
