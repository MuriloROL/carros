"""
Entrada da Serverless Function da Vercel (runtime Python).

O backend FastAPI vive em `agent/app`. Aqui montamos esse app sob `/api` para a
Vercel expor como função. O rewrite em vercel.json manda todo `/api/*` para este
arquivo; o mount remove o prefixo `/api` e entrega o caminho limpo (ex.:
`/mcqueen-tco`) para o app real, sem precisar mexer nas rotas existentes.
"""
from __future__ import annotations
import os
import sys

# `agent/` precisa estar no sys.path para os `import app...` resolverem tanto na
# Vercel (os arquivos vêm via includeFiles do vercel.json) quanto localmente.
AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent"))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from fastapi import FastAPI
from app.main import app as agent_app

app = FastAPI()
app.mount("/api", agent_app)
