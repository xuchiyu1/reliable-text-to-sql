# Eval cases

## q01
- Type: single value
- Question: What was Masimo's revenue in its latest quarter?
- Expected: 371500000.0000
- Trap: Masimo uses RevenueFromContractWithCustomerExcludingAssessedTax, not Revenues

```sql
SELECT ff.value
FROM companies c
JOIN filings f          ON f.cik   = c.cik
JOIN financial_facts ff ON ff.adsh = f.adsh
WHERE c.name   = 'MASIMO CORP'
  AND ff.tag   = 'RevenueFromContractWithCustomerExcludingAssessedTax'
  AND ff.ddate = '2025-09-30'
  AND ff.qtrs  = 1;
```

## q02
- Type: single value (balance sheet)
- Question: What were Medtronic's total assets at the latest period end?
- Expected: 91346000000.0000
- Trap: qtrs = 0 (point in time); Medtronic's latest period ends 2025-10-31

```sql
SELECT ff.value
FROM companies c
JOIN filings f          ON f.cik   = c.cik
JOIN financial_facts ff ON ff.adsh = f.adsh
WHERE c.name   = 'MEDTRONIC PLC'
  AND ff.tag   = 'Assets'
  AND ff.ddate = '2025-10-31'
  AND ff.qtrs  = 0;
```
