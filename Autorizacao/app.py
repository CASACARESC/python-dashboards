# app.py — Dashboard de Autorizações (FastAPI + oracledb async)
# Iniciar: python app.py   (porta 3002)
# Deps:    pip install fastapi uvicorn oracledb python-dotenv

import asyncio
import sys

# oracledb thin mode não funciona com ProactorEventLoop no Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from contextlib import asynccontextmanager
import oracledb
import os
import json
import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

DB_USER   = os.getenv("DB_USER")
DB_PASS   = os.getenv("DB_PASS")
DB_DSN    = os.getenv("DB_DSN")
TABLE    = os.getenv("TABLE_NAME", "benner_saude.vw_autorizacao_geral")

COL_DATE   = '"data solicita\u00e7\u00e3o"'
COL_TYPE   = '"Tipo guia"'
COL_CITY   = '"cidade da execu\u00e7\u00e3o"'
COL_CODE   = '"codigo do item"'
COL_AGE    = '"IDADE"'
COL_ATTEND = '"TIPO ATENDIMENTO"'

_pool: oracledb.AsyncConnectionPool | None = None
_schema_cache: dict | None = None


# ── LIFESPAN (inicializa pool na startup) ─────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    _pool = oracledb.create_pool_async(
        user=DB_USER, password=DB_PASS, dsn=DB_DSN,
        min=3, max=12, increment=1,
    )
    print(f"[OK] Pool async criado — {TABLE}")
    yield
    _pool.close()
    print("[OK] Pool fechado")


app = FastAPI(title="Dashboard Autorizações", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origins=["http://localhost:3002", "http://127.0.0.1:3002"],
                   allow_methods=["GET", "POST"],
                   allow_headers=["*"])



# ── HELPERS ───────────────────────────────────────────────
def serialize(v):
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    return v

def col_sql(name: str) -> str:
    return f'"{name}"' if (" " in name or name != name.upper()) else name

def parse_filters(raw: str) -> list:
    try:
        return json.loads(raw) if raw else []
    except Exception:
        return []

def build_where(date_from, date_to, extra: list = None):
    clauses, params = [], {}
    sub_clauses = []   # cláusulas para o interior da subquery de incidência
    sub_params  = {}   # bind variables com nomes únicos (_s) para evitar duplicatas
    incidence_pending = []

    # 1. Filtros de data
    if date_from:
        clauses.append(f"TO_CHAR({COL_DATE},'YYYY-MM') >= :date_from")
        sub_clauses.append(f"TO_CHAR({COL_DATE},'YYYY-MM') >= :s_date_from")
        params["date_from"]   = date_from
        sub_params["s_date_from"] = date_from
    if date_to:
        clauses.append(f"TO_CHAR({COL_DATE},'YYYY-MM') <= :date_to")
        sub_clauses.append(f"TO_CHAR({COL_DATE},'YYYY-MM') <= :s_date_to")
        params["date_to"]   = date_to
        sub_params["s_date_to"] = date_to

    # 2. Filtros normais (lista, range, texto) — incidência é processada depois
    for fi, f in enumerate(extra or []):
        ftype = f.get("type")
        c = col_sql(f["col"]) if f.get("col") else None
        if ftype == "incidence":
            incidence_pending.append((fi, f))
        elif ftype == "range":
            if f.get("min") not in (None, ""):
                clauses.append(f"{c} >= :f{fi}min")
                sub_clauses.append(f"{c} >= :s_f{fi}min")
                params[f"f{fi}min"]   = float(f["min"])
                sub_params[f"s_f{fi}min"] = float(f["min"])
            if f.get("max") not in (None, ""):
                clauses.append(f"{c} <= :f{fi}max")
                sub_clauses.append(f"{c} <= :s_f{fi}max")
                params[f"f{fi}max"]   = float(f["max"])
                sub_params[f"s_f{fi}max"] = float(f["max"])
        elif ftype == "text":
            if f.get("val"):
                v = f"%{f['val'].upper()}%"
                clauses.append(f"UPPER({c}) LIKE :f{fi}v")
                sub_clauses.append(f"UPPER({c}) LIKE :s_f{fi}v")
                params[f"f{fi}v"]   = v
                sub_params[f"s_f{fi}v"] = v
        else:  # list
            vals = [v for v in (f.get("vals") or []) if v]
            if vals:
                ph     = ", ".join([f":f{fi}v{vi}"   for vi in range(len(vals))])
                sub_ph = ", ".join([f":s_f{fi}v{vi}" for vi in range(len(vals))])
                clauses.append(f"NVL({c},'(vazio)') IN ({ph})")
                sub_clauses.append(f"NVL({c},'(vazio)') IN ({sub_ph})")
                for vi, v in enumerate(vals):
                    params[f"f{fi}v{vi}"]   = v
                    sub_params[f"s_f{fi}v{vi}"] = v

    # 3. WHERE base para a subquery (nomes _s para não colidir com o WHERE externo)
    base_sub_where = ("WHERE " + " AND ".join(sub_clauses)) if sub_clauses else ""

    # sub_params só entra no dict se houver filtro de incidência (senão oracledb rejeita vars não usadas)
    if incidence_pending:
        params.update(sub_params)

    # 4. Filtros de incidência: a contagem respeita o base_sub_where
    for fi, f in incidence_pending:
        c         = col_sql(f["col"])
        min_count = max(1, int(f.get("min") or 1))
        days      = max(1, int(f.get("days") or 1))
        per_bene  = bool(f.get("perBene", False))
        bene_col  = col_sql("Nome Beneficiario")
        # Converte DATE para número de dias (subtração de data base) para usar RANGE numérico
        # INTERVAL 'N' DAY falha no Oracle quando N >= 100 (precisão padrão DAY é 2 dígitos)
        _date_num = f"(TRUNC({COL_DATE}) - DATE '2000-01-01')"
        if per_bene:
            clauses.append(
                f"(NVL(TO_CHAR({c}),'') || CHR(0) || NVL(TO_CHAR({bene_col}),'')) IN ("
                f"SELECT DISTINCT NVL(TO_CHAR(ic),'') || CHR(0) || NVL(TO_CHAR(ib),'') FROM ("
                f"SELECT {c} AS ic, {bene_col} AS ib, "
                f"COUNT(*) OVER (PARTITION BY {c}, {bene_col} ORDER BY {_date_num} "
                f"RANGE BETWEEN {days} PRECEDING AND CURRENT ROW) AS icnt "
                f"FROM {TABLE} {base_sub_where}) WHERE icnt >= {min_count})"
            )
        else:
            clauses.append(
                f"{c} IN ("
                f"SELECT DISTINCT ic FROM ("
                f"SELECT {c} AS ic, "
                f"COUNT(*) OVER (PARTITION BY {c} ORDER BY {_date_num} "
                f"RANGE BETWEEN {days} PRECEDING AND CURRENT ROW) AS icnt "
                f"FROM {TABLE} {base_sub_where}) WHERE icnt >= {min_count})"
            )

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params

async def run_query(sql: str, params: dict = None) -> list[dict]:
    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(sql, params or {})
            except Exception as e:
                print(f"\n[SQL ERROR] {e}\n[SQL] {sql}\n[PARAMS] {params}\n")
                raise
            cols = [d[0] for d in cur.description]
            rows = await cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]

async def fetch_schema() -> dict:
    global _schema_cache
    if _schema_cache:
        return _schema_cache
    owner, tbl = TABLE.split(".") if "." in TABLE else (None, TABLE)
    if owner:
        rows = await run_query(
            "SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS "
            "WHERE OWNER = :o AND TABLE_NAME = :t ORDER BY COLUMN_ID",
            {"o": owner.upper(), "t": tbl.upper()})
    else:
        rows = await run_query(
            "SELECT COLUMN_NAME, DATA_TYPE FROM USER_TAB_COLUMNS "
            "WHERE TABLE_NAME = :t ORDER BY COLUMN_ID",
            {"t": tbl.upper()})
    _schema_cache = {r["COLUMN_NAME"]: r["DATA_TYPE"] for r in rows}
    return _schema_cache


# ── STATIC FILES ──────────────────────────────────────────
_DIR  = os.path.dirname(__file__)
_HTML = os.path.join(_DIR, "dashboard.html")

@app.get("/")
async def index():
    return RedirectResponse("/dashboard")

@app.get("/dashboard")
async def dashboard():
    return FileResponse(_HTML, media_type="text/html")


@app.get("/plotly.min.js")
async def plotly_js():
    return FileResponse(os.path.join(_DIR, "plotly.min.js"),
                        media_type="application/javascript",
                        headers={"Cache-Control": "public, max-age=31536000"})


# ── HEALTH ────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    try:
        await run_query("SELECT 1 FROM DUAL")
        return {"status": "ok", "db": "conectado", "table": TABLE}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── SCHEMA ────────────────────────────────────────────────
@app.get("/api/schema")
async def get_schema():
    owner, tbl = TABLE.split(".") if "." in TABLE else (None, TABLE)
    try:
        if owner:
            rows = await run_query(
                "SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE "
                "FROM ALL_TAB_COLUMNS WHERE OWNER=:o AND TABLE_NAME=:t ORDER BY COLUMN_ID",
                {"o": owner.upper(), "t": tbl.upper()})
        else:
            rows = await run_query(
                "SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE "
                "FROM USER_TAB_COLUMNS WHERE TABLE_NAME=:t ORDER BY COLUMN_ID",
                {"t": tbl.upper()})
        return {"success": True, "table": TABLE, "columns": rows}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── KPIs ──────────────────────────────────────────────────
@app.get("/api/kpis")
async def get_kpis(
    dateFrom: Optional[str] = None,
    dateTo:   Optional[str] = None,
    filters:  Optional[str] = None,
):
    where, params = build_where(dateFrom, dateTo, parse_filters(filters))
    try:
        import asyncio
        total_task = run_query(f"SELECT COUNT(*) AS N FROM {TABLE} {where}", params)
        tipo_task  = run_query(
            f"SELECT NVL({COL_TYPE},'(vazio)') AS TIPO, COUNT(*) AS QTD "
            f"FROM {TABLE} {where} GROUP BY {COL_TYPE} ORDER BY 2 DESC FETCH FIRST 20 ROWS ONLY",
            params)
        total_rows, tipo_rows = await asyncio.gather(total_task, tipo_task)
        return {
            "success":  True,
            "total":    total_rows[0]["N"],
            "por_tipo": [{"tipo": r["TIPO"], "qtd": r["QTD"]} for r in tipo_rows],
        }
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── CHART: por mês ────────────────────────────────────────
@app.get("/api/chart/mes")
async def chart_mes(dateFrom: Optional[str]=None, dateTo: Optional[str]=None,
                    filters: Optional[str]=None):
    where, params = build_where(dateFrom, dateTo, parse_filters(filters))
    try:
        rows = await run_query(
            f"SELECT TO_CHAR({COL_DATE},'YYYY-MM') AS MES, COUNT(*) AS QTD "
            f"FROM {TABLE} {where} GROUP BY TO_CHAR({COL_DATE},'YYYY-MM') ORDER BY 1", params)
        return {"success": True, "data": rows}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── CHART: tipo de guia ───────────────────────────────────
@app.get("/api/chart/tipo")
async def chart_tipo(dateFrom: Optional[str]=None, dateTo: Optional[str]=None,
                     filters: Optional[str]=None):
    where, params = build_where(dateFrom, dateTo, parse_filters(filters))
    try:
        rows = await run_query(
            f"SELECT NVL({COL_TYPE},'(vazio)') AS TIPO, COUNT(*) AS QTD "
            f"FROM {TABLE} {where} GROUP BY {COL_TYPE} ORDER BY 2 DESC FETCH FIRST 15 ROWS ONLY",
            params)
        return {"success": True, "data": rows}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── CHART: tipo de atendimento ────────────────────────────
@app.get("/api/chart/atendimento")
async def chart_atendimento(dateFrom: Optional[str]=None, dateTo: Optional[str]=None,
                             filters: Optional[str]=None):
    where, params = build_where(dateFrom, dateTo, parse_filters(filters))
    try:
        rows = await run_query(
            f"SELECT NVL({COL_ATTEND},'(vazio)') AS ATEND, COUNT(*) AS QTD "
            f"FROM {TABLE} {where} GROUP BY {COL_ATTEND} ORDER BY 2 DESC", params)
        return {"success": True, "data": rows}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── CHART: cidades ────────────────────────────────────────
@app.get("/api/chart/cidade")
async def chart_cidade(dateFrom: Optional[str]=None, dateTo: Optional[str]=None,
                       filters: Optional[str]=None):
    where, params = build_where(dateFrom, dateTo, parse_filters(filters))
    try:
        rows = await run_query(
            f"SELECT NVL({COL_CITY},'(vazio)') AS CIDADE, COUNT(*) AS QTD "
            f"FROM {TABLE} {where} GROUP BY {COL_CITY} ORDER BY 2 DESC FETCH FIRST 10 ROWS ONLY",
            params)
        return {"success": True, "data": rows}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── CHART: código de item ─────────────────────────────────
@app.get("/api/chart/codigo")
async def chart_codigo(dateFrom: Optional[str]=None, dateTo: Optional[str]=None,
                       filters: Optional[str]=None):
    where, params = build_where(dateFrom, dateTo, parse_filters(filters))
    try:
        rows = await run_query(
            f"SELECT NVL({COL_CODE},'(vazio)') AS CODIGO, COUNT(*) AS QTD "
            f"FROM {TABLE} {where} GROUP BY {COL_CODE} ORDER BY 2 DESC FETCH FIRST 15 ROWS ONLY",
            params)
        return {"success": True, "data": rows}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── CHART: faixa etária ───────────────────────────────────
@app.get("/api/chart/faixa")
async def chart_faixa(dateFrom: Optional[str]=None, dateTo: Optional[str]=None,
                      filters: Optional[str]=None):
    where, params = build_where(dateFrom, dateTo, parse_filters(filters))
    faixa = (f"CASE WHEN {COL_AGE}<=18 THEN '0-18' "
             f"WHEN {COL_AGE}<=23 THEN '19-23' "
             f"WHEN {COL_AGE}<=28 THEN '24-28' "
             f"WHEN {COL_AGE}<=33 THEN '29-33' "
             f"WHEN {COL_AGE}<=38 THEN '34-38' "
             f"WHEN {COL_AGE}<=43 THEN '39-43' "
             f"WHEN {COL_AGE}<=48 THEN '44-48' "
             f"WHEN {COL_AGE}<=53 THEN '49-53' "
             f"WHEN {COL_AGE}<=58 THEN '54-58' "
             f"ELSE '59+' END")
    try:
        rows = await run_query(
            f"SELECT {faixa} AS FAIXA, COUNT(*) AS QTD "
            f"FROM {TABLE} {where} GROUP BY {faixa} ORDER BY MIN({COL_AGE})", params)
        return {"success": True, "data": rows}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── EXPORT: cubo dimensional (todos os dados, sem filtro) ─
@app.get("/api/export/cube")
async def export_cube():
    faixa = (f"CASE WHEN {COL_AGE}<=18 THEN '0-18' "
             f"WHEN {COL_AGE}<=23 THEN '19-23' "
             f"WHEN {COL_AGE}<=28 THEN '24-28' "
             f"WHEN {COL_AGE}<=33 THEN '29-33' "
             f"WHEN {COL_AGE}<=38 THEN '34-38' "
             f"WHEN {COL_AGE}<=43 THEN '39-43' "
             f"WHEN {COL_AGE}<=48 THEN '44-48' "
             f"WHEN {COL_AGE}<=53 THEN '49-53' "
             f"WHEN {COL_AGE}<=58 THEN '54-58' "
             f"ELSE '59+' END")
    try:
        import asyncio
        main_task = run_query(
            f"SELECT TO_CHAR({COL_DATE},'YYYY-MM') AS MES,"
            f"NVL({COL_TYPE},'(vazio)') AS TIPO,"
            f"NVL({COL_ATTEND},'(vazio)') AS ATEND,"
            f"NVL({COL_CITY},'(vazio)') AS CIDADE,"
            f"{faixa} AS FAIXA,"
            f"COUNT(*) AS QTD "
            f"FROM {TABLE} "
            f"GROUP BY TO_CHAR({COL_DATE},'YYYY-MM'),{COL_TYPE},{COL_ATTEND},{COL_CITY},{faixa}")
        code_task = run_query(
            f"SELECT NVL({COL_CODE},'(vazio)') AS CODIGO,"
            f"TO_CHAR({COL_DATE},'YYYY-MM') AS MES,"
            f"NVL({COL_TYPE},'(vazio)') AS TIPO,"
            f"NVL({COL_ATTEND},'(vazio)') AS ATEND,"
            f"COUNT(*) AS QTD "
            f"FROM {TABLE} "
            f"GROUP BY {COL_CODE},TO_CHAR({COL_DATE},'YYYY-MM'),{COL_TYPE},{COL_ATTEND}")
        main_rows, code_rows = await asyncio.gather(main_task, code_task)
        return {"success": True, "main": main_rows, "codes": code_rows}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── VALORES DISTINTOS (filtros) ───────────────────────────
@app.get("/api/filter-values")
async def filter_values(col: str):
    try:
        schema = await fetch_schema()
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})
    # Case-insensitive lookup: find the real column name as stored in Oracle
    schema_upper = {k.upper(): k for k in schema}
    col_real = schema_upper.get(col.upper())
    if col_real is None:
        raise HTTPException(400, {"success": False, "error": f"Coluna '{col}' não encontrada"})
    c = col_sql(col_real)
    try:
        rows = await run_query(
            f"SELECT NVL(TO_CHAR({c}),'(vazio)') AS VAL, COUNT(*) AS QTD "
            f"FROM {TABLE} GROUP BY {c} ORDER BY 2 DESC FETCH FIRST 200 ROWS ONLY")
        return {"success": True, "col": col, "data": [{"val": r["VAL"], "qtd": r["QTD"]} for r in rows], "type": schema[col_real]}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── AGREGAÇÃO GENÉRICA ────────────────────────────────────
@app.get("/api/agg")
async def get_agg(
    col:      str,
    dateFrom: Optional[str] = None,
    dateTo:   Optional[str] = None,
    filters:  Optional[str] = None,
    top:      int = 20,
):
    try:
        schema = await fetch_schema()
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})
    schema_upper = {k.upper(): k for k in schema}
    col_real = schema_upper.get(col.upper())
    if col_real is None:
        raise HTTPException(400, {"success": False, "error": f"Coluna '{col}' não encontrada"})
    c = col_sql(col_real)
    where, params = build_where(dateFrom, dateTo, parse_filters(filters))
    try:
        rows = await run_query(
            f"SELECT NVL(TO_CHAR({c}),'(vazio)') AS LABEL, COUNT(*) AS QTD "
            f"FROM {TABLE} {where} GROUP BY {c} ORDER BY 2 DESC FETCH FIRST {top} ROWS ONLY",
            params)
        return {"success": True, "col": col, "data": rows}
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── ROWS: registros detalhados (usado pela tabela de incidência) ───────────────
@app.get("/api/rows")
async def get_rows(
    dateFrom: Optional[str] = None,
    dateTo:   Optional[str] = None,
    filters:  Optional[str] = None,
    limit:    int = 2000,
):
    # CTE usa TODOS os filtros (inclusive código do item) para encontrar os beneficiários corretos
    full_where, params = build_where(dateFrom, dateTo, parse_filters(filters))
    bene_col = '"Nome Beneficiario"'
    date_clauses = []
    if dateFrom:
        date_clauses.append(f"TO_CHAR({COL_DATE},'YYYY-MM') >= :date_from")
    if dateTo:
        date_clauses.append(f"TO_CHAR({COL_DATE},'YYYY-MM') <= :date_to")
    date_where = ("WHERE " + " AND ".join(date_clauses)) if date_clauses else ""

    cols = (
        f't.{bene_col} AS "Nome Beneficiario",'
        f't.{COL_DATE} AS "Data Solicitacao",'
        f't.{COL_TYPE} AS "Tipo Guia",'
        f't."descrição do evento" AS "Descricao Evento",'
        f't.{COL_CODE} AS "Codigo Item",'
        f't.{COL_ATTEND} AS "Tipo Atendimento",'
        f't.{COL_CITY} AS "Cidade"'
    )
    try:
        sql = (
            f"WITH mb AS (SELECT DISTINCT {bene_col} FROM {TABLE} {full_where}) "
            f"SELECT {cols} FROM {TABLE} t "
            f"INNER JOIN mb ON t.{bene_col} = mb.{bene_col} "
            f"{date_where} "
            f"ORDER BY t.{bene_col}, t.{COL_DATE} DESC "
            f"FETCH FIRST {limit} ROWS ONLY"
        )
        rows = await run_query(sql, params)
        return {
            "success": True,
            "total": len(rows),
            "rows": [{k: serialize(v) for k, v in r.items()} for r in rows]
        }
    except Exception as e:
        raise HTTPException(500, {"success": False, "error": str(e)})


# ── START ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=3002, reload=False, loop="none")
