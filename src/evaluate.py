from decimal import Decimal
import psycopg
from ask import ask          # 用你写的 ask() 去问 Claude

DB = "dbname=sec_fsds"

# 评测题：问题 + 你手写的标准答案 SQL（和 cases.md 里的一样）
CASES = [
    {"id": "q01",
     "question": "What was Masimo's revenue in its latest quarter?",
     "gold": """SELECT ff.value FROM companies c
                JOIN filings f ON f.cik = c.cik
                JOIN financial_facts ff ON ff.adsh = f.adsh
                WHERE c.name = 'MASIMO CORP'
                  AND ff.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'
                  AND ff.ddate = '2025-09-30' AND ff.qtrs = 1"""},
    {"id": "q02",
     "question": "What were Medtronic's total assets at the latest period end?",
     "gold": """SELECT ff.value FROM companies c
                JOIN filings f ON f.cik = c.cik
                JOIN financial_facts ff ON ff.adsh = f.adsh
                WHERE c.name = 'MEDTRONIC PLC'
                  AND ff.tag = 'Assets'
                  AND ff.ddate = '2025-10-31' AND ff.qtrs = 0"""},
    {"id": "q03",
     "question": "How much did Masimo's quarterly revenue grow year over year?",
     "gold": """SELECT (cur.value - prev.value) / prev.value FROM companies c
                JOIN filings f ON f.cik = c.cik
                JOIN financial_facts cur  ON cur.adsh  = f.adsh
                JOIN financial_facts prev ON prev.adsh = f.adsh
                                         AND prev.tag = cur.tag AND prev.qtrs = cur.qtrs
                WHERE c.name = 'MASIMO CORP'
                  AND cur.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'
                  AND cur.qtrs = 1
                  AND cur.ddate = '2025-09-30' AND prev.ddate = '2024-09-30'"""},
]

def clean_sql(text):
    # Claude 有时不听话，会加 ```sql ... ``` 包裹，这里去掉
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]      # 去掉第一行 ```sql
        text = text.rsplit("```", 1)[0]    # 去掉最后的 ```
    return text.strip()

def run_sql(sql):
    with psycopg.connect(DB) as conn:
        conn.read_only = True                         # 只读：就算 SQL 想删数据也会被拒绝
        cur = conn.cursor()
        cur.execute("SET statement_timeout = 5000")   # 最多跑 5 秒（需求第 6 题）
        cur.execute(sql)
        return cur.fetchall()

def numbers(rows):
    # 把结果里所有的数字取出来，忽略日期、文字这些列
    return [float(x) for row in rows for x in row if isinstance(x, (int, float, Decimal))]

def is_correct(gold_rows, pred_rows):
    if len(gold_rows) != len(pred_rows):              # 行数不同，肯定不对
        return False
    pred_nums = numbers(pred_rows)
    for g in numbers(gold_rows):
        # 标准答案里的每个数，都要在 Claude 的结果里找到（允许 0.1% 误差，需求第 5 题）
        if not any(abs(g - p) <= abs(g) * 0.001 for p in pred_nums):
            return False
    return True

if __name__ == "__main__":
    passed = 0
    for case in CASES:
        pred_sql = clean_sql(ask(case["question"]) or "")   # 1. 问 Claude
        gold_rows = run_sql(case["gold"])                   # 2. 跑标准答案
        try:
            pred_rows = run_sql(pred_sql)                   # 3. 跑 Claude 的 SQL
            ok = is_correct(gold_rows, pred_rows)           # 4. 比对
        except Exception as e:
            print(case["id"], "ERROR:", e)                  # SQL 写错了也算失败
            ok = False
        passed += ok
        print(case["id"], "PASS" if ok else "FAIL")
    print(f"accuracy: {passed}/{len(CASES)}")