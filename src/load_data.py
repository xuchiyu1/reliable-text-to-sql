import pandas as pd
import psycopg
from decimal import Decimal

RAW = "data/raw/2025q4"
SIC_CODES = [3845, 3841]
FORMS = ["10-K", "10-Q"]

def load_sub():
    sub = pd.read_csv(f"{RAW}/sub.txt", sep="\t", dtype=str)
        # TODO 1
    sub = sub[ pd.to_numeric(sub["sic"]).isin(SIC_CODES) ]
    # TODO 2
    sub = sub[ sub["form"].isin(FORMS) ]
    return sub
def load_num(adsh_list):
    parts = []
    for chunk in pd.read_csv(f"{RAW}/num.txt", sep="\t", dtype=str, chunksize=200_000):
        chunk = chunk[ chunk["adsh"].isin(adsh_list) ]   # 空 1：函数的参数名
        chunk = chunk[ chunk["segments"].isna() ]   # 空 2：为空，用 isna 还是 notna？
        chunk = chunk[ chunk["coreg"].isna() ]      # 空 3：为空
        chunk = chunk[ chunk["value"].notna() ]      # 空 4：不为空
        parts.append(chunk)
    return pd.concat(parts)
TOP_N = 20
EXCLUDE_CIKS = ["66740"]   # 3M：综合集团，不算纯医疗器械公司
DB = "dbname=sec_fsds"
def pick_top_companies(sub, num):
    
    # 1. 只留 tag 是 Assets 的行
    assets = num[ num["tag"] == "Assets" ]
    # 2. 加上 cik 列（num 里只有 adsh，cik 在 sub 里）
    assets = assets.merge(sub[["adsh", "cik"]], on="adsh")
    # 3. value 转成数字，才能比大小
    assets["value"] = pd.to_numeric(assets["value"])
    # 4. 每家公司只留最新一期
    assets = assets.sort_values("ddate").groupby("cik").tail(1)
    # 5. 去掉排除名单里的公司
    assets = assets[ ~assets["cik"].isin(EXCLUDE_CIKS) ]
    # 6. 按总资产从大到小排，取前 TOP_N 家
    assets = assets.sort_values("value", ascending=False).head(TOP_N)
    return assets["cik"]
   

def to_date(s):
    # "20250930" → 日期类型，数据库的 DATE 列需要它
    return pd.to_datetime(s, format="%Y%m%d").date()

def write_db(sub, num):
    with psycopg.connect(DB) as conn:
        cur = conn.cursor()

        # 第 4 步：清空 3 张表，让脚本可以重复运行
        cur.execute("TRUNCATE financial_facts, filings, companies")

        # 第 5a 步：companies（一家公司一行）
        for _, r in sub.drop_duplicates("cik").iterrows():
            cur.execute(
                "INSERT INTO companies (cik, name, ticker, sic, countryba) VALUES (%s, %s, %s, %s, %s)",
                (int(r["cik"]), r["name"], None, int(r["sic"]), r["countryba"]),
            )

        # 第 5b 步：filings（一份财报一行）
        for _, r in sub.iterrows():
            cur.execute(
                "INSERT INTO filings (adsh, cik, form, fy, fp, filed) VALUES (%s, %s, %s, %s, %s, %s)",
                (r["adsh"], int(r["cik"]), r["form"], int(r["fy"]), r["fp"], to_date(r["filed"])),
            )

        # 第 5c 步：financial_facts（一个数字一行）
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
    write_db(sub, num)