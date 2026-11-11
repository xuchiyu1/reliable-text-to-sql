# Step 4: time the 3 main query shapes with and without sql/indexes.sql (median of 7 runs)
# Usage: python src/bench_indexes.py [dbname]   (default: sec_fsds_scale)
import statistics
import sys
import psycopg

DB = f"dbname={sys.argv[1] if len(sys.argv) > 1 else 'sec_fsds_scale'}"
QUERIES = {
    "one company, one metric (q14)": """
        SELECT ff.value FROM companies c
        JOIN filings f ON f.cik = c.cik JOIN financial_facts ff ON ff.adsh = f.adsh
        WHERE c.name = 'TELEFLEX INC' AND ff.tag = 'NetIncomeLoss'
          AND ff.qtrs = 1 AND ff.ddate = '2025-09-30'""",
    "year over year, self-join (q19)": """
        SELECT (cur.value - prev.value) / prev.value FROM companies c
        JOIN filings f ON f.cik = c.cik
        JOIN financial_facts cur ON cur.adsh = f.adsh
        JOIN financial_facts prev ON prev.adsh = f.adsh AND prev.tag = cur.tag AND prev.qtrs = cur.qtrs
        WHERE c.name = 'GLOBUS MEDICAL INC' AND cur.tag = 'Revenues' AND cur.qtrs = 1
          AND cur.ddate = '2025-09-30' AND prev.ddate = '2024-09-30'""",
    "all companies, one metric (q18)": """
        SELECT name, value FROM (
            SELECT c.name, ff.value, ROW_NUMBER() OVER (PARTITION BY c.cik ORDER BY ff.ddate DESC) AS rn
            FROM companies c JOIN filings f ON f.cik = c.cik JOIN financial_facts ff ON ff.adsh = f.adsh
            WHERE ff.tag = 'Assets' AND ff.qtrs = 0) t
        WHERE rn = 1 ORDER BY value DESC LIMIT 3""",
}
INDEXES = open("sql/indexes.sql").read()
DROP = "DROP INDEX IF EXISTS filings_cik_idx, financial_facts_tag_qtrs_ddate_idx"


def time_ms(cur, sql):
    runs = []
    for _ in range(7):
        cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql)
        runs.append(cur.fetchone()[0][0]["Execution Time"])
    return statistics.median(runs)


with psycopg.connect(DB, autocommit=True) as conn:
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM financial_facts")
    print(f"{DB}: {cur.fetchone()[0]:,} facts")
    cur.execute(DROP); cur.execute("ANALYZE")
    before = {name: time_ms(cur, q) for name, q in QUERIES.items()}
    cur.execute(INDEXES); cur.execute("ANALYZE")
    after = {name: time_ms(cur, q) for name, q in QUERIES.items()}
    print(f"{'query':<34} {'before ms':>10} {'after ms':>10}")
    for name in QUERIES:
        print(f"{name:<34} {before[name]:>10.2f} {after[name]:>10.2f}")
