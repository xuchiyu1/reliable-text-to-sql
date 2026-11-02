# User entry point: python src/app.py "question" prints a readable answer (requirements §7)
import sys
from datetime import date
import sqlglot
from evaluate import answer

SOURCE = "Source: SEC Financial Statement Data Sets, 2025Q4 (20 medical-device companies)."

def column_names(sql, n):
    """Read each column name from the SQL; use col1, col2, ... when there is none (e.g. COUNT(*))."""
    names = [e.alias_or_name for e in sqlglot.parse_one(sql, read="postgres").selects]
    names = [x if x and x != "*" else f"col{i + 1}" for i, x in enumerate(names)]
    return names if len(names) == n else [f"col{i + 1}" for i in range(n)]

def respond(question):
    try:
        sql, rows, fixes = answer(question)
    except Exception as e:                    # still failing after 2 repairs, or blocked by the validator
        return f"Sorry, I could not build a safe, working query for this question.\n(reason: {str(e).splitlines()[0]})"
    if rows is None:                          # Claude replied CANNOT_ANSWER
                return ("This question can't be answered from the financial statement data "
                "(it has no stock prices, forecasts, or filing text).\n"
                "You can ask about revenue, net income, assets, cash, growth or margins "
                "of the 20 medical-device companies in the 2025Q4 SEC filings.")
    if not rows:                              # empty result != 0
        return f"No matching data was found. This means the data is missing, not that the value is 0.\nSQL: {sql}\n{SOURCE}"
    names = column_names(sql, len(rows[0]))
    lines = [" | ".join(names)]
    lines += [" | ".join(str(v) for v in row) for row in rows[:20]]   # show at most 20 rows
    if len(rows) > 20:
        lines.append(f"... ({len(rows)} rows in total)")
    periods = sorted({str(v) for row in rows for v in row if isinstance(v, date)})
    if periods:                               # if the result has dates, say which period it is
        lines.append("Period end: " + ", ".join(periods))
    lines += [f"SQL: {sql}", SOURCE]
    return "\n".join(lines)

if __name__ == "__main__":
    print(respond(sys.argv[1]))