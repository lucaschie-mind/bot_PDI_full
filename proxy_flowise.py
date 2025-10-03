
# proxy_flowise.py
import os
import json
import logging
from typing import List
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("proxy_flowise")

# Environment configs (set in Railway / env manager)
FLOWISE_URL = os.getenv("FLOWISE_URL")  # e.g. https://cloud.flowiseai.com/api/v1/prediction/<CHATFLOW_ID>
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY")  # optional
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "")  # comma separated list
PORT = int(os.getenv("PORT", 8000))

# Parse allowed origins
origins: List[str] = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
if not origins:
    origins = ["*"]  # development default; set explicit origins in production

app = FastAPI(title="Flowise Proxy (secure)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    email: str
    question: str

def get_user_docs_from_postgres(user_email: str, limit: int = 10) -> List[str]:
    """
    Placeholder for DB logic. Replace with actual DB queries using DATABASE_URL.
    Should return a list of text documents relevant to the user for RAG.
    """
    return []

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/chat")
async def chat(request: Request):
    # parse json safely
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        raw = (await request.body()).decode("utf-8", errors="replace")
        logger.error("Invalid JSON body: %s", raw[:500])
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}. Raw snippet: {raw[:200]}")
    # validate
    try:
        cr = ChatRequest(**body)
    except Exception as e:
        logger.error("Validation error: %s", str(e))
        raise HTTPException(status_code=400, detail="Invalid request payload")

    if not FLOWISE_URL:
        logger.error("FLOWISE_URL not configured")
        raise HTTPException(status_code=500, detail="Server not configured (FLOWISE_URL missing)")

    user_email = cr.email
    question = cr.question

    # fetch user docs (RAG)
    try:
        docs = get_user_docs_from_postgres(user_email, limit=10)
    except Exception:
        logger.exception("Error fetching user docs")
        docs = []

    context = "\n\n".join(docs) if docs else "n/a"
    system_prompt = (
        "Você é um assistente que responde usando APENAS o CONTEXTO do usuário abaixo. "
        "Se a informação não estiver no contexto, responda 'Não encontrei informação suficiente.'"
    )
    composed_prompt = f"SYSTEM:\\n{system_prompt}\\n\\nEMAIL: {user_email}\\n\\nCONTEXT:\\n{context}\\n\\nQUESTION:\\n{question}"

    logger.info("Chat request for user=%s docs=%d", user_email, len(docs))
    logger.debug("Prompt snippet: %s", composed_prompt[:1000])

    headers = {"Content-Type": "application/json"}
    if FLOWISE_API_KEY:
        headers["Authorization"] = f"Bearer {FLOWISE_API_KEY}"

    payload = {"input": composed_prompt}
    logger.info("Calling Flowise url=%s payload_snippet=%s", FLOWISE_URL, str(payload)[:200])

    try:
        r = requests.post(FLOWISE_URL, json=payload, headers=headers, timeout=120)
        logger.info("Flowise returned status=%s", getattr(r, "status_code", None))
        try:
            text_snip = r.text[:2000]
            logger.debug("Flowise response snippet: %s", text_snip)
        except Exception:
            logger.debug("Could not read flowise response text")
        r.raise_for_status()
        try:
            flowise_json = r.json()
        except ValueError:
            flowise_json = {"text": r.text}
    except requests.exceptions.RequestException as e:
        logger.exception("Error calling Flowise for user=%s", user_email)
        detail = f"Flowise request failed: {str(e)}"
        raise HTTPException(status_code=502, detail=detail)

    answer = None
    if isinstance(flowise_json, dict):
        for k in ("answer", "text", "output", "result"):
            if k in flowise_json:
                answer = flowise_json[k]
                break
        if not answer:
            answer = json.dumps(flowise_json)[:4000]
    else:
        answer = str(flowise_json)[:4000]

    # persist chat log - implement DB write in production
    # save_chat_log(user_email, question, answer, flowise_json)

    return {"answer": answer, "raw": flowise_json}

# Serve the static widget.html file (same dir)
@app.get("/widget", response_class=HTMLResponse)
async def widget():
    return FileResponse("widget.html", media_type="text/html")

@app.post("/debug_payload")
async def debug_payload(request: Request):
    try:
        body = await request.json()
    except Exception:
        raw = (await request.body()).decode("utf-8","replace")
        return JSONResponse({"error":"invalid json","raw_snippet": raw[:500]}, status_code=400)
    user_email = body.get("email")
    docs = []
    try:
        docs = get_user_docs_from_postgres(user_email, limit=10)
    except Exception:
        logger.exception("Error fetching docs in debug_payload")
    context = "\\n- ".join(docs) if docs else "n/a"
    system = "Você é um assistente. USE SOMENTE o CONTEXTO fornecido abaixo."
    composed = f"SYSTEM:\\n{system}\\n\\nEMAIL: {user_email}\\n\\nCONTEXT:\\n{context}\\n\\nQUESTION:\\n{body.get('question')}"
    return {"composed": composed, "context": context, "docs_count": len(docs)}

@app.get("/debug_routes")
async def debug_routes():
    routes = [{"path": getattr(r,"path",str(r)), "name": getattr(r,"name",None)} for r in app.router.routes]
    return {"routes": routes}

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/widget")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("proxy_flowise:app", host="0.0.0.0", port=PORT, reload=True)
