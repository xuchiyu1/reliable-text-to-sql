# Schema v0.1

## 1. Source datasets (SEC FSDS)
| Dataset | One row = | Unique key |
|---|---|---|
| SUB | one filing | adsh |
| NUM | 财报里具体内容数字 | adsh, tag, version, ddate, qtrs, uom, coreg |
| TAG | 一个标签的解释 | tag, version |
| PRE | 报表上的一行字 | adsh, report, line |

## 2. Why each NUM key field matters
- ddate: without it, these two rows get confused: 2025 年的营收 和 2024 年的营收
- qtrs: without it, these two rows get confused: 季度的营收 和 年度的营收

## 3. V0.1 tables
### companies
One row = one company (split from SUB to remove repeated company info)

| column | meaning |
|---|---|
| cik | 公司编号 |
| name | 公司名 |
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
One row = one number in a filing (from NUM)

| column | meaning |
|---|---|
| adsh | 财报编号 |
| tag | 指标标签（如 Revenues） |
| version | 标签来源版本 |
| ddate | 截止日期 |
| qtrs | 统计季度数 |
| uom | 单位 |
| coreg | 子公司（空 = 整个集团） |
| value | 数值 |

- PK: (adsh, tag, version, ddate, qtrs, uom, coreg)
- FK: adsh → filings.adsh

## 4. Relationships
- companies 1 — N filings (via cik)
- filings 1 — N financial_facts (via adsh)