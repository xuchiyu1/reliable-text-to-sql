from datetime import date
from decimal import Decimal

import pytest
from grader import clean_sql, numbers, row_matches, is_correct


def test_clean_sql_strips_code_fence():
    assert clean_sql("```sql\nSELECT 1\n```") == "SELECT 1"

def test_clean_sql_leaves_plain_sql():
    assert clean_sql("  SELECT 1  ") == "SELECT 1"

def test_numbers_ignores_text_and_dates():
    rows = [("MASIMO CORP", date(2025, 9, 30), Decimal("371500000"), 2)]
    assert numbers(rows) == [371500000.0, 2.0]

def test_decimal_and_percent_both_match():
    assert row_matches((0.0821,), (8.21,))

def test_within_tolerance_matches():
    assert row_matches((1000,), (1000.5,))

def test_outside_tolerance_fails():
    assert not row_matches((1000,), (1002,))

def test_row_count_mismatch_is_wrong():
    assert not is_correct([(1,), (2,)], [(1,)])

def test_unordered_ignores_row_order():
    assert is_correct([(1,), (2,)], [(2,), (1,)])

def test_ordered_requires_same_order():
    assert not is_correct([(1,), (2,)], [(2,), (1,)], ordered=True)

def test_extra_columns_are_ok():
    assert is_correct([(100,)], [("NVDA", 100)])

@pytest.mark.xfail(reason="known gap: unordered check doesn't count duplicates")
def test_duplicate_value_not_double_counted():
    assert not is_correct([(1,), (1,)], [(1,), (2,)])