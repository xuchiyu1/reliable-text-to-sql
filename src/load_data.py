import pandas as pd

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
if __name__ == "__main__":
    
    sub = load_sub()
    print("filings:", len(sub))
    print("companies:", sub["cik"].nunique())
    num = load_num(sub["adsh"])
    print("facts:", len(num))
    print( num["tag"].value_counts().head(10) )