# Bot PDI (FastAPI + Flowise) — Deploy no Railway (sandbox)

Este repositório contém o BOT PDI pronto para embed (iframe), com fluxo:
**Diagnóstico → (escolher 2 competências) → PDI 70-20-10 com metas SMART**.

> 🔐 **Sem segredos no Git**: use apenas o painel **Railway → Variables**. O arquivo `.env.example` é só um modelo.

## Arquivos importantes
- `widget_fastapi.py` — seu BOT
- `main.py` — loader que exporta `app` do arquivo acima (não precisa renomear)
- `requirements.txt` — dependências
- `Procfile` — comando para iniciar o servidor (uvicorn)
- `runtime.txt` — versão do Python (opcional)
- `.env.example` — **modelo** de variáveis (sem valores)
- `.gitignore` — ignora `.env` e artefatos
- `railway.json` — config opcional para orquestração no Railway

## Variáveis de ambiente (Railway → Variables)
Copie os **nomes** abaixo do `.env.example` e preencha os **valores** no Railway:
- `FLOWISE_PREDICTION_URL` **(recomendado)** — `https://<host>/api/v1/prediction/<chatflowId>`
- `FLOWISE_URL` + `FLOWISE_CHATFLOW_ID` **(alternativo)** — use se não tiver o endpoint direto
- `FLOWISE_API_KEY` — se sua instância exigir auth
- `DATABASE_URL` — string de conexão (ex.: do Postgres provisionado no Railway). Se exigir TLS, use `?sslmode=require`.
- `DB_SCHEMA` — ex.: `public`
- `DELTA_TEMPO_RESUMO`, `DELTA_TEMPO`, `TEMPO_ATUALIZACAO` — janelas de dados (opcional)
- `DEFAULT_USER_*` — apenas para sandbox/debug local

## Deploy (via GitHub → Railway)
1. Faça o push do repositório contendo os arquivos acima.
2. No **Railway**, clique em _New Project_ → **Deploy from GitHub Repo** → selecione o repositório.
3. Em **Variables**, cadastre as variáveis (sem subir `.env`).
4. O Railway detecta o `Procfile` e inicia com:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
5. A URL pública ficará disponível em **Settings → Domains**. Use-a no seu **iframe** de embed.

## Testes rápidos
- `GET /` — homepage do bot
- `POST /api/message` — endpoint do chat
  ```bash
  curl -X POST "$RAILWAY_URL/api/message" \
    -H 'Content-Type: application/json' \
    -d '{"message":"PDI","userId":"sandbox123","userName":"Teste","userEmail":"teste@example.com"}'
  ```

## Dicas e troubleshooting
- **Flowise** instável? Prefira `FLOWISE_PREDICTION_URL` (com chatflow embutido). O bot já usa `sessionId` diário `id_pessoa:YYYY-MM-DD` e _retries_.
- **Postgres** com SSL obrigatório? Acrescente `?sslmode=require` ao `DATABASE_URL`.
- **Quebra de linha no front**: use `white-space: pre-line` na classe `.msg` (já suportado no HTML do bot).
- **Renomeou o arquivo do bot?** Ajuste o nome em `main.py` (constante `BOT_FILE`).

---

Qualquer ajuste (Dockerfile, healthcheck custom, CI/CD), dá para incluir depois.
