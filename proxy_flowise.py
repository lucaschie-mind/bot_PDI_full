import os
import json
import logging
from typing import List, Optional
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Logging config (INFO default; ajustar conforme necessário) ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("proxy_flowise")

# --- Config from environment (NO secrets in code) ---
FLOWISE_URL = os.getenv("FLOWISE_URL")  # REQUIRED: ex: https://cloud.flowiseai.com/api/v1/prediction/<CHATFLOW_ID>
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY")  # optional
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "")  # comma separated, ex: https://full.mindsight.com.br,https://full.sandbox...
DATABASE_URL = os.getenv("DATABASE_URL")  # optional - set in Railway if using DB
PORT = int(os.getenv("PORT", 8000))

if not FLOWISE_URL:
    # fail fast if you're running in production without FLOWISE_URL
    logger.warning("FLOWISE_URL not set. Set FLOWISE_URL in environment (Railway Variables).")
    # Don't sys.exit() here so health check can still run; chat will check FLOWISE_URL and return 500 if missing.

# parse allowed origins
origins: List[str] = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
if not origins:
    origins = ["*"]  # permissive for dev only; in production set exact origins


app = FastAPI(title="Flowise Proxy (secure)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model for incoming chat requests
class ChatRequest(BaseModel):
    email: str
    question: str
    # optionally add user_id, metadata, etc.

# --- Helpers (do not put credentials here) ---
def mask_secret(s: Optional[str], keep: int = 6) -> str:
    if not s:
        return ""
    if len(s) <= keep:
        return "***"
    return s[:keep] + "...(redacted)"

def get_user_docs_from_postgres(user_email: str, limit: int = 10) -> List[str]:
    """
    Placeholder: implement your DB logic here. Do NOT put credentials in code.
    Set DATABASE_URL in Railway and use a secure DB client library.
    Return a list of text documents (strings) relevant to the user.
    """
    # Example: return [] when not implemented
    return []

# --- Routes ---
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
    # validate with pydantic
    try:
        cr = ChatRequest(**body)
    except Exception as e:
        logger.error("Validation error: %s", str(e))
        raise HTTPException(status_code=400, detail="Invalid request payload")

    # require FLOWISE_URL
    if not FLOWISE_URL:
        logger.error("FLOWISE_URL not configured in env")
        raise HTTPException(status_code=500, detail="Server not configured (FLOWISE_URL missing)")

    user_email = cr.email
    question = cr.question

    # fetch user docs (RAG context)
    try:
        docs = get_user_docs_from_postgres(user_email, limit=10)
    except Exception as e:
        logger.exception("Error fetching user docs for %s", user_email)
        docs = []

    context = "\n\n".join(docs) if docs else "n/a"

    # compose system prompt (adjust to your flow)
    system_prompt = (
        "Você é um assistente que responde usando APENAS o CONTEXTO do usuário abaixo. "
        "Se a informação não estiver no contexto, responda 'Não encontrei informação suficiente.'"
    )
    composed_prompt = (
        f"SYSTEM:\n{system_prompt}\n\nEMAIL: {user_email}\n\nCONTEXT:\n{context}\n\nQUESTION:\n{question}"
    )

    # safe logging: never log secrets; log truncated prompt/context
    logger.info("Chat request for user=%s docs=%d", user_email, len(docs))
    logger.debug("Prompt snippet: %s", composed_prompt[:1000])

    headers = {"Content-Type": "application/json"}
    if FLOWISE_API_KEY:
        headers["Authorization"] = f"Bearer {FLOWISE_API_KEY}"

    payload = {"input": composed_prompt}  # adjust per Flowise ingestion format
    # log only small snippet of payload (not secrets)
    logger.info("Calling Flowise url=%s payload_snippet=%s", FLOWISE_URL, str(payload)[:200])

    try:
        r = requests.post(FLOWISE_URL, json=payload, headers=headers, timeout=120)
        logger.info("Flowise returned status=%s", getattr(r, "status_code", None))
        # truncated body for logs
        try:
            text_snip = r.text[:2000]
            logger.debug("Flowise response snippet: %s", text_snip)
        except Exception:
            logger.debug("Could not read flowise response text")
        r.raise_for_status()
        # try parse JSON - if not JSON, return raw text
        try:
            flowise_json = r.json()
        except ValueError:
            flowise_json = {"text": r.text}
    except requests.exceptions.RequestException as e:
        logger.exception("Error calling Flowise for user=%s", user_email)
        # do not return secrets in error messages
        detail = f"Flowise request failed: {str(e)}"
        raise HTTPException(status_code=502, detail=detail)

    # extract answer from flowise response - adapt to your Flowise structure
    answer = None
    if isinstance(flowise_json, dict):
        # try common fields
        for k in ("answer", "text", "output", "result"):
            if k in flowise_json:
                answer = flowise_json[k]
                break
        # fallback: pretty-print whole JSON
        if not answer:
            answer = json.dumps(flowise_json)[:4000]
    else:
        answer = str(flowise_json)[:4000]

    return {"answer": answer, "raw": flowise_json}

# Simple widget HTML (small, self-contained). Adjust ALLOWED_PARENT in script if needed.
WIDGET_HTML = """
<!doctype html><html><head><meta charset="utf-8"/><title>Bot Widget</title>
<style>body{font-family:Arial;margin:0}#chat{height:100vh;display:flex;flex-direction:column}
#messages{flex:1;overflow:auto;padding:8px}#controls{display:flex;padding:8px}
input{flex:1;padding:8px;border:1px solid #ddd;border-radius:6px}button{padding:8px 12px;border-radius:6px;background:#2563eb;color:#fff;border:none}
.msg{margin:6px 0;padding:8px;border-radius:6px;background:#f3f4f6}.you{background:#e0f2fe;text-align:right}
</style></head><body>
<div id="chat"><div id="messages"></div><div id="controls">
<input id="input" placeholder="Escreva sua pergunta..." /><button id="send">Enviar</button></div></div>
<script>
(function(){
  // Allowed parent origins - adjust in environment if needed
  const ALLOWED_PARENTS = []; // empty => skip origin check (for testing only)
  const PROXY_ORIGIN = location.origin;
  let user = { email: null, id: null };
  const messagesEl = document.getElementById('messages');
  const inputEl = document.getElementById('input');
  const sendBtn = document.getElementById('send');
  function append(who,text){const el=document.createElement('div');el.className='msg '+(who==='you'?'you':'bot');el.textContent=(who==='you'?'Você: ':'Bot: ')+text;messagesEl.appendChild(el);messagesEl.scrollTop=messagesEl.scrollHeight}
  window.addEventListener('message', (event) => {
    // if ALLOWED_PARENTS set, enforce origin check; otherwise skip (dev)
    if (ALLOWED_PARENTS.length>0 && !ALLOWED_PARENTS.includes(event.origin)) return;
    const data = event.data||{};
    if (data.type==='init'){ user.email=data.email||null; user.id=data.id||null; append('bot','Usuário identificado: '+(user.email||user.id||'desconhecido')); }
  }, false);
  async function ask(question){
    if (!user.email && !user.id){ append('bot','Erro: usuário não identificado.'); return; }
    append('you',question);
    try {
      const res = await fetch(PROXY_ORIGIN + '/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:user.email,question})});
      const j=await res.json(); append('bot', j.answer || (j.raw && JSON.stringify(j.raw)) || 'Sem resposta');
    } catch(e){append('bot','Erro: '+(e.message||e));}
  }
  sendBtn.addEventListener('click',()=>{const q=inputEl.value.trim(); if(!q) return; ask(q); inputEl.value='';});
})();
</script>
</body></html>
"""

@app.get("/widget", response_class=HTMLResponse)
async def widget():
    return HTMLResponse(WIDGET_HTML)

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
    except Exception as e:
        logger.exception("Error fetching docs in debug_payload")
    context = "\n- ".join(docs) if docs else "n/a"
    system = "Você é um assistente. USE SOMENTE o CONTEXTO fornecido abaixo."
    composed = f"SYSTEM:\\n{system}\\n\\nEMAIL: {user_email}\\n\\nCONTEXT:\\n{context}\\n\\nQUESTION:\\n{body.get('question')}"
    return {"composed": composed, "context": context, "docs_count": len(docs)}

@app.get("/debug_routes")
async def debug_routes():
    routes = [{"path": getattr(r,"path",str(r)), "name": getattr(r,"name",None)} for r in app.router.routes]
    return {"routes": routes}

# Optional root redirect to widget
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/widget")

# run with: python -m uvicorn proxy_flowise:app --host 0.0.0.0 --port $PORT
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("proxy_flowise:app", host="0.0.0.0", port=PORT, reload=True)
