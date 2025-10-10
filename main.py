"""
Loader de aplicação FastAPI para Railway/uvicorn.

Mantém o arquivo original com nome `widget_fastapi.py` e exporta `app`
sem precisar renomear o arquivo.
"""
import importlib.util
from pathlib import Path

BOT_FILE = Path(__file__).with_name("widget_fastapi.py")

spec = importlib.util.spec_from_file_location("botapp", str(BOT_FILE))
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader, "Falha ao carregar módulo do BOT"
spec.loader.exec_module(module)

# Exporta o app FastAPI para o uvicorn
app = getattr(module, "app", None)
if app is None:
    raise RuntimeError("Objeto `app` (FastAPI) não encontrado em widget_fastapi.py")
