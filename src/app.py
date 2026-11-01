# 用户入口：python src/app.py "问题"，按 需求第 5 节 输出一段能读懂的回答
import sys
from datetime import date
import sqlglot
from evaluate import answer

SOURCE = "Source: SEC Financial Statement Data Sets, 2025Q4 (20 medical-device companies)."

def column_names(sql, n):
    """从 SQL 里读出每一列的名字；读不出的（比如 COUNT(*)）用 col1、col2 代替"""
    names = [e.alias_or_name for e in sqlglot.parse_one(sql, read="postgres").selects]
    names = [x if x and x != "*" else f"col{i + 1}" for i, x in enumerate(names)]
    return names if len(names) == n else [f"col{i + 1}" for i in range(n)]

def respond(question):
    try:
        sql, rows, fixes = answer(question)
    except Exception as e:                    # 修正 2 次还是失败，或者被 validator 拦下
        return f"Sorry, I could not build a safe, working query for this question.\n(reason: {str(e).splitlines()[0]})"
    if rows is None:                          # Claude 回答了 CANNOT_ANSWER
        return ("This question can't be answered from the financial statement data "
                "(it has no stock prices, forecasts, or filing text).")
    if not rows:                              # 空结果 ≠ 0
        return f"No matching data was found. This means the data is missing, not that the value is 0.\nSQL: {sql}\n{SOURCE}"
    names = column_names(sql, len(rows[0]))
    lines = [" | ".join(names)]
    lines += [" | ".join(str(v) for v in row) for row in rows[:20]]   # 最多显示 20 行
    if len(rows) > 20:
        lines.append(f"... ({len(rows)} rows in total)")
    periods = sorted({str(v) for row in rows for v in row if isinstance(v, date)})
    if periods:                               # 结果里带日期的话，说明是哪个时期
        lines.append("Period end: " + ", ".join(periods))
    lines += [f"SQL: {sql}", SOURCE]
    return "\n".join(lines)

if __name__ == "__main__":
    print(respond(sys.argv[1]))