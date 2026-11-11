# Scale test for Step 4: load EVERY company's 10-K/10-Q numbers from the 2025Q4 package (not just
# the 20 medical-device companies) into a separate database, so index timings mean something.
# Usage: createdb sec_fsds_scale && psql -d sec_fsds_scale -f sql/create_tables.sql
#        python src/load_scale.py
import os
import pandas as pd
import psycopg

RAW = "data/raw/2025q4"
DB = os.environ.get("SCALE_DATABASE_URL", "dbname=sec_fsds_scale")
FORMS = ["10-K", "10-Q"]


def ymd(col):
    # "20250930" -> "2025-09-30", the text form PostgreSQL's COPY accepts for DATE
    return col.str[:4] + "-" + col.str[4:6] + "-" + col.str[6:8]


def main():
    sub = pd.read_csv(f"{RAW}/sub.txt", sep="\t", dtype=str)
    sub = sub[sub["form"].isin(FORMS) & sub["sic"].notna()]
    companies = sub.drop_duplicates("cik")[["cik", "name", "sic", "countryba"]].fillna({"countryba": ""})

    with psycopg.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("TRUNCATE financial_facts, filings, companies")
        # COPY streams rows in bulk: much faster than one INSERT per row (load_data.py's way)
        with cur.copy("COPY companies (cik, name, ticker, sic, countryba) FROM STDIN") as cp:
            for r in companies.itertuples():
                cp.write_row((int(r.cik), r.name, None, int(r.sic), r.countryba))
        with cur.copy("COPY filings (adsh, cik, form, fy, fp, filed) FROM STDIN") as cp:
            for r in sub.itertuples():
                cp.write_row((r.adsh, int(r.cik), r.form, int(r.fy) if pd.notna(r.fy) else 0,
                              r.fp if pd.notna(r.fp) else "", ymd(pd.Series([r.filed]))[0]))
        adsh = set(sub["adsh"])
        total = 0
        with cur.copy("COPY financial_facts (adsh, tag, version, ddate, qtrs, uom, value) FROM STDIN") as cp:
            for chunk in pd.read_csv(f"{RAW}/num.txt", sep="\t", dtype=str, chunksize=500_000):
                chunk = chunk[chunk["adsh"].isin(adsh) & chunk["segments"].isna()
                              & chunk["coreg"].isna() & chunk["value"].notna()]
                chunk = chunk.drop_duplicates(["adsh", "tag", "version", "ddate", "qtrs", "uom"])
                chunk["ddate"] = ymd(chunk["ddate"])
                for r in chunk[["adsh", "tag", "version", "ddate", "qtrs", "uom", "value"]].itertuples(index=False):
                    cp.write_row(r)
                total += len(chunk)
        cur.execute("ANALYZE")      # refresh planner statistics after a bulk load
    print(f"companies {len(companies)}, filings {len(sub)}, facts {total}")


if __name__ == "__main__":
    main()
