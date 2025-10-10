from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any
import os, re, unicodedata, json
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql as psql

# ================= .env =================
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True) or str(Path(__file__).with_name(".env")))
except Exception:
    pass

# ================= Config =================
FLOWISE_URL = os.getenv("FLOWISE_URL", "")
FLOWISE_CHATFLOW_ID = os.getenv("FLOWISE_CHATFLOW_ID", "")
FLOWISE_PREDICTION_URL = os.getenv("FLOWISE_PREDICTION_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_URL_RESUMO_SEMANAL = os.getenv("DATABASE_URL_RESUMO_SEMANAL", "")
DB_SCHEMA = os.getenv("DB_SCHEMA", "")
DB_TABLE = os.getenv("DB_TABLE", "")

# Janelas (dias)
DELTA_TEMPO_RESUMO = int(os.getenv("DELTA_TEMPO_RESUMO", 30))
DELTA_TEMPO = int(os.getenv("DELTA_TEMPO", 90))
TEMPO_ATUALIZACAO = int(os.getenv("TEMPO_ATUALIZACAO", 180))

# Valores padrão (fallback)
DEFAULT_USER_ID = "131"
DEFAULT_USER_NAME = "Lucas Chieregatti Machado"
DEFAULT_USER_EMAIL = "lucas@mindsight.com.br"

# ================= App =================
app = FastAPI(title="Bot PDI – FastAPI + Flowise + PostgreSQL")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("Content-Security-Policy", "frame-ancestors *")
    return resp

# ================= Frontend =================
INDEX_HTML = r"""
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Widget de Chat – PDI (Bot)</title>
    <style>
      :root { 
        --bg: #ffffff; 
        --panel: #f8f9fa; 
        --panel-2: #ffffff; 
        --text: #1a1a1a; 
        --muted: #6c757d; 
        --accent: #0d6efd; 
        --ring: rgba(13, 110, 253, 0.25);
        --border: #dee2e6;
        --msg-bot-bg: #EFDBFF;
        --msg-bot-border: #722ED1;
        --msg-user-bg: #f1f3f5;
        --msg-user-border: #ced4da;
      }
      
      * { box-sizing: border-box; }
      
      html, body { 
        height: 100%; 
        margin: 0; 
        padding: 0;
      }
      
      body {
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans";
        background: var(--bg);
        color: var(--text);
      }
      
      .container {
        width: 100%;
        height: 100vh;
        display: flex;
        flex-direction: column;
        padding: 0;
        margin: 0;
      }
      
      .chat-wrap {
        width: 100%;
        height: 100%;
        display: grid;
        grid-template-rows: auto 1fr auto;
        background: var(--panel);
        border: none;
        overflow: hidden;
      }
      
      header {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 16px 20px;
        border-bottom: 1px solid var(--border);
        background: var(--panel-2);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
      }
      
      header .dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #34d399;
        box-shadow: 0 0 0 4px rgba(52, 211, 153, 0.15);
      }
      
      header h1 {
        font-size: 16px;
        font-weight: 600;
        margin: 0;
        color: var(--text);
      }
      
      header p {
        margin: 0;
        color: var(--muted);
        font-size: 12px;
      }
      
      .stack {
        display: flex;
        flex-direction: column;
      }
      
      .messages {
        padding: 20px;
        overflow: auto;
        display: flex;
        flex-direction: column;
        gap: 12px;
        background: var(--bg);
      }
      
      .msg {
        max-width: 85%;
        padding: 12px 14px;
        border-radius: 12px;
        line-height: 1.4;
        word-wrap: break-word;
        white-space: pre-line;
      }
      
      .msg.bot {
        background: var(--msg-bot-bg);
        border: 1px solid var(--msg-bot-border);
        align-self: flex-start;
        color: var(--text);
      }
      
      .msg.user {
        background: var(--msg-user-bg);
        border: 1px solid var(--msg-user-border);
        align-self: flex-end;
        color: var(--text);
      }
      
      .msg time {
        display: block;
        margin-top: 6px;
        font-size: 11px;
        color: var(--muted);
        opacity: 0.8;
      }
      
      .hint {
        text-align: center;
        color: var(--muted);
        font-size: 12px;
        padding: 8px 16px;
        background: var(--panel-2);
        border-top: 1px solid var(--border);
      }
      
      form {
        display: flex;
        gap: 8px;
        padding: 16px;
        border-top: 1px solid var(--border);
        background: var(--panel-2);
      }
      
      input[type=text] {
        flex: 1;
        min-width: 0;
        padding: 12px 14px;
        border-radius: 8px;
        border: 1px solid var(--border);
        background: var(--bg);
        color: var(--text);
        outline: none;
        transition: box-shadow 0.15s, border-color 0.15s;
        font-size: 14px;
      }
      
      input[type=text]:focus {
        border-color: var(--accent);
        box-shadow: 0 0 0 3px var(--ring);
      }
      
      input[type=text]::placeholder {
        color: var(--muted);
      }
      
      button {
        padding: 12px 20px;
        border-radius: 8px;
        border: 0px ;
        background: #722ED1;
        color: #fff;
        cursor: pointer;
        font-weight: 600;
        font-size: 14px;
        transition: background 0.15s;
      }
      
      button:hover {
        background: #391085;
      }
      
      button:active {
        transform: translateY(1px);
      }
      
      .panel {
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px;
        background: var(--panel-2);
        margin: 16px;
      }
      
      .muted {
        color: var(--muted);
        font-size: 12px;
      }
      
      #flowise-chatbot {
        display: none;
      }
      
      @media (max-width: 420px) {
        header h1 {
          font-size: 14px;
        }
        
        .msg {
          max-width: 90%;
        }
      }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="chat-wrap" id="chat">
        <header>
          <div class="dot" aria-hidden="true"></div>
          <div class="stack">
            <h1>Synapses</h1>
            <p>Assistente da Mindsight que apoia você a construir um plano de desenvolvimento alinhado aos seus objetivos.</p>
          </div>
        </header>

        <div class="messages" id="messages" aria-live="polite"></div>
        
        <div>
          <p class="hint">Digite "1" ou "Montar PDI" para iniciar. Qualquer outra coisa retorna "Escolha uma opção válida".</p>
          <form id="chat-form" autocomplete="off">
            <input id="chat-input" type="text" placeholder="Digite aqui…" aria-label="Mensagem" />
            <button type="submit" aria-label="Enviar">Enviar</button>
          </form>
        </div>
      </div>

      <div class="panel" style="display: none;">
        <div id="flowise-chatbot"></div>
        <p class="muted">Flowise: inicializa se FLOWISE_URL e FLOWISE_CHATFLOW_ID estiverem definidos.</p>
      </div>
    </div>

    <script>
      const $ = (sel) => document.querySelector(sel);
      const messagesEl = $('#messages');
      const user = { id: "__USER_ID__", name: "__USER_NAME__", email: "__USER_EMAIL__" };

      function timeNow(){ 
        const d = new Date(); 
        return d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}); 
      }
      
      function addMessage(text, who='bot'){
        const div = document.createElement('div');
        div.className = `msg ${who}`;
        div.innerHTML = `${escapeHtml(text)}<time>${timeNow()}</time>`;
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        autoResize();
      }
      
      function escapeHtml(str){ 
        return String(str)
          .replaceAll('&','&amp;')
          .replaceAll('<','&lt;')
          .replaceAll('>','&gt;')
          .replaceAll('"','&quot;')
          .replaceAll("'",'&#039;'); 
      }

      async function sendMessage(text){
        try{
          const res = await fetch('/api/message', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ 
              text,
              user_id: user.id,
              user_name: user.name,
              user_email: user.email
            }) 
          });
          if(!res.ok) throw new Error('Falha no envio');
          const data = await res.json();
          addMessage(data.reply || `Ok!`, 'bot');
        }catch(err){ 
          addMessage('Ops! Não consegui responder agora.', 'bot'); 
        }
      }

      document.getElementById('chat-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('chat-input');
        const text = input.value.trim();
        if(!text) return;
        addMessage(text, 'user');
        input.value='';
        sendMessage(text);
      });

      // Mensagem inicial
      addMessage(`Olá, ${user.name}! Selecione a opção desejada:\n1 - Montar PDI`);

      // Auto-resize (iframe)
      const ro = new ResizeObserver(() => autoResize());
      ro.observe(document.body);
      function autoResize(){
        const height = document.documentElement.scrollHeight;
        try{ 
          window.parent.postMessage({ type: 'WIDGET_HEIGHT', height }, '*'); 
        }catch(_){ }
      }
      autoResize();

      // ================= Flowise Embed (visual, opcional) =================
      const FLOWISE_URL = "__FLOWISE_URL__";
      const CHATFLOW_ID = "__FLOWISE_CHATFLOW_ID__";
      (function loadFlowise(){
        if(!FLOWISE_URL || !CHATFLOW_ID){
          console.warn('Flowise embed não iniciado: configure FLOWISE_URL e FLOWISE_CHATFLOW_ID no .env.');
          return;
        }
        let host = FLOWISE_URL;
        if (host.endsWith('/')) host = host.slice(0, -1);
        const script = document.createElement('script');
        script.src = host + '/embed.min.js';
        script.onload = () => {
          try{
            window.Flowise && window.Flowise.initFull({
              chatflowid: CHATFLOW_ID,
              apiHost: host,
              chatflowConfig: {
                sessionId: String(user.id),
                vars: {
                  userId: user.id,
                  userName: user.name,
                  userEmail: user.email,
                  currentUrl: window.location.href,
                  userRole: 'authenticated'
                }
              }
            });
          } catch (e){ 
            console.error('Falha ao inicializar Flowise (embed):', e); 
          }
        };
        script.onerror = () => console.error('Não foi possível carregar embed.min.js do Flowise.');
        document.body.appendChild(script);
      })();
    </script>
  </body>
</html>
"""

# ================= Helpers =================
def normalize_text(s: str) -> str:
    s = s.lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# ================= Dados & Filtros (PostgreSQL) =================
INFO_TAGS_PF = "tags pontos fortes"
INFO_TAGS_PD = "tags pontos desenvolvimento"
INFO_OBJETIVOS = "objetivos de carreira"
INFO_TAREFAS = "tarefas cargo (autoavaliação)"
INFO_DIAGNOSTICO = "diagnostico pdi"
INFO_COMPETENCIAS = "competencias foco"
TIPOS_CANON = [
    INFO_TAGS_PF,
    INFO_TAGS_PD,
    "resumo avd",
    "output_feedback",
    "output_pdi",
    INFO_OBJETIVOS,
    INFO_TAREFAS,
    INFO_DIAGNOSTICO,
]

_DAYS_BY_TYPE = { t: DELTA_TEMPO for t in TIPOS_CANON }
_DAYS_BY_TYPE["resumo avd"] = DELTA_TEMPO_RESUMO


def _discover_info_table(conn) -> Tuple[str, str]:
    if DB_SCHEMA and DB_TABLE:
        return DB_SCHEMA, DB_TABLE
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT schemaname, tablename
            FROM pg_catalog.pg_tables
            WHERE lower(tablename) = lower('dados_AVD_pessoas')
            ORDER BY (schemaname = 'public') DESC, schemaname, tablename
            LIMIT 1;
            """
        )
        row = cur.fetchone()
        if row:
            return row[0], row[1]
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.columns
            WHERE column_name IN ('email','informacao','descricao','data')
            GROUP BY table_schema, table_name
            HAVING COUNT(DISTINCT column_name) = 4
            ORDER BY (table_schema='public') DESC, table_schema, table_name
            LIMIT 1;
            """
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("Não encontrei tabela com colunas email/informacao/descricao/data. Defina DB_SCHEMA/DB_TABLE no .env.")
        return row["table_schema"], row["table_name"]


def get_basic_profile(email: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not DATABASE_URL:
        return None, None, None
    try:
        with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT resumo_pessoa, id, posicao
                FROM pessoas_ativos
                WHERE email = %s
                LIMIT 1;
                """,
                (email,)
            )
            row = cur.fetchone()
            if row:
                resumo_pessoa, id_pessoa, cargo_pessoa = row
                return (
                    (resumo_pessoa or None),
                    (cargo_pessoa or None),
                    (str(id_pessoa) if id_pessoa is not None else None),
                )
    except Exception:
        pass
    return None, None, None


def get_historico_bot(email: str, days: int = DELTA_TEMPO_RESUMO) -> str:
    if not DATABASE_URL:
        return ""
    try:
        limit_date = datetime.now(timezone.utc) - timedelta(days=days)
        with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT data, output_pessoa_bot
                FROM outputs_bot_pessoas
                WHERE email = %s AND data >= %s
                ORDER BY data DESC
                LIMIT 5;
                """,
                (email, limit_date)
            )
            rows = cur.fetchall() or []
            if not rows:
                return "Não há nenhuma interação até o momento"
            parts = []
            for d, resumo in rows:
                try:
                    ts = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)
                except Exception:
                    ts = str(d)
                parts.append(f"data: {ts} - resumo: {str(resumo or '').strip()}")
            return "; ".join(parts)
    except Exception:
        return ""


def get_resumos_semanal(email: str, days: int = DELTA_TEMPO) -> str:
    if not DATABASE_URL_RESUMO_SEMANAL:
        return ""
    try:
        limit_date = datetime.now(timezone.utc) - timedelta(days=days)
        with psycopg2.connect(DATABASE_URL_RESUMO_SEMANAL) as conn, conn.cursor() as cur:
            cur.execute(
                'SELECT summary, "timestamp" FROM resumos WHERE employee_email = %s AND "timestamp" >= %s ORDER BY "timestamp" ASC;',
                (email, limit_date)
            )
            rows = cur.fetchall() or []
            if not rows:
                return ""
            lines = []
            for summary, ts in rows:
                try:
                    ts_fmt = ts.strftime('%d/%m/%Y') if hasattr(ts, 'strftime') else str(ts)
                except Exception:
                    ts_fmt = str(ts)
                s = str(summary or '').strip()
                if s:
                    lines.append(f"resumo da semana {ts_fmt} - {s}")
            return "\n".join(lines)
    except Exception:
        return ""


def get_latest_infos(email: str):
    valores = {t: "" for t in TIPOS_CANON}
    datas = {t: None for t in TIPOS_CANON}
    if not DATABASE_URL:
        return valores, datas, False, "DATABASE_URL não configurado"
    from_date_days = max(DELTA_TEMPO_RESUMO, DELTA_TEMPO, TEMPO_ATUALIZACAO)
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            schema, table = _discover_info_table(conn)
            tbl = psql.SQL("{}.{}").format(psql.Identifier(schema), psql.Identifier(table))
            query = psql.SQL(
                """
                SELECT DISTINCT ON (info_norm) info_norm, descricao, data
                FROM (
                    SELECT trim(lower(informacao)) AS info_norm,
                           descricao, data
                    FROM {tbl}
                    WHERE email = %s
                      AND (data IS NULL OR data >= now() - make_interval(days => %s))
                ) t
                ORDER BY info_norm, data DESC NULLS LAST;
                """
            ).format(tbl=tbl)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (email, from_date_days))
                rows = cur.fetchall()
    except Exception as e:
        return valores, datas, False, f"Erro ao consultar PostgreSQL: {e}"

    now = datetime.now(timezone.utc)
    def _norm(s: str) -> str:
        s = s.lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    alvo = { _norm(t): t for t in TIPOS_CANON }
    for r in rows:
        info_norm = _norm(r.get("info_norm") or "")
        if info_norm not in alvo:
            continue
        canon = alvo[info_norm]
        d = r.get("data")
        desc = (r.get("descricao") or "").strip()
        days = _DAYS_BY_TYPE.get(canon, DELTA_TEMPO)
        keep = True
        if d:
            if getattr(d, 'tzinfo', None) is None:
                d = d.replace(tzinfo=timezone.utc)
            age_days = (now - d).days
            if age_days > days:
                keep = False
            if age_days > TEMPO_ATUALIZACAO:
                keep = False
        if keep and desc:
            valores[canon] = desc
            datas[canon] = d
    return valores, datas, True, "ok"


def format_profile_context(email: str, user_name: str, valores: Dict[str, str]) -> str:
    resumo_pessoa, cargo_pessoa, id_pessoa = get_basic_profile(email)
    historico = get_historico_bot(email)
    resumos_sem = get_resumos_semanal(email)
    lines = [f"email: {email}", f"nome: {user_name}"]
    if id_pessoa: lines.append(f"id_pessoa: {id_pessoa}")
    if cargo_pessoa: lines.append(f"cargo: {cargo_pessoa}")
    if resumo_pessoa: lines.append(f"resumo_pessoa: {resumo_pessoa}")
    for k in TIPOS_CANON:
        v = (valores.get(k) or "").strip()
        if v:
            lines.append(f"{k}: {v}")
    if historico:
        lines.append(f"historico_bot: {historico}")
    if resumos_sem:
        lines.append("resumos_semanais:")
        lines.append(resumos_sem)
    if len(lines) <= 2:
        lines.append("(sem dados válidos no intervalo configurado)")
    return "\n".join(lines)

# ================= Flowise =================


async def call_flowise_with_session(prompt: str, session_id: str, user_name: str, user_email: str) -> str:
    url = FLOWISE_PREDICTION_URL or (f"{FLOWISE_URL.rstrip('/')}/api/v1/prediction/{FLOWISE_CHATFLOW_ID}" if (FLOWISE_URL and FLOWISE_CHATFLOW_ID) else None)
    if not url:
        return "(Flowise não configurado)"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {
        "question": prompt,
        "overrideConfig": {"sessionId": session_id, "vars": {"userName": user_name, "userEmail": user_email}},
        "responseMode": "blocking",
    }
    for attempt in range(3):
        try:
            timeout = 90.0 if attempt == 0 else 120.0
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                body_text = (resp.text or "").strip()
                if resp.status_code >= 400:
                    if attempt < 2:
                        continue
                    try:
                        data = resp.json()
                        msg = data.get("message") if isinstance(data, dict) else None
                    except Exception:
                        msg = None
                    return f"(Flowise indisponível) HTTP {resp.status_code}: {msg or (body_text[:240] or 'sem corpo')}"
                try:
                    data = resp.json()
                    reply = (data.get("text") or data.get("message") or data.get("data")) if isinstance(data, dict) else data
                    return reply if isinstance(reply, str) else json.dumps(reply)
                except Exception:
                    return body_text[:500] or "(Flowise retornou corpo vazio)"
        except Exception as e:
            if attempt == 2:
                return f"(Flowise indisponível) Erro: {e}"
            continue
async def call_flowise(prompt: str, user_id: str, user_name: str, user_email: str) -> str:
    if not (FLOWISE_PREDICTION_URL or (FLOWISE_URL and FLOWISE_CHATFLOW_ID)):
        return "(Flowise não configurado) Defina FLOWISE_PREDICTION_URL ou FLOWISE_URL + FLOWISE_CHATFLOW_ID no .env."
    url = FLOWISE_PREDICTION_URL or f"{FLOWISE_URL.rstrip('/')}/api/v1/prediction/{FLOWISE_CHATFLOW_ID}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {
        "question": prompt,
        "overrideConfig": {
            "sessionId": str(user_id),
            "vars": {
                "userId": user_id,
                "userName": user_name,
                "userEmail": user_email,
                "currentUrl": "",
                "userRole": "authenticated",
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            ct = resp.headers.get("content-type", "")
            body_text = (resp.text or "").strip()
            print(f"[Flowise] POST {url} -> {resp.status_code} {ct}")
            if body_text:
                print(f"[Flowise] body (head 300): {body_text[:300]}")
            if resp.status_code >= 400:
                try:
                    data = resp.json()
                    msg = (data.get("message") or data.get("error") or data.get("text") or data.get("detail")) if isinstance(data, dict) else None
                    return f"(Flowise indisponível) HTTP {resp.status_code}: {msg or (body_text[:240] or str(data))}"
                except Exception:
                    return f"(Flowise indisponível) HTTP {resp.status_code}. Corpo: {body_text[:240] or '(vazio)'}"
            if "application/json" in ct.lower():
                try:
                    data = resp.json()
                    reply = (data.get("text") or data.get("message") or data.get("data")) if isinstance(data, dict) else data
                    return reply if isinstance(reply, str) else json.dumps(reply)
                except Exception as e:
                    return f"(Flowise indisponível) Resposta JSON inválida: {e}. Corpo: {body_text[:240]}"
            return body_text[:500] or "(Flowise retornou corpo vazio)"
    except Exception as e:
        return f"(Flowise indisponível) Erro: {e}"

# ================= Estado da Conversa (roteiro) =================
SESSIONS: Dict[str, Dict[str, Any]] = {}

ROTEIRO = [
    {"key": INFO_TAGS_PF,     "pergunta": "Aponte resumidamente seus principais pontos fortes:"},
    {"key": INFO_TAGS_PD,     "pergunta": "Resumidamente, em quais pontos você precisa se desenvolver?"},
    {"key": INFO_OBJETIVOS,   "pergunta": "Quais são seus principais objetivos de carreira (6–12 meses)?"},
    {"key": INFO_TAREFAS,     "pergunta": "Descreva suas tarefas mais importantes. Onde tem mais facilidade e mais dificuldade?"},
]

START_PROMPT_FLOWISE = (
    "Você é um assistente, e caso você esteja recebendo isso e funcionando, "
    "retorne pedindo para a pessoa escrever um texto sobre ela."
)


PROMPT_DIAGNOSIS = """
Nesse momento, você como especialista deverá fazer um diagnóstico que ajude a pessoa a tomar a decisão do que pode fazer mais sentido se desenvolver.
para isso, aqui estão algumas informações da pessoa {resumo_pessoa}.
O feedback, caso a pessoa tenha, foi esse aqui {feedback}.
os pontos fortes são: {pontos_fortes} e os pontos de desenvolvimento são: {pontos_desenvolvimento}.
Na tarefa atual essa são as tarefas e um pouco de como ela é: {resultado}.
e os objetivos são: {objetivos} e que tem o seguinte histórico de interação com você: {historico_bot}.
Leve em consideração também, para mapear as tarefas e dificuldades os relatórios semanais da pessoa {resumos_semanal}.
Retorne esse diagnóstico com a seguinte estrutura e oferecendo argumentos e os motivos.
1- Resumo da pessoa até o momento:
2- Gaps na posição atual e direcional para a posição atual: 
3- Futuro dado posição atual e objetivos de carreira:
4- Indicações de pontos de desenvolvimento:(Citando competências, habilidades e atitudes que dado as informações a pessoa deveria considerar desenvolver, bem como os motivos. Foque apenas em sugestões sem montar um PDI ou usar o 70 20 10. é apenas recomendação.)
"""

# ================= Rotas =================
@app.get("/", response_class=HTMLResponse)
async def index(
    user_id: Optional[str] = Query(default=DEFAULT_USER_ID, description="ID do usuário"),
    user_name: Optional[str] = Query(default=DEFAULT_USER_NAME, description="Nome do usuário"),
    user_email: Optional[str] = Query(default=DEFAULT_USER_EMAIL, description="Email do usuário")
):
    html = INDEX_HTML
    #html = html.replace("__FLOWISE_URL__", FLOWISE_URL)
    #html = html.replace("__FLOWISE_CHATFLOW_ID__", FLOWISE_CHATFLOW_ID)
    html = html.replace("__USER_ID__", user_id)
    html = html.replace("__USER_NAME__", user_name)
    html = html.replace("__USER_EMAIL__", user_email)
    return HTMLResponse(html)

@app.post("/api/message")
async def api_message(req: Request):
    try:
        payload = await req.json()
        raw = str(payload.get("text", ""))
        user_id = str(payload.get("user_id", DEFAULT_USER_ID))
        user_name = str(payload.get("user_name", DEFAULT_USER_NAME))
        user_email = str(payload.get("user_email", DEFAULT_USER_EMAIL))
    except Exception:
        raw = ""
        user_id = DEFAULT_USER_ID
        user_name = DEFAULT_USER_NAME
        user_email = DEFAULT_USER_EMAIL

    n = normalize_text(raw)

    # === Etapa pós-diagnóstico: aguardando competências (handler prioritário) ===
    sess_tmp = SESSIONS.get(user_id)
    if sess_tmp and sess_tmp.get("await_competencies"):
        comps_raw = raw.strip()
        comps = [c.strip() for c in comps_raw.split(";") if c.strip()]
        if len(comps) < 2:
            return JSONResponse({"reply": "Digite DUAS competências separadas por ponto e vírgula (ex.: Comunicação; Planejamento)."})
        sess_tmp["await_competencies"] = False
        focos_desenvolvimento = "; ".join(comps[:2])
        sess_tmp["answers"][INFO_COMPETENCIAS] = focos_desenvolvimento
        SESSIONS[user_id] = sess_tmp

        # Monta prompt de PDI no formato exato fornecido
        sess_email = sess_tmp.get("user_email", user_email)
        sess_name = sess_tmp.get("user_name", user_name)
        valores, datas, ok_db, msg_db = get_latest_infos(sess_email)
        ctx = format_profile_context(sess_email, sess_name, valores)
        ans = sess_tmp.get("answers", {})
        resumo_pf = ans.get(INFO_TAGS_PF, "")
        resumo_pd = ans.get(INFO_TAGS_PD, "")
        objetivos = ans.get(INFO_OBJETIVOS, "")
        resultado = ans.get(INFO_TAREFAS, "")
        resumos_semanal = get_resumos_semanal(sess_email)
        diagnostico_salvo = sess_tmp.get("diagnosis", "")

        prompt_pdi = f"""
        Você é um especialista em desenvolvimento de carreira e deverá criar um Plano de Desenvolvimento Individual (PDI) de alta qualidade.

        Use as informações do diagnóstico inicial abaixo como base para montar o PDI:

        {diagnostico_salvo}

        Além disso, utilize as informações reais de {resultado} e {resumos_semanal} para sugerir atividades práticas que façam sentido no contexto do dia a dia da pessoa.

        Estruture o PDI no modelo 70-20-10, separado por competência para os seguintes pontos de desenvolvimento escolhidos pela pessoa {focos_desenvolvimento}.
        Para cada competência identificada no diagnóstico, siga esta estrutura:

        ### Competência: [nome da competência]

        **Objetivo de Desenvolvimento**
        Descreva o objetivo principal para esta competência, resumido em 2-3 linhas.

        **70% Atividades práticas (on the job)**
        Liste de 3 a 5 atividades diretamente conectadas às {resultado} e {resumos_semanal} da pessoa.
        Cada atividade deve ser descrita no formato SMART.

        **20% Aprendizagem com os outros**
        Liste de 2 a 4 atividades informais (mentorias, feedbacks, shadowing etc.), conectadas às {resultado} e {resumos_semanal}, no formato SMART.

        **10% Cursos e treinamentos**
        Indique de 1 a 3 formações formais relacionadas à competência.

        --- Regras ---
        - O PDI deve ter múltiplas competências, cada uma com sua própria estrutura.
        - Nas seções 70% e 20%, use {resultado} e {resumos_semanal} para alinhar à realidade.
        - Todas as metas devem estar no formato SMART.
        - Conecte os objetivos de desenvolvimento ao impacto esperado no negócio.
        """

        # Chamada ao Flowise com sessionId id_pessoa:YYYY-MM-DD
        resumo_pessoa, cargo_pessoa, id_pessoa = get_basic_profile(sess_email)
        from datetime import date
        sess_id_override = f"{id_pessoa or user_id}:{date.today().isoformat()}"
        resposta_pdi = await call_flowise_with_session(prompt_pdi, sess_id_override, sess_name, sess_email)

        # Finaliza sessão e retorna
        sess_tmp["started"] = False
        SESSIONS[user_id] = sess_tmp
        aviso_db = f"\n\n(Aviso: {msg_db})" if not ok_db else ""
        return JSONResponse({"reply": f"{resposta_pdi}{aviso_db}"})

    # === Início do fluxo ===
    if n == "1" or "montar pdi" in n or "monte pdi" in n or n == "pdi":
        valores, datas, ok_db, msg_db = get_latest_infos(user_email)
        ctx = format_profile_context(user_email, user_name, valores)

        # 1ª chamada ao Flowise (mensagem inicial do assistente)
        prompt1 = f"[Contexto do usuário]\n{ctx}\n\n{START_PROMPT_FLOWISE}"
        inicio = await call_flowise(prompt1, user_id, user_name, user_email)

        # inicia sessão do roteiro
        SESSIONS[user_id] = {"step": 0, "answers": {}, "started": True, "user_email": user_email, "user_name": user_name}
        # Pré-preenche PF/PD/Objetivos com o que já existe no banco e esteja fresco
        valores, datas, ok_db, msg_db = get_latest_infos(user_email)
        answers = {}
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        def _is_fresh(ts):
            try:
                return (now - ts) <= timedelta(days=TEMPO_ATUALIZACAO)
            except Exception:
                return False
        pre_map = {
            INFO_TAGS_PF: valores.get(INFO_TAGS_PF) or "",
            INFO_TAGS_PD: valores.get(INFO_TAGS_PD) or "",
            INFO_OBJETIVOS: valores.get(INFO_OBJETIVOS) or "",
        }
        for k, v in pre_map.items():
            if v and _is_fresh(datas.get(k)):
                answers[k] = v.strip()
        SESSIONS[user_id]["answers"] = answers
        step0 = 0
        for item in ROTEIRO:
            if item["key"] in answers and answers[item["key"]]:
                step0 += 1
            else:
                break
        SESSIONS[user_id]["step"] = step0
        proxima = ROTEIRO[step0]["pergunta"] if step0 < len(ROTEIRO) else None
        aviso_db = f"\n\n(Aviso: {msg_db})" if not ok_db else ""
        if proxima:
            return JSONResponse({"reply": f"{inicio}{aviso_db}\n\nVamos começar. {proxima}"})
        # caso tudo esteja preenchido, segue fluxo normal (sem perguntar novamente)

        proxima = ROTEIRO[0]["pergunta"]
        aviso_db = f"\n\n(Aviso: {msg_db})" if not ok_db else ""
        return JSONResponse({"reply": f"{inicio}{aviso_db}\n\nVamos começar. {proxima}"})

    # === Continuação do roteiro ===
    sess = SESSIONS.get(user_id)
    if sess and sess.get("started"):
        step = int(sess.get("step", 0))
        if step < len(ROTEIRO):
            # grava resposta do passo atual (se não é o primeiro prompt)
            key = ROTEIRO[step]["key"]
            sess["answers"][key] = raw.strip()
            step += 1
            sess["step"] = step
            SESSIONS[user_id] = sess

            if step < len(ROTEIRO):
                return JSONResponse({"reply": ROTEIRO[step]["pergunta"]})

            # Coletou tudo → 2ª chamada ao Flowise
            sess_email = sess.get("user_email", user_email)
            sess_name = sess.get("user_name", user_name)
            valores, datas, ok_db, msg_db = get_latest_infos(sess_email)
            ctx = format_profile_context(sess_email, sess_name, valores)
            ans = sess.get("answers", {})
            resumo_pf = ans.get(INFO_TAGS_PF, "")
            resumo_pd = ans.get(INFO_TAGS_PD, "")
            objetivos = ans.get(INFO_OBJETIVOS, "")
            tarefas = ans.get(INFO_TAREFAS, "")

            
            prompt2 = PROMPT_DIAGNOSIS.format(
                resumo_pessoa=get_basic_profile(sess_email)[0] or "",
                feedback=valores.get("output_feedback", "") or "",
                pontos_fortes=resumo_pf or valores.get(INFO_TAGS_PF, ""),
                pontos_desenvolvimento=resumo_pd or valores.get(INFO_TAGS_PD, ""),
                resultado=tarefas,
                objetivos=objetivos or valores.get(INFO_OBJETIVOS, ""),
                historico_bot=get_historico_bot(sess_email) or "",
                resumos_semanal=get_resumos_semanal(sess_email) or ""
            )
            from datetime import date
            resumo_pessoa, cargo_pessoa, id_pessoa = get_basic_profile(sess_email)
            sess_id_override = f"{id_pessoa or user_id}:{date.today().isoformat()}"
            resposta = await call_flowise_with_session(prompt2, sess_id_override, sess_name, sess_email)

            # guarda diagnóstico e pede as competências (não encerra a sessão)
            sess["diagnosis"] = resposta
            sess["await_competencies"] = True
            SESSIONS[user_id] = sess

            aviso_db = f"\n\n(Aviso: {msg_db})" if not ok_db else ""
            follow = (
                "Diagnóstico inicial:\n\n" + resposta + aviso_db +
                "\n\nAgora, com o diagnóstico feito, escolha DUAS habilidades/competências para desenvolver neste ciclo "
                "(separe por ponto e vírgula). Ex.: Comunicação; Pragmatismo"
            )
            return JSONResponse({"reply": follow})


    # === Fora de fluxo ===
    return JSONResponse({"reply": "Escolha uma opção válida."})

@app.get("/diag")
async def diag():
    url = FLOWISE_PREDICTION_URL or (f"{FLOWISE_URL.rstrip('/')}/api/v1/prediction/{FLOWISE_CHATFLOW_ID}" if FLOWISE_URL and FLOWISE_CHATFLOW_ID else "")
    db_ok = False; db_msg = ""
    if DATABASE_URL:
        try:
            with psycopg2.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    _ = cur.fetchone()
            db_ok = True; db_msg = "ok"
        except Exception as e:
            db_msg = f"erro: {e}"
    db2_ok = False; db2_msg = ""
    if DATABASE_URL_RESUMO_SEMANAL:
        try:
            with psycopg2.connect(DATABASE_URL_RESUMO_SEMANAL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    _ = cur.fetchone()
            db2_ok = True; db2_msg = "ok"
        except Exception as e:
            db2_msg = f"erro: {e}"
    return {
        "FLOWISE_URL": FLOWISE_URL,
        "FLOWISE_CHATFLOW_ID": FLOWISE_CHATFLOW_ID,
        "FLOWISE_PREDICTION_URL": FLOWISE_PREDICTION_URL,
        "effective_url": url,
        "db_configured": bool(DATABASE_URL),
        "db_ok": db_ok,
        "db_msg": db_msg,
        "db2_configured": bool(DATABASE_URL_RESUMO_SEMANAL),
        "db2_ok": db2_ok,
        "db2_msg": db2_msg,
        "deltas": {
            "DELTA_TEMPO_RESUMO": DELTA_TEMPO_RESUMO,
            "DELTA_TEMPO": DELTA_TEMPO,
            "TEMPO_ATUALIZACAO": TEMPO_ATUALIZACAO,
        }
    }

@app.get("/profile")
async def profile(email: str = Query(default=DEFAULT_USER_EMAIL)):
    valores, datas, ok_db, msg_db = get_latest_infos(email)
    resumo_pessoa, cargo_pessoa, id_pessoa = get_basic_profile(email)
    historico = get_historico_bot(email)
    resumos_sem = get_resumos_semanal(email)
    return {
        "ok": ok_db,
        "msg": msg_db,
        "email": email,
        "perfil": {
            "resumo_pessoa": resumo_pessoa,
            "cargo": cargo_pessoa,
            "id": id_pessoa,
            "historico_bot": historico,
            "resumos_semanal": resumos_sem,
        },
        "valores": valores,
        "datas": {k: (str(v) if v else None) for k,v in datas.items()},
    }

@app.get("/health")
async def health():
    return PlainTextResponse("ok")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("widget_oi_fastapi:app", host="0.0.0.0", port=8000, reload=True)