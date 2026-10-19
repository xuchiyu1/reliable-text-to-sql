DROP TABLE IF EXISTS financial_facts;
DROP TABLE IF EXISTS filings;
DROP TABLE IF EXISTS companies;

CREATE TABLE companies (
    cik INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    ticker TEXT,
    sic INTEGER NOT NULL,
    countryba TEXT NOT NULL
);

CREATE TABLE filings (
    adsh  TEXT    PRIMARY KEY,
    cik   INTEGER NOT NULL REFERENCES companies(cik),
    form  TEXT    NOT NULL,
    fy    INTEGER NOT NULL,
    fp    TEXT    NOT NULL,
    filed DATE    NOT NULL
);
CREATE TABLE financial_facts(
    adsh  TEXT    NOT NULL REFERENCES filings(adsh),
    tag   TEXT    NOT NULL,
    version TEXT    NOT NULL,
    ddate DATE    NOT NULL,
    qtrs INTEGER NOT NULL,
    uom TEXT NOT NULL,
    value NUMERIC NOT NULL,
    PRIMARY KEY (adsh, tag, version, ddate, qtrs, uom)
);
