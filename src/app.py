# User entry point: python src/app.py "question" prints a readable answer (requirements §7)
import sys
from evaluate import answer
from present import column_names, describe_periods, period_line

SOURCE = "Source: SEC Financial Statement Data Sets, 2025Q3 + 2025Q4 packages (20 medical-device companies)."

def respond(question):
    try:
        sql, rows, fixes = answer(question)
    except Exception as e:                    # still failing after 2 repairs, or blocked by the validator
        return f"Sorry, I could not build a safe, working query for this question.\n(reason: {str(e).splitlines()[0]})"
    if rows is None:                          # Claude replied CANNOT_ANSWER
                return ("This question can't be answered from the financial statement data "
                "(it has no stock prices, forecasts, or filing text).\n"
                "You can ask about revenue, net income, assets, cash, growth or margins "
                "of the 20 medical-device companies in the 2025Q3-2025Q4 SEC filings.")
    if not rows:                              # empty result != 0
        return f"No matching data was found. This means the data is missing, not that the value is 0.\nSQL: {sql}\n{SOURCE}"
    names = column_names(sql, len(rows[0]))
    lines = [" | ".join(names)]
    lines += [" | ".join(str(v) for v in row) for row in rows[:20]]   # show at most 20 rows
    if len(rows) > 20:
        lines.append(f"... ({len(rows)} rows in total)")
    lines.append(period_line(describe_periods(names, rows)))   # which period(s) the numbers cover
    lines += [f"SQL: {sql}", SOURCE]
    return "\n".join(lines)

if __name__ == "__main__":
    print(respond(sys.argv[1]))