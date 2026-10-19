# Schema v0.2

## Changelog
- v0.2 (2026-10-18): real 2025Q4 data has an 8-field NUM key (`segments` added); V1 imports only rows with empty `segments` and empty `coreg`, so financial_facts drops both and uses a 6-field PK; companies gets `ticker` for name matching. See `requirements.md` §8–9.
- v0.1 (2026-10-16): first design, 3 tables.

## 1. Source datasets (SEC FSDS)
| Dataset | One row = | Unique key |
|---|---|---|
| SUB | one filing | adsh |
| NUM | 财报里具体内容数字 | adsh, tag, version, ddate, qtrs, uom, segments, coreg |
| TAG | 一个标签的解释 | tag, version |
| PRE | 报表上的一行字 | adsh, report, line |

## 2. Why each NUM key field matters
- ddate: without it, these two rows get confused: 2025 年的营收 和 2024 年的营收
- qtrs: without it, these two rows get confused: 季度的营收 和 年度的营收
- segments: without it, these rows get confused: 公司总营收 和 按产品线/地区拆分的营收
- coreg: without it, these rows get confused: 整个集团的营收 和 子公司的营收

## 3. V0.2 tables
### companies
One row = one company (split from SUB to remove repeated company info)

| column | meaning |
|---|---|
| cik | 公司编号 |
| name | 公司名（最新一份财报里的正式名称） |
| ticker | 股票代码（如 NVDA），用来匹配用户说的简称 |
| sic | 行业代码 |
| countryba | 公司所在国家 |

- PK: cik

### filings
One row = one filing (from SUB)

| column | meaning |
|---|---|
| adsh | 财报编号 |
| cik | 公司编号 |
| form | 财报类型（10-K 年报 / 10-Q 季报） |
| fy | 财年 |
| fp | 财期（FY / Q1 / Q2 / Q3） |
| filed | 提交日期 |

- PK: adsh
- FK: cik → companies.cik

### financial_facts
One row = one company-level number in a filing (from NUM, only rows with empty `segments` and empty `coreg`)

| column | meaning |
|---|---|
| adsh | 财报编号 |
| tag | 指标标签（如 Revenues） |
| version | 标签来源版本 |
| ddate | 截止日期 |
| qtrs | 统计季度数 |
| uom | 单位 |
| value | 数值 |

- PK: (adsh, tag, version, ddate, qtrs, uom)
- FK: adsh → filings.adsh

## 4. Relationships
- companies 1 — N filings (via cik)
- filings 1 — N financial_facts (via adsh)
