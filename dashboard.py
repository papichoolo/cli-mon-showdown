import json
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

@app.get("/")
def get_dashboard():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/state")
def get_state():
    if os.path.exists("agent_state.json"):
        try:
            with open("agent_state.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

if __name__ == "__main__":
    print("🚀 Starting Agent Dashboard on http://127.0.0.1:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080)
