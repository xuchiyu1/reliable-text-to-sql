# Turn a query result into what the user reads: column names and the period each number covers.
# The period is read from the columns the query actually returned (ddate, qtrs), not from model text,
# so it always matches the data that produced the answer (requirements §4).
from datetime import date
import sqlglot

# qtrs = number of quarters a number covers; 0 = balance sheet value at one point in time
LENGTH = {
    0: "as of {d}",
    1: "single quarter ended {d}",
    2: "six months ended {d}",
    3: "nine months ended {d}",
    4: "full year ended {d}",
}


def column_names(sql, n):
    """Read each column name from the SQL; use col1, col2, ... when there is none (e.g. COUNT(*))."""
    names = [e.alias_or_name for e in sqlglot.parse_one(sql, read="postgres").selects]
    names = [x if x and x != "*" else f"col{i + 1}" for i, x in enumerate(names)]
    return names if len(names) == n else [f"col{i + 1}" for i in range(n)]


def describe_periods(columns, rows):
    """List the distinct periods in a result, e.g. ["single quarter ended 2025-09-30"].

    Date columns are found by value type; qtrs columns by name. If there are as many qtrs
    columns as date columns, they are paired in order (cur_ddate with cur_qtrs, ...);
    if there is one qtrs column, it applies to every date. Returns [] when the result has no date.
    """
    if not rows:
        return []
    date_cols = [i for i in range(len(columns)) if isinstance(rows[0][i], date)]
    qtrs_cols = [i for i, name in enumerate(columns) if "qtrs" in name.lower()]
    if len(qtrs_cols) == len(date_cols):
        pairs = list(zip(date_cols, qtrs_cols))
    elif len(qtrs_cols) == 1:
        pairs = [(d, qtrs_cols[0]) for d in date_cols]
    else:                                   # can't tell which qtrs belongs to which date
        pairs = [(d, None) for d in date_cols]

    periods = []
    for row in rows:
        for d, q in pairs:
            if row[d] is None:
                continue
            qtrs = row[q] if q is not None else None
            if qtrs in LENGTH:
                text = LENGTH[qtrs].format(d=row[d])
            elif qtrs is None:
                text = f"period ended {row[d]} (length unknown)"
            else:
                text = f"{qtrs} quarters ended {row[d]}"
            if text not in periods:         # keep first-seen order, no duplicates
                periods.append(text)
    return periods


def period_line(periods, limit=5):
    """One line for the answer. Says so plainly when the result carries no period."""
    if not periods:
        return "Period: not in the result (check the SQL's ddate filter)"
    shown = periods[:limit]
    more = f" (+{len(periods) - limit} more)" if len(periods) > limit else ""
    return "Period: " + "; ".join(shown) + more
