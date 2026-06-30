# app.py — API Flask + servidor do Dashboard de Protocolos
# Dependências: pip install flask flask-cors oracledb python-dotenv gunicorn
# Produção: gunicorn -w 4 -b 0.0.0.0:3001 app:app

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import oracledb
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)
CORS(app)  # Permite chamadas do dashboard (cross-origin)

# ── CONFIGURAÇÃO DO BANCO ────────────────────────────────
DB_CONFIG = {
    "user":     os.getenv("DB_USER", "SEU_USUARIO"),
    "password": os.getenv("DB_PASS", "SUA_SENHA"),
    "dsn":      os.getenv("DB_DSN",  "HOST:PORTA/SERVICO"),
    # Ex: "oracle.empresa.com:1521/ORCL"
}

# Nome da view no Oracle
VIEW_NAME = os.getenv("VIEW_NAME", "VW_PROTOCOLO_DASHBOARD")

# ── HELPER — conexão ─────────────────────────────────────
def get_conn():
    # Modo thin: não precisa do Oracle Instant Client instalado!
    return oracledb.connect(**DB_CONFIG)


# ── DASHBOARD ────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")


# ── ROTA PRINCIPAL ───────────────────────────────────────
@app.route("/api/protocolos", methods=["GET"])
def get_protocolos():
    date_from = request.args.get("dateFrom")  # Ex: 2024-01
    date_to   = request.args.get("dateTo")    # Ex: 2025-12

    where_clauses = []
    bind_params   = {}

    if date_from:
        where_clauses.append("TO_CHAR(DATA_ABERTURA, 'YYYY-MM') >= :date_from")
        bind_params["date_from"] = date_from

    if date_to:
        where_clauses.append("TO_CHAR(DATA_ABERTURA, 'YYYY-MM') <= :date_to")
        bind_params["date_to"] = date_to

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sql = f"""
        SELECT
            TO_CHAR(DATA_ABERTURA, 'YYYY-MM')  AS INICIADOEM_STR,
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
        FROM {VIEW_NAME}
        {where_sql}
        ORDER BY DATA_ABERTURA
    """

    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, bind_params)

        # Pega os nomes das colunas automaticamente
        columns = [col[0] for col in cursor.description]

        # Converte cada linha em dicionário
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "total": len(rows),
            "sql": sql.strip(),
            "data": rows
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── HEALTHCHECK ──────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM DUAL")
        cursor.close()
        conn.close()
        return jsonify({"status": "ok", "db": "conectado"})
    except Exception as e:
        return jsonify({"status": "erro", "db": str(e)}), 500


# ── START ────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001, debug=True)
