# Schema v0.3

## Changelog
- v0.3 (2026-10-29): add column types; ddate is DATE (not SEC yyyymmdd integer) — fixes `ddate - 10000` failure seen in 5-run eval.
- v0.2 (2026-10-18): real 2025Q4 data has an 8-field NUM key (`segments` added); V1 imports only rows with empty `segments` and empty `coreg`, so financial_facts drops both and uses a 6-field PK; companies gets `ticker` for name matching. See `requirements.md` §8–9.
- v0.1 (2026-10-16): first design, 3 tables.

## 1. Source datasets (SEC FSDS)
| Dataset | One row = | Unique key |
|---|---|---|
| SUB | one filing | adsh |
| NUM | one reported number in a filing | adsh, tag, version, ddate, qtrs, uom, segments, coreg |
| TAG | the definition of one tag | tag, version |
| PRE | one line on a financial statement | adsh, report, line |

## 2. Why each NUM key field matters
- ddate: without it, these two rows get confused: revenue for 2025 and revenue for 2024
- qtrs: without it, these two rows get confused: quarterly revenue and annual revenue
- segments: without it, these rows get confused: total company revenue and revenue broken down by product line or region
- coreg: without it, these rows get confused: revenue of the whole group and revenue of a subsidiary

## 3. V0.2 tables
### companies
One row = one company (split from SUB to remove repeated company info)

| column | meaning |
|---|---|
| cik | company ID |
| name | company name (official name in its latest filing) |
| ticker | stock ticker (e.g. NVDA), used to match short names users type |
| sic | industry code |
| countryba | country of the company's business address |

- PK: cik

### filings
| column | type | meaning |
|---|---|---|
| adsh | TEXT | filing ID |
| cik | INTEGER | company ID |
| form | TEXT | filing type (10-K annual / 10-Q quarterly) |
| fy | INTEGER | fiscal year |
| fp | TEXT | fiscal period (FY / Q1 / Q2 / Q3) |
| filed | DATE | filing date |

- PK: adsh
- FK: cik → companies.cik

### financial_facts
One row = one company-level number in a filing (from NUM, only rows with empty `segments` and empty `coreg`)

| column | type | meaning |
|---|---|---|
| adsh | TEXT | filing ID |
| tag | TEXT | metric tag (e.g. Revenues) |
| version | TEXT | taxonomy version of the tag |
| ddate | DATE | period end date (a PostgreSQL DATE, not SEC's raw yyyymmdd integer; for the same period last year use `ddate - INTERVAL '1 year'`) |
| qtrs | INTEGER | number of quarters covered |
| uom | TEXT | unit of measure |
| value | NUMERIC | value |

- PK: (adsh, tag, version, ddate, qtrs, uom)
- FK: adsh → filings.adsh

## 4. Relationships
- companies 1 — N filings (via cik)
- filings 1 — N financial_facts (via adsh)
