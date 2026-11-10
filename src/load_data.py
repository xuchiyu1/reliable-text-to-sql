import os
import pandas as pd
import psycopg
import json
from decimal import Decimal

RAW = "data/raw/2025q4"
SIC_CODES = [3845, 3841]
FORMS = ["10-K", "10-Q"]
def load_tickers():
    # SEC's official CIK -> ticker map
    # File format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    with open("data/raw/company_tickers.json") as f:
        data = json.load(f)
    # our cik is a string (dtype=str), so convert cik_str to a string too so they match
    return {str(row["cik_str"]): row["ticker"] for row in data.values()}
def load_sub():
    sub = pd.read_csv(f"{RAW}/sub.txt", sep="\t", dtype=str)
        # keep medical-device SIC codes only
    sub = sub[ pd.to_numeric(sub["sic"]).isin(SIC_CODES) ]
    # keep 10-K / 10-Q filings only
    sub = sub[ sub["form"].isin(FORMS) ]
    return sub
def load_num(adsh_list):
    parts = []
    for chunk in pd.read_csv(f"{RAW}/num.txt", sep="\t", dtype=str, chunksize=200_000):
        chunk = chunk[ chunk["adsh"].isin(adsh_list) ]   # selected filings only
        chunk = chunk[ chunk["segments"].isna() ]   # company totals only (no segment breakdown)
        chunk = chunk[ chunk["coreg"].isna() ]      # consolidated group only (no co-registrant)
        chunk = chunk[ chunk["value"].notna() ]      # rows that have a value
        parts.append(chunk)
    return pd.concat(parts)
TOP_N = 20
EXCLUDE_CIKS = ["66740"]   # 3M: a conglomerate, not a pure medical-device company
DB = os.environ.get("LOADER_DATABASE_URL", "dbname=sec_fsds")   # owner role, can write; Docker sets LOADER_DATABASE_URL
def pick_top_companies(sub, num):
    
    # 1. keep only rows with tag Assets
    assets = num[ num["tag"] == "Assets" ]
    # 2. add the cik column (num has only adsh; cik is in sub)
    assets = assets.merge(sub[["adsh", "cik"]], on="adsh")
    # 3. convert value to a number so it can be compared
    assets["value"] = pd.to_numeric(assets["value"])
    # 4. keep only each company's latest period
    assets = assets.sort_values("ddate").groupby("cik").tail(1)
    # 5. drop companies on the exclude list
    assets = assets[ ~assets["cik"].isin(EXCLUDE_CIKS) ]
    # 6. sort by total assets, largest first, and take the top TOP_N
    assets = assets.sort_values("value", ascending=False).head(TOP_N)
    return assets["cik"]
   

def to_date(s):
    # "20250930" -> date, needed for the DATE column
    return pd.to_datetime(s, format="%Y%m%d").date()

def write_db(sub, num, tickers):
    with psycopg.connect(DB) as conn:
        cur = conn.cursor()

        # truncate the 3 tables so the script can be re-run
        cur.execute("TRUNCATE financial_facts, filings, companies")

        # companies (one row per company)
        for _, r in sub.drop_duplicates("cik").iterrows():
            cur.execute(
                "INSERT INTO companies (cik, name, ticker, sic, countryba) VALUES (%s, %s, %s, %s, %s)",
                (int(r["cik"]), r["name"], tickers.get(r["cik"]), int(r["sic"]), r["countryba"]),
            )

        # filings (one row per filing)
        for _, r in sub.iterrows():
            cur.execute(
                "INSERT INTO filings (adsh, cik, form, fy, fp, filed) VALUES (%s, %s, %s, %s, %s, %s)",
                (r["adsh"], int(r["cik"]), r["form"], int(r["fy"]), r["fp"], to_date(r["filed"])),
            )

        # financial_facts (one row per number)
        for _, r in num.iterrows():
            cur.execute(
                "INSERT INTO financial_facts (adsh, tag, version, ddate, qtrs, uom, value) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (r["adsh"], r["tag"], r["version"], to_date(r["ddate"]), int(r["qtrs"]), r["uom"], Decimal(r["value"])),
            )
if __name__ == "__main__":
    
    sub = load_sub()
    print("filings:", len(sub))
    print("companies:", sub["cik"].nunique())
    num = load_num(sub["adsh"])
    print("facts:", len(num))
    print( num["tag"].value_counts().head(10) )
    top = pick_top_companies(sub, num)
    print("top:", sub[sub["cik"].isin(top)]["name"].unique())

    sub = sub[ sub["cik"].isin(top) ]
    num = num[ num["adsh"].isin(sub["adsh"]) ]
    print("top filings:", len(sub))
    print("top facts:", len(num))
    tickers = load_tickers()
    write_db(sub, num, tickers)
