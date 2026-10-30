from decimal import Decimal
import psycopg
from ask import ask, fix     # 用你写的 ask() 去问 Claude，fix() 用来修正报错的 SQL       # 用你写的 ask() 去问 Claude

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
    {"id": "q04",
     "question": "What was Masimo's net margin in its latest quarter?",
     "gold": """SELECT ni.value / rev.value FROM companies c
                JOIN filings f           ON f.cik    = c.cik
                JOIN financial_facts ni  ON ni.adsh  = f.adsh
                JOIN financial_facts rev ON rev.adsh = f.adsh
                                        AND rev.ddate = ni.ddate AND rev.qtrs = ni.qtrs
                WHERE c.name = 'MASIMO CORP'
                  AND ni.tag  = 'NetIncomeLoss'
                  AND rev.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'
                  AND ni.qtrs = 1 AND ni.ddate = '2025-09-30'"""},
    {"id": "q05", "ordered": True,
     "question": "Rank Medtronic, Boston Scientific, Stryker, Dexcom, and Masimo by revenue in their latest quarter.",
     "gold": """SELECT name, value FROM (
                    SELECT c.name, ff.value,
                           ROW_NUMBER() OVER (PARTITION BY c.cik ORDER BY ff.ddate DESC) AS rn
                    FROM companies c
                    JOIN filings f          ON f.cik   = c.cik
                    JOIN financial_facts ff ON ff.adsh = f.adsh
                    WHERE c.name IN ('MEDTRONIC PLC', 'BOSTON SCIENTIFIC CORP', 'STRYKER CORP',
                                     'DEXCOM INC', 'MASIMO CORP')
                      AND ff.tag IN ('RevenueFromContractWithCustomerExcludingAssessedTax',
                                     'Revenues',
                                     'RevenueFromContractWithCustomerIncludingAssessedTax')
                      AND ff.qtrs = 1
                ) t
                WHERE rn = 1            -- 每家公司只留最新的那一期
                ORDER BY value DESC"""},
    {"id": "q06", "refuse": True,
     "question": "What is Masimo's stock price today?"},   # 数据里没有股价，应该拒答
    {"id": "q07",
     "question": "What was Masimo's total revenue for the first nine months of 2025?",
     "gold": """SELECT ff.value FROM companies c
                JOIN filings f          ON f.cik   = c.cik
                JOIN financial_facts ff ON ff.adsh = f.adsh
                WHERE c.name = 'MASIMO CORP'
                  AND ff.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'
                  AND ff.qtrs = 3                    -- 前三季度累计，不是单季
                  AND ff.ddate = '2025-09-30'"""},
    {"id": "q08",
     "question": "How much did Dexcom spend on research and development in its latest quarter?",
     "gold": """SELECT ff.value FROM companies c
                JOIN filings f          ON f.cik   = c.cik
                JOIN financial_facts ff ON ff.adsh = f.adsh
                WHERE c.name = 'DEXCOM INC'
                  AND ff.tag = 'ResearchAndDevelopmentExpense'   -- 词典里没有这个指标
                  AND ff.qtrs = 1
                  AND ff.ddate = '2025-09-30'"""},
    {"id": "q09", "refuse": True,
     "question": "Who is the CEO of Masimo?"},                            # 数据里没有人名
    {"id": "q10", "refuse": True,
     "question": "What is Dexcom's market share in glucose monitors?"},   # 没有市场份额数据
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

def row_matches(gold_row, pred_row):
    # 一行对一行：标准答案这一行的每个数字，都要在 Claude 对应那一行里找到
    pred_nums = numbers([pred_row])
    for g in numbers([gold_row]):
        candidates = [g, g * 100]          # 小数或百分比都算对
        if not any(abs(c - p) <= abs(c) * 0.001 for c in candidates for p in pred_nums):
            return False
    return True

def is_correct(gold_rows, pred_rows, ordered=False):
    if len(gold_rows) != len(pred_rows):   # 行数不同，肯定不对
        return False
    if ordered:
        # 排名题：第 1 行对第 1 行、第 2 行对第 2 行……顺序必须一致（需求第 5 题第 3 条）
        return all(row_matches(g, p) for g, p in zip(gold_rows, pred_rows))
    # 非排名题：不管顺序，标准答案里的每个数都能在结果里找到就算对
    pred_nums = numbers(pred_rows)
    for g in numbers(gold_rows):
        candidates = [g, g * 100]
        if not any(abs(c - p) <= abs(c) * 0.001 for c in candidates for p in pred_nums):
            return False
    return True
MAX_FIXES = 2   # 最多让 Claude 改 2 次（需求第 7 题：自动修正最多 2 次）
RUNS = 3
  # LLM 每次输出不一样，同一道题跑 3 次看稳不稳定

def answer(question):
    # 问 Claude；如果 SQL 报错，就把错误发回去让它改，最多改 MAX_FIXES 次
    sql = clean_sql(ask(question) or "")
    for attempt in range(MAX_FIXES + 1):
        try:
            return sql, run_sql(sql), attempt           # 能跑通就返回：SQL、结果、改了几次
        except Exception as e:
            if attempt == MAX_FIXES:                    # 改够次数了还是错，就放弃
                raise
            sql = clean_sql(fix(question, sql, str(e)) or "")
if __name__ == "__main__":
    wins = {case["id"]: 0 for case in CASES}   # 记录每题 3 次里通过了几次
    for run in range(RUNS):
        for case in CASES:
            if case.get("refuse"):
                # 拒答题：Claude 应该回答 CANNOT_ANSWER，而不是硬写一条 SQL（需求第 5 节第 5 条）
                reply = ask(case["question"]) or ""
                ok = "CANNOT_ANSWER" in reply
                fixes = 0
            else:
                gold_rows = run_sql(case["gold"])
                try:
                    sql, pred_rows, fixes = answer(case["question"])
                    ok = is_correct(gold_rows, pred_rows, case.get("ordered", False))
                    if not ok:
                        print("  SQL:", sql)   # 答错时打印 Claude 写的 SQL，方便找原因
                except Exception as e:
                    print(case["id"], "ERROR:", str(e).splitlines()[0])
                    ok = False
                    fixes = MAX_FIXES
            wins[case["id"]] += ok
            print(f"run {run + 1}", case["id"], "PASS" if ok else "FAIL", f"(fixes: {fixes})")

    for case_id, n in wins.items():
        print(case_id, f"{n}/{RUNS}")                  # 例如 q07 2/3 = 不稳定
    total = sum(wins.values())
    print(f"accuracy: {total}/{len(CASES) * RUNS}")