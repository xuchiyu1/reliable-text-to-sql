import os
import sys
import time
import anthropic

from dotenv import load_dotenv
load_dotenv(override=True)        # let the key in .env override an old key already in the environment
load_dotenv()                     # read ANTHROPIC_API_KEY from .env
client = anthropic.Anthropic()

from databases import DEFAULT_DB, system_prompt   # after load_dotenv, so settings see .env

# which model and effort to use; set them from the shell to compare models, e.g. MODEL=claude-opus-5-5
MODEL = os.environ.get("MODEL", "claude-haiku-5-5")
EFFORT = os.environ.get("EFFORT", "medium")   # medium is the default for both Haiku 5.5 and Opus 5.5; set it explicitly so runs are comparable

# running totals over every API call in this process (evaluate.py reads them to report cost and latency)
USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0}

def call_claude(messages, db=DEFAULT_DB):
    start = time.perf_counter()
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system_for(db),
        messages=messages,
        output_config={"effort": EFFORT},
    )
    USAGE["calls"] += 1
    USAGE["input_tokens"] += response.usage.input_tokens
    USAGE["output_tokens"] += response.usage.output_tokens    # includes thinking tokens, which are billed as output
    USAGE["seconds"] += time.perf_counter() - start
    if response.stop_reason == "refusal":   # refused by safety rules, so return no SQL
        return None
    # the reply may have several content blocks (e.g. thinking); keep only the text
    return "".join(b.text for b in response.content if b.type == "text")

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