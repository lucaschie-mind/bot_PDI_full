
-- schema.sql

CREATE TABLE IF NOT EXISTS user_docs (
  id SERIAL PRIMARY KEY,
  user_email TEXT NOT NULL,
  doc_key TEXT,
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_docs_email ON user_docs(user_email);

CREATE TABLE IF NOT EXISTS chat_logs (
  id SERIAL PRIMARY KEY,
  user_email TEXT,
  question TEXT,
  answer TEXT,
  raw JSONB,
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_logs_email ON chat_logs(user_email);

CREATE TABLE IF NOT EXISTS user_mappings (
  id SERIAL PRIMARY KEY,
  sandbox_email TEXT UNIQUE,
  prod_email TEXT,
  created_at TIMESTAMP DEFAULT now()
);
