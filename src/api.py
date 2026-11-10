# HTTP entry point: POST /ask returns the answer as JSON (V1.1 Step 2)
from fastapi import FastAPI
from pydantic import BaseModel, Field

from app import column_names
from evaluate import answer

app = FastAPI(title="Reliable Text-to-SQL")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask_endpoint(req: AskRequest):
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
    return {"status": "ok", "sql": sql,
            "columns": column_names(sql, len(rows[0])),
            "rows": rows, "fixes": fixes}