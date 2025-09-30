# flowise-proxy

Proxy FastAPI para orquestrar chamadas ao Flowise Cloud com controle de acesso por usuário.

## Arquivos
- `proxy_flowise.py` - app principal
- `requirements.txt` - dependências
- `Procfile` - para Railway
- `Dockerfile` - opcional

## Variáveis de ambiente
- `FLOWISE_URL` (obrigatório): endpoint do seu chatflow no Flowise Cloud, ex: `https://cloud.flowiseai.com/api/v1/prediction/<CHATFLOW_ID>`
- `DATABASE_URL` (opcional): Postgres (para `user_docs` e `chat_logs`)
- `ALLOWED_ORIGINS` (opcional): origem(s) permitidas para CORS, ex: `https://full.mindsight.com.br` (padrão `*`)
- `JWT_SECRET` (opcional): chave para verificar JWT HS256 (se disponível)
- `JWT_ALGORITHM` (opcional): `HS256` por padrão

## Deploy no Railway (passos rápidos)
1. Crie um repo no GitHub com estes arquivos.
2. No Railway, crie um novo projeto → Connect GitHub → selecione o repo.
3. Configure as variáveis de ambiente no painel do Railway: `FLOWISE_URL`, `DATABASE_URL` (se usar), `ALLOWED_ORIGINS`.
4. Deploy. O Railway irá expor uma URL pública `https://<seu-projeto>.up.railway.app`.

## Teste local (antes de deploy)
1. pip install -r requirements.txt
2. export FLOWISE_URL="https://cloud.flowiseai.com/api/v1/prediction/<CHATFLOW_ID>"
3. uvicorn proxy_flowise:app --reload --port 8001
4. Teste com curl:

```bash
curl -X POST http://127.0.0.1:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"email":"lucas@mindsight.com.br","question":"confirma meu email"}'
```

## Observações de segurança
- Em produção, garanta que o proxy valide o JWT (não aceite email arbitrário do cliente).
- Restrinja `ALLOWED_ORIGINS` ao domínio(s) da sua aplicação.
- Não exponha `FLOWISE_URL` com credenciais em front-end.
