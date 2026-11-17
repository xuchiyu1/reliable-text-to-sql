import os
import pandas as pd
import psycopg
import json
from decimal import Decimal

# SEC packages are grouped by FILING date: 2025q3 = filed Jul-Sep (Q2 10-Qs), 2025q4 = filed Oct-Dec (Q3 10-Qs).
# Loading both gives each company 2 quarter ends, so quarter-over-quarter questions become answerable.
RAWS = ["data/raw/2025q3", "data/raw/2025q4"]   # oldest first; the last one picks the companies
SIC_CODES = [3845, 3841]
FORMS = ["10-K", "10-Q"]
def load_tickers():
    # SEC's official CIK -> ticker map
    # File format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    with open("data/raw/company_tickers.json") as f:
        data = json.load(f)
    # our cik is a string (dtype=str), so convert cik_str to a string too so they match
    return {str(row["cik_str"]): row["ticker"] for row in data.values()}
def load_sub(raw):
    sub = pd.read_csv(f"{raw}/sub.txt", sep="\t", dtype=str)
        # keep medical-device SIC codes only
    sub = sub[ pd.to_numeric(sub["sic"]).isin(SIC_CODES) ]
    # keep 10-K / 10-Q filings only
    sub = sub[ sub["form"].isin(FORMS) ]
    return sub
def load_num(raw, adsh_list):
    parts = []
    for chunk in pd.read_csv(f"{raw}/num.txt", sep="\t", dtype=str, chunksize=200_000):
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

        # companies (one row per company; name and address from its most recent filing)
        for _, r in sub.sort_values("filed").drop_duplicates("cik", keep="last").iterrows():
            cur.execute(
                "INSERT INTO companies (cik, name, ticker, sic, countryba) VALUES (%s, %s, %s, %s, %s)",
                (int(r["cik"]), r["name"], tickers.get(r["cik"]), int(r["sic"]), r["countryba"]),
            )

        # filings (one row per filing)
        for _, r in sub.iterrows():
            cur.execute(
                "INSERT INTO filings (adsh, cik, form, fy, fp, filed) VALUES (%s, %s, %s, %s, %s, %s)",
                (r["adsh"], int(r["cik"]), r["form"], int(r["fy"]) if pd.notna(r["fy"]) else 0, r["fp"] if pd.notna(r["fp"]) else "", to_date(r["filed"])),
            )

        # financial_facts (one row per number)
        for _, r in num.iterrows():
            cur.execute(
                "INSERT INTO financial_facts (adsh, tag, version, ddate, qtrs, uom, value) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (r["adsh"], r["tag"], r["version"], to_date(r["ddate"]), int(r["qtrs"]), r["uom"], Decimal(r["value"])),
            )
if __name__ == "__main__":
    # 1. pick the companies from the latest package (same 20 companies as V1.1, so the eval still applies)
    latest_sub = load_sub(RAWS[-1])
    latest_num = load_num(RAWS[-1], latest_sub["adsh"])
    top = pick_top_companies(latest_sub, latest_num)
    print("top:", latest_sub[latest_sub["cik"].isin(top)]["name"].unique())

    # 2. load those companies' filings and numbers from every package
    subs, nums = [], []
    for raw in RAWS:
        sub = latest_sub if raw == RAWS[-1] else load_sub(raw)
        sub = sub[ sub["cik"].isin(top) ]
        num = latest_num if raw == RAWS[-1] else load_num(raw, sub["adsh"])
        num = num[ num["adsh"].isin(sub["adsh"]) ]
        print(f"{raw}: filings {len(sub)}, facts {len(num)}")
        subs.append(sub)
        nums.append(num)
    sub = pd.concat(subs).drop_duplicates("adsh")   # a filing is in exactly one package; this is a guard
    num = pd.concat(nums)
    print("total: filings", len(sub), "facts", len(num))

    # 3. write everything. The same number can now appear in 2 filings (e.g. the prior year-end balance
    #    sheet in both the Q2 and Q3 10-Q); both rows are kept, and the latest_facts view picks one.
    tickers = load_tickers()
    write_db(sub, num, tickers)
