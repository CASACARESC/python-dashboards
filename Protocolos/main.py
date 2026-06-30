# main.py — API FastAPI para o Dashboard de Protocolos
# Dependências: pip install fastapi uvicorn oracledb python-dotenv

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import oracledb
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── CONFIGURAÇÃO ─────────────────────────────────────────
DB_CONFIG = {
    "user":     os.getenv("DB_USER", "SEU_USUARIO"),
    "password": os.getenv("DB_PASS", "SUA_SENHA"),
    "dsn":      os.getenv("DB_DSN",  "HOST:PORTA/SERVICO"),
}
VIEW = os.getenv("VIEW_NAME", "VW_PROTOCOLO_DASHBOARD")

app = FastAPI(title="Dashboard Protocolos API")

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── ROTA PRINCIPAL ───────────────────────────────────────
@app.get("/api/protocolos")
def get_protocolos(
    dateFrom: Optional[str] = Query(None, description="Mês inicial YYYY-MM"),
    dateTo:   Optional[str] = Query(None, description="Mês final YYYY-MM"),
    limit:    Optional[int] = Query(None, description="Limite de registros"),
):
    where_clauses = []
    bind_params   = {}

    if dateFrom:
        where_clauses.append("TO_CHAR(DATA_ABERTURA, 'YYYY-MM') >= :date_from")
        bind_params["date_from"] = dateFrom

    if dateTo:
        where_clauses.append("TO_CHAR(DATA_ABERTURA, 'YYYY-MM') <= :date_to")
        bind_params["date_to"] = dateTo

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    limit_sql = f"FETCH FIRST {limit} ROWS ONLY" if limit else ""

    sql = f"""
        SELECT
            TO_CHAR(DATA_ABERTURA, 'YYYY-MM')   AS INICIADOEM_STR,
            TO_CHAR(FINALIZADOEM, 'YYYY-MM')   AS FINALIZADOEM_STR,
            TBTIPOPROTOCOLO,
            SITUACAO,
            SITUACAOINTERNA_SITUACAO,
            ASSUNTO_ASSUNTO,
            ATENDENTE_QUE_FINALIZOU,
            ATENDENTE_QUE_ABRIU,
            BANDEJA,
            ATENDEU_PRAZO_ANS                  AS "ATENDEU__PRAZO_ANS",
            ACEITOUFORADOPRAZO,
            TIPOPRAZO_NOME,
            NVL(VALORBRUTO, 0)                 AS VALORBRUTO
        FROM {VIEW}
        {where_sql}
        ORDER BY DATA_ABERTURA
        {limit_sql}
    """

    try:
        conn   = oracledb.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql, bind_params)
        columns = [col[0] for col in cursor.description]
        rows    = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return {"success": True, "total": len(rows), "data": rows}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── HEALTHCHECK ──────────────────────────────────────────
@app.get("/api/health")
def health():
    try:
        conn   = oracledb.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM DUAL")
        cursor.close()
        conn.close()
        return {"status": "ok", "db": "conectado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── START (dev) ──────────────────────────────────────────
# Rode com: uvicorn main:app --host 0.0.0.0 --port 3001 --reload
