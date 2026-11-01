# 第 1 层防线：执行前检查 Claude 写的 SQL（需求第 6 节）
import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"companies", "filings", "financial_facts"}
FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create)   # 会改数据的语句
BANNED_FUNCS = {"pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "lo_import", "dblink"}   # 卡死数据库或读服务器文件

def validate(sql):
    """通过就返回 None；不通过就返回被拦的原因"""
    try:
        trees = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        return f"cannot parse SQL: {e}"
    trees = [t for t in trees if t is not None]      # 末尾的分号可能多出一个空语句
    if len(trees) != 1:
        return "only one statement is allowed"       # 防止 "SELECT ...; DROP ..."
    tree = trees[0]
    if not isinstance(tree, exp.Query):              # SELECT、WITH...SELECT、UNION 都属于 Query
        return "only SELECT is allowed"
    if tree.find(*FORBIDDEN):                        # 防止藏在子查询里的 DELETE
        return "data-changing statement inside query"
    for func in tree.find_all(exp.Anonymous):             # sqlglot 不认识的函数都归到 Anonymous
        if func.name.lower() in BANNED_FUNCS:
            return f"function not allowed: {func.name}"
    cte_names = {cte.alias for cte in tree.find_all(exp.CTE)}   # WITH 起的临时表名也算合法
    for table in tree.find_all(exp.Table):
        if table.name not in ALLOWED_TABLES | cte_names:
            return f"table not allowed: {table.name}"
    return None
MAX_ROWS = 1000   # 防止一次查出几十万行，把内存和 token 撑爆

def add_limit(sql):
    """SQL 本身没写 LIMIT 的话，在末尾补一个 LIMIT 1000；写了就不动"""
    tree = sqlglot.parse_one(sql, read="postgres")
    if tree.args.get("limit") is None:
        tree = tree.limit(MAX_ROWS)
    return tree.sql(dialect="postgres")

if __name__ == "__main__":
    tests = [
        "SELECT name FROM companies",                                  # 应通过
        "WITH x AS (SELECT * FROM filings) SELECT * FROM x",           # 应通过（CTE）
        "DROP TABLE companies",                                        # 应拦：不是 SELECT
        "SELECT 1 FROM companies; DELETE FROM filings",                # 应拦：两条语句
        "SELECT * FROM pg_user",                                       # 应拦：系统表
        "SELECT name FROM companies WHERE pg_sleep(10) IS NULL",       # 应拦：危险函数
    ]
    for sql in tests:
        print(validate(sql) or "OK", "|", sql)