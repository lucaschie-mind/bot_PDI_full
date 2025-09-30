# proxy_flowise.py
import os
import textwrap
import requests
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# opcional para JWT decode
import jwt

load_dotenv()

# CONFIG
FLOWISE_URL = os.getenv("FLOWISE_URL")  # ex: https://cloud.flowiseai.com/api/v1/prediction/<CHATFLOW_ID>
DATABASE_URL = os.getenv("DATABASE_URL")  # opcional (Postgres) - ex: postgres://user:pass@host:5432/db
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")  # ex: https://app.suaempresa.com
JWT_SECRET = os.getenv("JWT_SECRET")  # opcional - se quiser validar JWTs (HS256)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

if not FLOWISE_URL:
    raise SystemExit("Set FLOWISE_URL in env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("proxy_flowise")

app = FastAPI()
origins = [o.strip() for o in ALLOWED_ORIGINS.split(",")] if ALLOWED_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

# === helpers DB (opcional) ===
def get_user_docs_from_postgres(user_email: str, limit: int = 10):
    if not DATABASE_URL:
        return []
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        with conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT content FROM user_docs
                WHERE user_email = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_email, limit))
            rows = cur.fetchall()
        return [r["content"] for r in rows]
    except Exception as e:
        logger.warning("DB fetch failed: %s", e)
        return []

def save_chat_log(user_email: str, question: str, answer: str):
    if not DATABASE_URL:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO chat_logs (user_email, question, answer)
                VALUES (%s, %s, %s)
            """, (user_email, question, answer))
            conn.commit()
    except Exception as e:
        logger.warning("DB save failed: %s", e)

# === auth helpers ===
def extract_email_from_jwt(token: str):
    try:
        if JWT_SECRET:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        else:
            # decode WITHOUT verification for debugging only
            payload = jwt.decode(token, options={"verify_signature": False})
        # examine common claims
        for k in ("email", "username", "sub"):
            if k in payload:
                return payload[k]
        return None
    except Exception as e:
        logger.warning("JWT decode failed: %s", e)
        return None

def get_email_from_request(request: Request, body_email: str = None):
    # priority:
    # 1) Authorization: Bearer <token>
    # 2) Cookie 'access_token'
    # 3) email in request body (fallback - less secure)
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(None, 1)[1]
        email = extract_email_from_jwt(token)
        if email:
            return email

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        email = extract_email_from_jwt(cookie_token)
        if email:
            return email

    # fallback to body-provided email (acceptable for POC only)
    if body_email:
        return body_email

    return None

# === endpoints ===
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/chat")
async def chat(request: Request):
    """
    Body expected:
    {
      "email": "lucas@mindsight.com.br",   # optional if Authorization cookie/token present
      "question": "text question"
    }
    """
    body = await request.json()
    body_email = body.get("email")
    question = body.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question' in body")

    # 1) determine user email (validate via JWT if possible)
    user_email = get_email_from_request(request, body_email=body_email)
    if not user_email:
        raise HTTPException(status_code=401, detail="Unable to determine user email. Provide Authorization Bearer token or include email in body (POC)")

    # 2) fetch user docs (Postgres) - ensures we only send user's data onward
    docs = get_user_docs_from_postgres(user_email, limit=10)
    joined = "\n- ".join(docs) if docs else "n/a"
    context = textwrap.shorten(f"- {joined}", width=6000, placeholder=" ...[truncated]")

    # 3) compose prompt instructing Flowise to only use user's context
    system = (
        "Você é um assistente. USE SOMENTE o CONTEXTO fornecido abaixo (pertence ao usuário). "
        "Se a resposta não estiver no contexto, responda: 'Não encontrei informação suficiente'. "
        "NÃO inclua ou infira dados de outros usuários."
    )
    composed = f"SYSTEM:\n{system}\n\nEMAIL: {user_email}\n\nCONTEXT:\n{context}\n\nQUESTION:\n{question}"
    payload = {"question": composed}

    # 4) call Flowise Cloud
    try:
        r = requests.post(FLOWISE_URL, json=payload, timeout=60)
        r.raise_for_status()
        flowise_resp = r.json()
    except Exception as e:
        logger.exception("Flowise call failed")
        raise HTTPException(status_code=502, detail=f"Flowise error: {e}")

    # 5) try to extract textual answer (depends on your flow)
    answer = flowise_resp.get("text") or flowise_resp.get("message") or str(flowise_resp)

    # 6) save chat log (optional)
    try:
        save_chat_log(user_email, question, answer)
    except Exception:
        pass

    return {"answer": answer, "raw": flowise_resp}
