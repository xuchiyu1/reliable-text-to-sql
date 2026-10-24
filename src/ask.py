import sys
import anthropic

from dotenv import load_dotenv
load_dotenv(override=True)        # 用 .env 里的 key 覆盖系统里已有的旧 key
load_dotenv()                     # 从 .env 读取 ANTHROPIC_API_KEY
client = anthropic.Anthropic()

# 把你写的 schema.md 整份交给 Claude，它只能靠这份说明来写 SQL
SCHEMA = open("docs/schema.md", encoding="utf-8").read()

SYSTEM = f"""You translate questions into PostgreSQL queries for this database.

{SCHEMA}

Metric glossary (use these tags):
- Revenue: tag IN ('RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'RevenueFromContractWithCustomerIncludingAssessedTax')
- Net income: tag = 'NetIncomeLoss'
- Total assets: tag = 'Assets'
- Quarterly values use qtrs = 1; balance sheet values use qtrs = 0.
- Do NOT use tags that only contain the word Revenue, such as CostOfRevenue or DeferredRevenue.

Rules:
- Return only one SQL SELECT statement. No explanation, no markdown.
- Use only the tables and columns described above.
- Match companies by name using ILIKE (e.g. c.name ILIKE '%masimo%'). The ticker column may be NULL.
"""



def ask(question):
    response = client.messages.create(
        model="claude-haiku-5-5",     # 开发期用最便宜的模型；以后做 Opus 对比实验
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": question}],
    )
    if response.stop_reason == "refusal":   # 被安全规则拒绝了，就不返回 SQL
        return None
    # 回复里可能有好几块内容，只取文字部分
    return "".join(b.text for b in response.content if b.type == "text")

if __name__ == "__main__":
    question = sys.argv[1]       # 终端里输入的那句英文问题
    print(ask(question))