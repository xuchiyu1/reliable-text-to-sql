import sys
import anthropic

from dotenv import load_dotenv
load_dotenv(override=True)        # let the key in .env override an old key already in the environment
load_dotenv()                     # read ANTHROPIC_API_KEY from .env
client = anthropic.Anthropic()

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
- If the question cannot be answered from these tables (for example stock prices, forecasts, or text from the filings such as risk factors), return exactly CANNOT_ANSWER and nothing else.
"""



def ask(question):
    response = client.messages.create(
        model="claude-haiku-5-5",     # cheapest model during development; compare with Opus later
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": question}],
    )
    if response.stop_reason == "refusal":   # refused by safety rules, so return no SQL
        return None
    # the reply may have several content blocks; keep only the text
    return "".join(b.text for b in response.content if b.type == "text")

def fix(question, bad_sql, error):
    # send the failing SQL and the database error back to Claude to fix
    response = client.messages.create(
        model="claude-haiku-5-5",
        max_tokens=16000,
        system=SYSTEM,
        messages=[
            {"role": "user", "content": question},                  # the original question
            {"role": "assistant", "content": bad_sql},              # the SQL Claude wrote last time
            {"role": "user", "content": f"That SQL failed with this error:\n{error}\nReturn only the corrected SQL."},
        ],
    )
    if response.stop_reason == "refusal":
        return None
    return "".join(b.text for b in response.content if b.type == "text")

if __name__ == "__main__":
    question = sys.argv[1]       # the English question typed in the terminal
    print(ask(question))