
# Bot PDI - Flowise Embed Widget (v2)

Arquivos gerados para facilitar a integração do widget Flowise embutido no seu sistema via iframe.

## Conteúdo
- `proxy_flowise.py` - FastAPI proxy que serve `widget.html` e expõe `/chat`, `/debug_payload`, `/debug_routes`, `/health`.
- `widget.html` - widget que carrega `embed.min.js` do Flowise e inicializa `Flowise.initFull` com parâmetros (hardcoded por padrão, sobrescrevíveis por query params ou postMessage).
- `parent_snippet.html` - snippet para colar na aplicação host (usa `/mindsight/api/v1/current_user/` para pegar email/id e envia via postMessage).
- `ChatWidget.jsx` - componente React pronto para projetos React (usa `user` prop in the format {id, host, userId, userName, userEmail}).
- `schema.sql` - SQL com tabelas mínimas (user_docs, chat_logs, user_mappings).
- `.gitignore` - recomendado.

## Quick start (local)
1. Copie os arquivos para uma pasta de projeto.
2. Instale dependências e rode o proxy:
```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install fastapi uvicorn requests pydantic
python -m uvicorn proxy_flowise:app --reload --port 8001
```
3. Abra `http://127.0.0.1:8001/widget` — widget usa valores hardcoded por padrão.
4. Para inicializar com dados específicos, abra `http://127.0.0.1:8001/widget?id=<CHATFLOW_ID>&host=<FLOWISE_HOST>&userId=<ID>&userName=<NAME>&userEmail=<EMAIL>`
5. Ou use the `parent_snippet.html` approach (postMessage) para enviar dados do parent.

## Security notes
- NÃO comitar segredos. Use env variables in Railway for `FLOWISE_URL`, `FLOWISE_API_KEY`, `ALLOWED_ORIGINS`, `DATABASE_URL`.
- Prefer server-side validation (JWT or session verification) before trusting user info sent from parent.
