import json, os
import oracledb
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

conn = oracledb.connect(
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    dsn=os.getenv("DB_DSN"),
)

view = os.getenv("VIEW_NAME", "VW_PROTOCOLO_DASHBOARD")

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
    FROM {view}
    ORDER BY DATA_ABERTURA
"""

cursor = conn.cursor()
cursor.execute(sql)
columns = [col[0] for col in cursor.description]
rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
cursor.close()
conn.close()

out = os.path.join(os.path.dirname(__file__), "dados_raw.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"success": True, "total": len(rows), "data": rows}, f, ensure_ascii=False, default=str)

print(f"OK! {len(rows)} registros salvos em dados_raw.json")
