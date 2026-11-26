# V1.3 step 2: build the schema description for the prompt from the database itself,
# instead of the hand-written docs/schema.md. A team that connects a new database writes
# COMMENT ON TABLE / COLUMN there (see sql/comments.sql); this file reads:
#   - table and column names + types   from information_schema (standard SQL, also exists in MySQL)
#   - comments, primary and foreign keys from pg_catalog (Postgres system tables)
# Only the allowed tables are read, so tables the agent may not query are never shown to the model.
import psycopg

TABLES_SQL = """
SELECT t.table_name, t.table_type,
       obj_description(to_regclass(quote_ident(t.table_schema) || '.' || quote_ident(t.table_name)), 'pg_class')
FROM information_schema.tables t
WHERE t.table_schema = %s AND t.table_name = ANY(%s)
ORDER BY t.table_name
"""

COLUMNS_SQL = """
SELECT c.table_name, c.column_name, c.data_type, col_description(a.attrelid, a.attnum)
FROM information_schema.columns c
JOIN pg_attribute a
  ON a.attrelid = to_regclass(quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))
 AND a.attname = c.column_name
WHERE c.table_schema = %s AND c.table_name = ANY(%s)
ORDER BY c.table_name, c.ordinal_position
"""

# Keys come from pg_constraint, not information_schema.table_constraints: the information_schema
# views only list constraints to roles with more than SELECT on the table, and the agent connects
# as a SELECT-only role. Foreign keys pointing to a table that is not allowed are left out.
CONSTRAINTS_SQL = """
SELECT cl.relname, pg_get_constraintdef(con.oid)
FROM pg_constraint con
JOIN pg_class cl ON cl.oid = con.conrelid
JOIN pg_namespace n ON n.oid = cl.relnamespace
LEFT JOIN pg_class ref ON ref.oid = con.confrelid
WHERE n.nspname = %s AND cl.relname = ANY(%s)
  AND (con.contype = 'p' OR (con.contype = 'f' AND ref.relname = ANY(%s)))
ORDER BY cl.relname, con.contype DESC, con.conname
"""


def fetch(url, schema, tables):
    """Read tables, columns and keys of the allowed tables. Returns three lists of tuples."""
    names = sorted(tables)
    with psycopg.connect(url) as conn:
        conn.read_only = True
        cur = conn.cursor()
        cur.execute(TABLES_SQL, (schema, names))
        table_rows = cur.fetchall()
        cur.execute(COLUMNS_SQL, (schema, names))
        column_rows = cur.fetchall()
        cur.execute(CONSTRAINTS_SQL, (schema, names, names))
        key_rows = cur.fetchall()
    return table_rows, column_rows, key_rows


def format_schema(table_rows, column_rows, key_rows):
    """Turn the rows from fetch() into Markdown for the prompt (pure function, no database)."""
    lines = ["Tables you can query (read from the database):"]
    for name, table_type, comment in table_rows:
        kind = "view" if table_type == "VIEW" else "table"
        lines += ["", f"### {name} ({kind})"]
        if comment:
            lines.append(comment)
        lines += ["", "| column | type | meaning |", "|---|---|---|"]
        lines += [f"| {col} | {dtype} | {note or ''} |"
                  for table, col, dtype, note in column_rows if table == name]
        keys = [definition for table, definition in key_rows if table == name]
        if keys:
            lines.append("")
            lines += [f"- {definition}" for definition in keys]
    return "\n".join(lines) + "\n"


def describe(url, schema, tables):
    return format_schema(*fetch(url, schema, tables))


if __name__ == "__main__":
    # print the generated description for the default database, to compare with docs/schema.md
    from databases import get
    cfg = get()
    print(describe(cfg["url"], cfg["schema"], cfg["allowed_tables"]))
