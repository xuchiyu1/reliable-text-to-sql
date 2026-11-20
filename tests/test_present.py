from datetime import date
from decimal import Decimal

from present import describe_periods, period_line

Q3 = date(2025, 9, 30)
Q2 = date(2025, 6, 30)


def test_value_only_has_no_period():
    assert describe_periods(["value"], [(Decimal("1209300000"),)]) == []


def test_single_quarter():
    rows = [(Decimal("1209300000"), Q3, 1)]
    assert describe_periods(["value", "ddate", "qtrs"], rows) == ["single quarter ended 2025-09-30"]


def test_balance_sheet_is_point_in_time():
    rows = [(Decimal("2402600000"), Q3, 0)]
    assert describe_periods(["value", "ddate", "qtrs"], rows) == ["as of 2025-09-30"]


def test_nine_months_and_full_year():
    assert describe_periods(["value", "ddate", "qtrs"], [(1, Q3, 3)]) == ["nine months ended 2025-09-30"]
    assert describe_periods(["value", "ddate", "qtrs"], [(1, Q3, 4)]) == ["full year ended 2025-09-30"]


def test_comparison_pairs_each_date_with_its_qtrs():
    # QoQ self-join: cur.ddate/cur.qtrs and prev.ddate/prev.qtrs, paired in order
    cols = ["change", "ddate", "qtrs", "prev_ddate", "prev_qtrs"]
    rows = [(Decimal("-585100000"), Q3, 0, Q2, 0)]
    assert describe_periods(cols, rows) == ["as of 2025-09-30", "as of 2025-06-30"]


def test_one_qtrs_column_applies_to_every_date():
    cols = ["growth", "ddate", "prev_ddate", "qtrs"]
    rows = [(0.0451, Q3, Q2, 1)]
    assert describe_periods(cols, rows) == ["single quarter ended 2025-09-30", "single quarter ended 2025-06-30"]


def test_ranking_with_same_period_is_listed_once():
    rows = [("A", Decimal("3"), Q3, 1), ("B", Decimal("2"), Q3, 1), ("C", Decimal("1"), Q3, 1)]
    assert describe_periods(["name", "value", "ddate", "qtrs"], rows) == ["single quarter ended 2025-09-30"]


def test_companies_with_different_periods_are_listed_separately():
    # fiscal years differ, so "latest quarter" can end in different months (requirements §4)
    rows = [("A", 1, Q3, 1), ("B", 2, date(2025, 8, 31), 1)]
    assert describe_periods(["name", "value", "ddate", "qtrs"], rows) == [
        "single quarter ended 2025-09-30", "single quarter ended 2025-08-31"]


def test_date_without_qtrs_says_length_unknown():
    assert describe_periods(["value", "ddate"], [(1, Q3)]) == ["period ended 2025-09-30 (length unknown)"]


def test_empty_result():
    assert describe_periods(["value"], []) == []


def test_period_line():
    assert period_line([]) == "Period: not in the result (check the SQL's ddate filter)"
    assert period_line(["as of 2025-09-30"]) == "Period: as of 2025-09-30"
    assert period_line([f"p{i}" for i in range(7)]) == "Period: p0; p1; p2; p3; p4 (+2 more)"
