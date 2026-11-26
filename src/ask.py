import os
import sys
import time
import anthropic

from dotenv import load_dotenv
load_dotenv(override=True)        # let the key in .env override an old key already in the environment
load_dotenv()                     # read ANTHROPIC_API_KEY from .env
client = anthropic.Anthropic()

from databases import DEFAULT_DB, system_prompt   # after load_dotenv, so settings see .env
from grader import sql_from_reply

# which model and effort to use; set them from the shell to compare models, e.g. MODEL=claude-opus-5-5
MODEL = os.environ.get("MODEL", "claude-haiku-5-5")
EFFORT = os.environ.get("EFFORT", "medium")   # medium is the default for both Haiku 5.5 and Opus 5.5; set it explicitly so runs are comparable

# How Claude returns the SQL (V1.3 step 2b). "text": the whole reply is the SQL. "json": structured output,
# the reply must be {"sql": "..."}, so nothing can be written around the SQL (stray tags, placeholders).
# Set SQL_OUTPUT=json or text in the shell to compare them.
SQL_OUTPUT = os.environ.get("SQL_OUTPUT", "json")   # default json since the 2026-11-26 A/B (0 repairs with either schema source)
SQL_FORMAT = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "sql": {"type": "string",
                    "description": "One SQL SELECT statement, or exactly CANNOT_ANSWER"},
        },
        "required": ["sql"],
        "additionalProperties": False,
    },
}

# running totals over every API call in this process (evaluate.py reads them to report cost and latency)
USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0}

def call_claude(messages, db=DEFAULT_DB):
    start = time.perf_counter()
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system_for(db),
        messages=messages,
        output_config=output_config(),
    )
    USAGE["calls"] += 1
    USAGE["input_tokens"] += response.usage.input_tokens
    USAGE["output_tokens"] += response.usage.output_tokens    # includes thinking tokens, which are billed as output
    USAGE["seconds"] += time.perf_counter() - start
    if response.stop_reason == "refusal":   # refused by safety rules, so return no SQL
        return None
    # the reply may have several content blocks (e.g. thinking); keep only the text
    text = "".join(b.text for b in response.content if b.type == "text")
    return sql_from_reply(text) if SQL_OUTPUT == "json" else text

def output_config():
    config = {"effort": EFFORT}
    if SQL_OUTPUT == "json":
        config["format"] = SQL_FORMAT
    return config

# one system prompt per database (dialect line + schema + rules), built once and reused
PROMPTS = {}

def system_for(db):
    if db not in PROMPTS:
        PROMPTS[db] = system_prompt(db)
    return PROMPTS[db]

def ask(question, db=DEFAULT_DB):
    return call_claude([{"role": "user", "content": question}], db)

def fix(question, bad_sql, error, db=DEFAULT_DB):
    # send the failing SQL and the database error back to Claude to fix
    return call_claude([
        {"role": "user", "content": question},                  # the original question
        {"role": "assistant", "content": bad_sql},              # the SQL Claude wrote last time
        {"role": "user", "content": f"That SQL failed with this error:\n{error}\nReturn only the corrected SQL."},
    ], db)

if __name__ == "__main__":
    question = sys.argv[1]       # the English question typed in the terminal
    print(ask(question))