import os
import sys
import time
import anthropic

from dotenv import load_dotenv
load_dotenv(override=True)        # let the key in .env override an old key already in the environment
load_dotenv()                     # read ANTHROPIC_API_KEY from .env
client = anthropic.Anthropic()

# which model and effort to use; set them from the shell to compare models, e.g. MODEL=claude-opus-5-5
MODEL = os.environ.get("MODEL", "claude-haiku-5-5")
EFFORT = os.environ.get("EFFORT", "medium")   # medium is the default for both Haiku 5.5 and Opus 5.5; set it explicitly so runs are comparable

# running totals over every API call in this process (evaluate.py reads them to report cost and latency)
USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0}

def call_claude(messages):
    start = time.perf_counter()
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=messages,
        output_config={"effort": EFFORT},
    )
    USAGE["calls"] += 1
    USAGE["input_tokens"] += response.usage.input_tokens
    USAGE["output_tokens"] += response.usage.output_tokens    # includes thinking tokens, which are billed as output
    USAGE["seconds"] += time.perf_counter() - start
    if response.stop_reason == "refusal":   # refused by safety rules, so return no SQL
        return None
    # the reply may have several content blocks (e.g. thinking); keep only the text
    return "".join(b.text for b in response.content if b.type == "text")

# give Claude the whole schema.md; it writes SQL from this description only
SCHEMA = open("docs/schema.md", encoding="utf-8").read()

SYSTEM = f"""You translate questions into PostgreSQL queries for this database.

{SCHEMA}

Metric glossary (use these tags):
- Revenue: tag IN ('RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'RevenueFromContractWithCustomerIncludingAssessedTax')
- Net income: tag = 'NetIncomeLoss'
- Total assets: tag = 'Assets'
- Quarterly values use qtrs = 1; balance sheet values use qtrs = 0.
- Cumulative periods (first six/nine months, year to date, full fiscal year) are reported directly: use qtrs = 2, 3 or 4 at the period's end date. Never add up quarterly rows to build them: the database does not hold every quarter, so a sum can silently miss one.
- Do NOT use tags that only contain the word Revenue, such as CostOfRevenue or DeferredRevenue.
- Read numbers from latest_facts (join companies ON companies.cik = latest_facts.cik). Do not use financial_facts.
- latest_facts has several periods per company. Always filter ddate to the period you want; a company's latest period is its MAX(ddate) for that tag and qtrs.
- Prior periods are rows with an earlier ddate for the same cik, tag and qtrs: the same quarter last year is ddate - INTERVAL '1 year'; the previous quarter is the latest ddate before the current one (date arithmetic like - INTERVAL '3 months' can miss month ends). Use ddate, not fy/fp.

Rules:
- Return only one SQL SELECT statement. No explanation, no markdown.
- Use only the tables and columns described above.
- Match companies by name using ILIKE (e.g. c.name ILIKE '%masimo%'). The ticker column may be NULL.
- Whenever you return a financial value, also return the ddate and qtrs it comes from (e.g. SELECT c.name, lf.value, lf.ddate, lf.qtrs). When you compare two periods, return both: cur.ddate, cur.qtrs, prev.ddate AS prev_ddate, prev.qtrs AS prev_qtrs. The answer shown to the user states the period from these columns.
- If the question cannot be answered from these tables (for example stock prices, forecasts, or text from the filings such as risk factors), return exactly CANNOT_ANSWER and nothing else.
"""



def ask(question):
    return call_claude([{"role": "user", "content": question}])

def fix(question, bad_sql, error):
    # send the failing SQL and the database error back to Claude to fix
    return call_claude([
        {"role": "user", "content": question},                  # the original question
        {"role": "assistant", "content": bad_sql},              # the SQL Claude wrote last time
        {"role": "user", "content": f"That SQL failed with this error:\n{error}\nReturn only the corrected SQL."},
    ])

if __name__ == "__main__":
    question = sys.argv[1]       # the English question typed in the terminal
    print(ask(question))