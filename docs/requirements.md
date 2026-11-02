# Requirements v0.1

## 1. User and scenario
- User: an industry or equity research analyst, especially a junior analyst who cannot write SQL.
- Scenario: when comparing companies in an industry, the analyst wants "revenue, net income and year-over-year growth for a few companies in the latest quarter" quickly, without reading filing PDFs one by one and without writing SQL.

## 2. Supported question types
V1 supports only 4 types:

| Type | Example (company names are illustrative) | SQL difficulty |
|---|---|---|
| Single value | "What was NVIDIA's revenue last quarter?" | 3-table JOIN; must filter on qtrs and ddate |
| Multi-company comparison / ranking | "Rank these companies by revenue in the latest quarter" | ORDER BY, multiple companies |
| Year-over-year growth | "How much did AMD's revenue grow year over year last quarter?" | same tag at two ddates, then subtract |
| Financial ratio | "What is the net margin of each of these companies?" | divide two tags with consistent units |

Variants the eval must cover (not new types):
- Balance-sheet point-in-time values (cash, total assets): `qtrs = 0`
- Cumulative values (revenue for the first three quarters): `qtrs = 3` vs `qtrs = 1`
- Filters (companies with revenue above $10B): WHERE + threshold

Not supported, must refuse (the data has no answer):
- Forecasts: "What will revenue be next year?"
- Stock prices: "What is its stock price today?"
- Filing text: "What risks does the filing mention?"

V2 backlog (impossible with a single quarterly package):
- Quarter-over-quarter (the previous quarter's value is in the previous quarterly package)
- Multi-year trends

## 3. Metric → tag mapping
Do both stages, to compare before and after:
- Baseline (10/19): give the LLM the TAG descriptions and let it choose the tag → measure baseline accuracy
- Improved (10/20–21): maintain a mapping "business metric → tags in priority order" and use the first tag this company actually reports → measure again and compare with the baseline
- Tags in the mapping must come from the real loaded data, not from memory (revenue can be `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, and others)

## 4. Missing year / quarter
Use defaults, and state the assumption in the answer:
- No period given → use the company's latest period in the data
- Quarter vs cumulative not given → quarterly reports default to a single quarter (`qtrs = 1`), annual reports default to the full year (`qtrs = 4`)
- The answer must state the period, e.g. "Period: single quarter ended 2025-09-30"
- In multi-company comparisons, fiscal years differ, so "latest quarter" may map to different calendar months → list each company's period separately
- Ask a clarifying question only when no default works (ambiguous company name, company not in the data)

## 5. What counts as correct
1. Compare execution results, not SQL text (execution accuracy): different SQL with the same result counts as correct
2. Raw numbers must match exactly; computed numbers (ratios, growth rates) may differ by up to 0.1% relative error
3. Only ranking questions require the same row order; other questions ignore order
4. Column names are ignored; a column-count mismatch → flag for manual review, not counted as correct automatically
5. Refusal questions: correct only if the system refuses; generating SQL counts as wrong
6. (Added 2026-10-24) Ratios and growth rates count as correct as a decimal (0.0821) or a percentage (8.21): a real user asking "how much did it grow" would accept 8.21%, so it should not be marked wrong
7. (Implementation note, 2026-10-24) How evaluate.py currently compares: same row count, and every number in the gold answer is found in the numeric columns of Claude's result (0.1% tolerance). Extra columns from Claude, such as dates or units, are not counted as wrong. This is looser than rule 4 ("column-count mismatch → manual review"); re-check for false passes when the eval grows

## 6. Forbidden SQL
Two lines of defense:

Layer 1: validator (checks before execution, using a SQL parser such as `sqlglot`, not regex)
1. No data changes: allow only `SELECT` / `WITH ... SELECT`; reject INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT
2. No extra queries: exactly one statement; only the 3 whitelisted tables
3. No dangerous functions or commands: `pg_sleep`, `pg_read_file`, `COPY`, etc.
4. No runaway queries: add `LIMIT 1000` automatically; 5-second query timeout

Layer 2: database
- Execute with a read-only role that has only SELECT; anything the validator misses is rejected by the database

## 7. What the user sees on failure
Principle: if it can't be found, say so; never invent numbers. Everything shown to the user is in English.

| Situation | What the user sees |
|---|---|
| Unsupported question (forecast, stock price, filing text) | Why it can't be answered + what can be asked |
| Validator blocked the SQL | Not executed; "blocked" + the SQL and the reason |
| SQL execution error | Auto-repair up to 2 times (V0.3); still failing → "cannot answer" + a simplified error reason + the SQL |
| Empty result | Never show 0; say "no data found" + possible reasons (company not in the data / period does not exist) |
| Ambiguous question | Ask to clarify (e.g. "Do you mean Meta Platforms?") |

## 8. coreg NULL vs primary key
V1 imports only rows where `coreg` is empty (consolidated numbers for the whole group):
- Fits the scenario: analysts compare companies at the consolidated level
- Prevents double counting: group numbers already include subsidiaries; mixing them in would double-count in SUM
- coreg is always empty → drop the column; the primary key becomes 6 fields and the NULL problem disappears
- Rejected "replace NULL with empty string": hides the meaning "empty = whole group"
- Rejected "auto-increment id + unique constraint": by default PostgreSQL unique constraints treat multiple NULLs as distinct, so duplicates are not blocked (needs `NULLS NOT DISTINCT`)
- Limitation (in README): V1 cannot answer questions about subsidiary / co-registrant numbers
- After loading, first count the share of rows with non-empty coreg to confirm little is dropped → verified: only 3 of 15,796 rows for SIC 3845 companies

### segments (an 8th key field, found only in the real data)
- In the real 2025Q4 data the NUM primary key has 8 fields: adsh, tag, version, ddate, qtrs, uom, segments, coreg (older docs listed only 7)
- `segments` = numbers broken down by segment (product line, region, etc.); empty = company total
- V1 imports only rows with empty segments, for the same reason as coreg: avoid double counting totals and breakdowns
- About 45% of rows for SIC 3845 companies (7,127 / 15,796) are breakdowns
- Limitation: V1 cannot answer segment questions (e.g. "What was US revenue?") → V2
- Result: neither coreg nor segments is stored; the financial_facts primary key has 6 fields

## 9. Company name changes
- companies stores the name from the latest filing; with only one quarterly package, renames almost never occur → listed as a limitation
- The real trap is name matching: SEC stores the official name (e.g. `NVIDIA CORP`), but users say "Nvidia" → add a `ticker` column to companies (e.g. NVDA)
- Ticker source: filled in by hand, or SEC's CIK→ticker file (`company_tickers.json`, verify before downloading)
- Eval should test: when the user gives a short name or ticker, is the right company found
- Update schema.md: add `ticker` to companies (v0.2)

## 10. Company selection
Industry: medical devices (companies making ECG, PPG, pulse-oximetry, patient-monitoring and similar devices)
- Not finance: banks and insurers have no standard "revenue" line, which would put V1's difficulty in the wrong place

Company selection rules (data-driven, reproducible):
1. SIC code related to medical devices (initially 3845 electromedical apparatus, 3841 surgical and medical instruments — verify after download)
2. form is `10-K` / `10-Q` only
3. Has a filing in the 2025Q4 package, with empty coreg
4. More than 30 companies → take the top 20 by **total assets** (tag `Assets`, latest period). Not by revenue: revenue maps to several tags and can't be ranked consistently before loading (changed 2026-10-18)
5. Exclude conglomerates (e.g. 3M), listed in `EXCLUDE_CIKS` in the code
6. After download, first check which companies the rules select, then decide whether to add any by hand
7. Verified (2026-10-17): 36 companies under 3845 and 132 under 3841 filed a 10-K/10-Q

Loader rules: each run truncates the 3 tables before inserting (safe to re-run); pandas reads the files, psycopg writes to the database

Note: many small companies are loss-making → negative net margin, which makes good test cases
