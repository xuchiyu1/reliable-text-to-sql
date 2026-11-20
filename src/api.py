# HTTP entry point: POST /ask returns the answer as JSON (V1.1 Step 2)
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from guard import key_ok, RateLimiter
from present import column_names, describe_periods
from evaluate import answer

API_KEY = os.environ.get("APP_API_KEY", "")                         # shared secret; empty = /ask refuses everyone
LIMIT = RateLimiter(int(os.environ.get("ASK_PER_MINUTE", "10")), 60)  # caps API spend if the key leaks

app = FastAPI(title="Reliable Text-to-SQL")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask_endpoint(req: AskRequest, x_api_key: str | None = Header(default=None)):
    # check the key first, so requests without it can't use up the rate limit
    if not key_ok(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="missing or wrong X-API-Key header")
    if not LIMIT.allow():
        raise HTTPException(status_code=429, detail="too many questions, try again in a minute")
    try:
        sql, rows, fixes = answer(req.question)
    except Exception as e:                  # still failing after 2 repairs, or blocked
        return {"status": "error", "message": str(e).split("\n")[0]}
    if rows is None:                        # Claude replied CANNOT_ANSWER
        return {"status": "cannot_answer",
                "message": "The data has no stock prices, forecasts or filing text."}
    if not rows:                            # empty result != 0
        return {"status": "empty", "sql": sql, "rows": [],
                "message": "No matching data found (missing, not 0)."}
    columns = column_names(sql, len(rows[0]))
    return {"status": "ok", "sql": sql,
            "columns": columns, "rows": rows,
            "periods": describe_periods(columns, rows),   # e.g. ["single quarter ended 2025-09-30"]; [] = not in the result
            "fixes": fixes}