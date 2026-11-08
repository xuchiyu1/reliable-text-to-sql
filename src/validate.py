# Safety layer 2: check Claude's SQL before it runs (requirements §6)
import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"companies", "filings", "financial_facts"}
FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create)   # statements that change data
BANNED_FUNCS = {"pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "lo_import", "dblink",
                "current_setting", "set_config"}   # can hang the database, read server files, or read/change settings

def validate(sql):
    """Return None if the SQL is allowed, otherwise the reason it was blocked."""
    try:
        trees = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        return f"cannot parse SQL: {e}"
    trees = [t for t in trees if t is not None]      # a trailing semicolon can add an empty statement
    if len(trees) != 1:
        return "only one statement is allowed"       # stops "SELECT ...; DROP ..."
    tree = trees[0]
    if not isinstance(tree, exp.Query):              # SELECT, WITH...SELECT and UNION are all Query
        return "only SELECT is allowed"
    if tree.find(*FORBIDDEN):                        # catches a DELETE hidden in a subquery
        return "data-changing statement inside query"
    for func in tree.find_all(exp.Anonymous):             # sqlglot puts functions it doesn't know under Anonymous
        if func.name.lower() in BANNED_FUNCS:
            return f"function not allowed: {func.name}"
    cte_names = {cte.alias for cte in tree.find_all(exp.CTE)}   # names defined in WITH are allowed too
    for table in tree.find_all(exp.Table):
        if table.db and table.db != "public":            # only the public schema; blocks other_schema.companies
            return f"schema not allowed: {table.db}"
        if table.name not in ALLOWED_TABLES | cte_names:
            return f"table not allowed: {table.name}"
    return None
MAX_ROWS = 1000   # avoid returning huge results that blow up memory and tokens

def add_limit(sql):
    """Append LIMIT 1000 if the SQL has no LIMIT; leave it unchanged otherwise."""
    tree = sqlglot.parse_one(sql, read="postgres")
    if tree.args.get("limit") is None:
        tree = tree.limit(MAX_ROWS)
    return tree.sql(dialect="postgres")
