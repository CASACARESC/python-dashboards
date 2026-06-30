"""
Sistema de Auditoria Médica - Quimioterapia e Medicamentos de Alto Custo
Versão 1.0 | EPAGRI - Contas Médicas
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date
import warnings
import io

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
#  CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Auditoria Médica | Quimio",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  CSS CUSTOMIZADO
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 16px;
        border-left: 5px solid #dc3545;
        margin-bottom: 10px;
    }
    .metric-card.warning {
        border-left-color: #ffc107;
    }
    .metric-card.info {
        border-left-color: #0d6efd;
    }
    .metric-card.success {
        border-left-color: #198754;
    }
    .regra-header {
        font-size: 1.05rem;
        font-weight: 700;
        color: #212529;
    }
    .badge-critico {
        background: #dc3545;
        color: white;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .badge-alto {
        background: #fd7e14;
        color: white;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .badge-medio {
        background: #ffc107;
        color: #212529;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .badge-baixo {
        background: #0d6efd;
        color: white;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #dee2e6;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  CARREGAMENTO DOS DADOS
# ─────────────────────────────────────────────
@st.cache_data(show_spinner="Carregando e processando dados...")
def load_data(uploaded_file=None, default_path: str = None):
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, engine="xlrd")
    elif default_path:
        df = pd.read_excel(default_path, engine="xlrd")
    else:
        return None

    # Normalizar encoding
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(lambda x: x.encode("latin1").decode("utf-8", errors="replace")
                                if isinstance(x, str) else x)

    # Converter datas
    for col in ["REALIZACAO", "DT_AVISO", "DATA_NASCIMENTO"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Calcular idade na data de referência (último REF do arquivo)
    ref_date = datetime(2026, 4, 1)
    df["IDADE"] = df["DATA_NASCIMENTO"].apply(
        lambda x: int((ref_date - x).days // 365.25) if pd.notnull(x) else None
    )

    # Preço unitário
    df["PRECO_UNIT"] = df.apply(
        lambda r: r["VALOR"] / r["QTDE"] if pd.notnull(r["QTDE"]) and r["QTDE"] > 0 else None,
        axis=1,
    )

    # Diferença valor cobrado × pago
    df["DIFF_VALOR"] = df["VALOR"] - df["VALOR_PAGO"]

    # Sexo upper
    df["SEXO"] = df["SEXO"].str.strip().str.upper()

    return df


# ─────────────────────────────────────────────
#  DICIONÁRIOS DE REGRAS MÉDICAS
# ─────────────────────────────────────────────

# Medicamentos com indicação predominantemente feminina
MEDS_FEMININOS = {
    "HERCEPTIN": "Câncer de mama (HER2+) – indicação predominantemente feminina",
    "PERJETA": "Câncer de mama (HER2+) – indicação predominantemente feminina",
    "LETROZOL": "Hormônio-terapia para câncer de mama – exclusivo feminino",
    "ANASTROZOL": "Hormônio-terapia para câncer de mama – exclusivo feminino",
    "EXEMESTANO": "Hormônio-terapia para câncer de mama – exclusivo feminino",
    "KISQALI": "Câncer de mama HR+ – indicação predominantemente feminina",
    "VERZENIOS": "Câncer de mama HR+ HER2- – indicação predominantemente feminina",
    "IBRANCE": "Câncer de mama HR+ HER2- – indicação predominantemente feminina",
    "KADCYLA": "Câncer de mama HER2+ – indicação predominantemente feminina",
    "ENHERTU": "Câncer de mama HER2+ – indicação predominantemente feminina",
    "FASLODEX": "Câncer de mama ER+ – exclusivo feminino",
    "FULVESTRANTO": "Câncer de mama ER+ – exclusivo feminino",
}

# Medicamentos com indicação exclusivamente masculina
MEDS_MASCULINOS = {
    "ABIRATERONA": "Câncer de próstata – exclusivo masculino",
    "ACETATO DE ABIRATERONA": "Câncer de próstata – exclusivo masculino",
    "ERLEADA": "Câncer de próstata (apalutamida) – exclusivo masculino",
    "XTANDI": "Câncer de próstata (enzalutamida) – exclusivo masculino",
    "NUBEQA": "Câncer de próstata (darolutamida) – exclusivo masculino",
    "ZYTIGA": "Câncer de próstata – exclusivo masculino",
    "LUPRON": "Câncer de próstata / bloqueio androgênico – verificar se feminino",
    "ELIGARD": "Câncer de próstata – exclusivo masculino",
    "DEGARELIX": "Câncer de próstata – exclusivo masculino",
}

# Medicamentos com limite de idade mínima (adultos)
MEDS_ADULTOS_APENAS = {
    "ABIRATERONA": 18,
    "ACETATO DE ABIRATERONA": 18,
    "ERLEADA": 18,
    "LETROZOL": 18,
    "ANASTROZOL": 18,
    "VERZENIOS": 18,
    "IBRANCE": 18,
    "KISQALI": 18,
    "ERLEADA": 18,
    "XTANDI": 18,
}

# Medicamentos oncológicos de alto custo (usados para identificar sessões sem medicamento)
MEDS_ONCOLOGICOS_KEYWORDS = [
    "KEYTRUDA", "AVASTIN", "HERCEPTIN", "PERJETA", "MABTHERA", "RITUXAN",
    "BLAUIMUNO", "DALINVI", "LIBTAYO", "OPDIVO", "TECENTRIQ", "IMFINZI",
    "TREMFYA", "DUPIXENT", "COSENTYX", "SIMPONI", "XOLAIR", "ZARZIO",
    "FAULDLEUCO", "FAULDFLUOR", "FAULDCARBO", "OXALIBBS", "TEMOZOLOMIDA",
    "VIVAXXIA", "GENUXAL", "ONTAX", "ERLEADA", "VERZENIOS", "LETROZOL",
    "ZYTIGA", "REMSIMA", "XGEVA", "DENOSUMABE", "BEVACIZUMABE", "TRASTUZUMABE",
    "PERTUZUMABE", "RITUXIMABE", "CARBOPLATINA", "OXALIPLATINA", "PACLITAXEL",
    "DOCETAXEL", "CICLOFOSFAMIDA", "ETOPOSIDO",
]

SESSAO_KEYWORDS = [
    "sess", "quimio", "oncol", "imunoterapia", "imunobiol", "infus",
    "terapia oncol", "planejamento e 1"
]


# ─────────────────────────────────────────────
#  MOTOR DE AUDITORIA
# ─────────────────────────────────────────────
def run_audit(df: pd.DataFrame) -> dict:
    results = {}

    # ── R01: Duplicatas exatas ───────────────────────────────────────────────
    mask_dup = df.duplicated(subset=["BENEF", "SERVICO", "REALIZACAO", "VALOR"], keep=False)
    r01 = df[mask_dup].copy()
    r01["ANOMALIA"] = "Duplicata exata (mesmo beneficiário, serviço, data e valor)"
    r01["SEVERIDADE"] = "CRITICO"
    r01["REGRA"] = "R01"
    results["R01"] = {
        "titulo": "R01 – Duplicatas Exatas",
        "descricao": "Mesmo beneficiário, mesmo código TUSS, mesma data e mesmo valor faturado.",
        "severidade": "CRITICO",
        "df": r01,
        "impacto": r01["VALOR"].sum() / 2,  # metade é duplicado
    }

    # ── R02: Mesma guia diferente valor ─────────────────────────────────────
    grp = df.groupby(["BENEF", "SERVICO", "REALIZACAO"])
    r02_rows = []
    for key, g in grp:
        if len(g) > 1 and g["VALOR"].nunique() > 1:
            g2 = g.copy()
            g2["ANOMALIA"] = f"Mesmo serviço/paciente/data com valores divergentes: {list(g['VALOR'].unique())}"
            g2["SEVERIDADE"] = "CRITICO"
            g2["REGRA"] = "R02"
            r02_rows.append(g2)
    r02 = pd.concat(r02_rows) if r02_rows else pd.DataFrame()
    results["R02"] = {
        "titulo": "R02 – Mesmo Serviço com Valores Divergentes",
        "descricao": "Mesmo beneficiário, mesmo código TUSS e mesma data com valores diferentes – possível fracionamento ou cobrança indevida.",
        "severidade": "CRITICO",
        "df": r02,
        "impacto": r02["VALOR"].sum() if not r02.empty else 0,
    }

    # ── R03: Medicamento incompatível com sexo ───────────────────────────────
    r03_rows = []
    for keyword, motivo in MEDS_FEMININOS.items():
        mask = df["DESCRICAO"].str.contains(keyword, case=False, na=False) & (df["SEXO"] == "M")
        rows = df[mask].copy()
        rows["ANOMALIA"] = f"Medicamento feminino em paciente MASCULINO – {motivo}"
        rows["SEVERIDADE"] = "ALTO"
        rows["REGRA"] = "R03"
        r03_rows.append(rows)
    for keyword, motivo in MEDS_MASCULINOS.items():
        mask = df["DESCRICAO"].str.contains(keyword, case=False, na=False) & (df["SEXO"] == "F")
        rows = df[mask].copy()
        rows["ANOMALIA"] = f"Medicamento masculino em paciente FEMININO – {motivo}"
        rows["SEVERIDADE"] = "ALTO"
        rows["REGRA"] = "R03"
        r03_rows.append(rows)
    r03 = pd.concat(r03_rows) if r03_rows else pd.DataFrame()
    results["R03"] = {
        "titulo": "R03 – Medicamento Incompatível com Sexo",
        "descricao": "Medicamentos com indicação predominantemente ou exclusivamente de um gênero sendo cobrados para o sexo oposto.",
        "severidade": "ALTO",
        "df": r03,
        "impacto": r03["VALOR"].sum() if not r03.empty else 0,
    }

    # ── R04: Medicamento adulto em menores de 18 ─────────────────────────────
    r04_rows = []
    for keyword, min_age in MEDS_ADULTOS_APENAS.items():
        mask = df["DESCRICAO"].str.contains(keyword, case=False, na=False) & (df["IDADE"] < min_age)
        rows = df[mask].copy().reset_index(drop=True)
        if rows.empty:
            continue
        rows["ANOMALIA"] = (
            "Medicamento adulto (" + keyword + ") em paciente com "
            + rows["IDADE"].astype(str) + " anos (minimo " + str(min_age) + ")"
        )
        rows["SEVERIDADE"] = "ALTO"
        rows["REGRA"] = "R04"
        r04_rows.append(rows)
    r04 = pd.concat(r04_rows) if r04_rows else pd.DataFrame()
    results["R04"] = {
        "titulo": "R04 – Medicamento Adulto em Paciente Pediátrico",
        "descricao": "Medicamentos sem aprovação pediátrica sendo faturados para pacientes menores de 18 anos.",
        "severidade": "ALTO",
        "df": r04,
        "impacto": r04["VALOR"].sum() if not r04.empty else 0,
    }

    # ── R05: Preço unitário anômalo ─────────────────────────────────────────
    r05_rows = []
    preco_stats = df[df["PRECO_UNIT"].notnull() & (df["VALOR"] > 100)].groupby("DESCRICAO")["PRECO_UNIT"].agg(
        ["median", "std", "count"]
    )
    preco_stats = preco_stats[preco_stats["count"] >= 2].copy()
    preco_stats["zscore_thresh"] = preco_stats.apply(
        lambda r: r["median"] + 3 * r["std"] if pd.notnull(r["std"]) and r["std"] > 0 else None, axis=1
    )
    for desc, stats in preco_stats.iterrows():
        if pd.isnull(stats["zscore_thresh"]):
            continue
        mask = (
            df["DESCRICAO"] == desc
        ) & (
            df["PRECO_UNIT"].notnull()
        ) & (
            df["PRECO_UNIT"] > stats["zscore_thresh"]
        )
        rows = df[mask].copy().reset_index(drop=True)
        if rows.empty:
            continue
        lim_txt = f"{stats['zscore_thresh']:.4f}"
        med_txt = f"{stats['median']:.4f}"
        rows["ANOMALIA"] = (
            "Preco unitario R$ " + rows["PRECO_UNIT"].map(lambda v: f"{v:.4f}")
            + f" acima de 3sigma (mediana R$ {med_txt}, limite R$ {lim_txt})"
        )
        rows["SEVERIDADE"] = "ALTO"
        rows["REGRA"] = "R05"
        r05_rows.append(rows)
    r05 = pd.concat(r05_rows) if r05_rows else pd.DataFrame()
    results["R05"] = {
        "titulo": "R05 – Preço Unitário Estatisticamente Anômalo",
        "descricao": "Preço por unidade do medicamento acima de 3 desvios padrões da mediana do mesmo item no período.",
        "severidade": "ALTO",
        "df": r05,
        "impacto": r05["VALOR"].sum() if not r05.empty else 0,
    }

    # ── R06: Quantidade anômala ──────────────────────────────────────────────
    r06_rows = []
    qtde_stats = df[df["QTDE"].notnull() & (df["QTDE"] > 0)].groupby("DESCRICAO")["QTDE"].agg(
        ["median", "std", "count"]
    )
    qtde_stats = qtde_stats[qtde_stats["count"] >= 2].copy()
    for desc, stats in qtde_stats.iterrows():
        if pd.isnull(stats["std"]) or stats["std"] == 0:
            continue
        limite = stats["median"] + 3 * stats["std"]
        mask = (df["DESCRICAO"] == desc) & (df["QTDE"] > limite)
        rows = df[mask].copy().reset_index(drop=True)
        if rows.empty:
            continue
        lim_txt = f"{limite:.1f}"
        med_txt = f"{stats['median']:.1f}"
        rows["ANOMALIA"] = (
            "Quantidade " + rows["QTDE"].map(lambda v: f"{v:.0f}")
            + f" acima de 3sigma (mediana {med_txt}, limite {lim_txt})"
        )
        rows["SEVERIDADE"] = "MEDIO"
        rows["REGRA"] = "R06"
        r06_rows.append(rows)
    r06 = pd.concat(r06_rows) if r06_rows else pd.DataFrame()
    results["R06"] = {
        "titulo": "R06 – Quantidade Anômala por Item",
        "descricao": "Quantidade faturada acima de 3 desvios padrões em relação aos demais registros do mesmo item.",
        "severidade": "MEDIO",
        "df": r06,
        "impacto": r06["VALOR"].sum() if not r06.empty else 0,
    }

    # ── R07: Valor cobrado ≠ valor pago ─────────────────────────────────────
    r07 = df[df["DIFF_VALOR"].abs() > 0.05].copy().reset_index(drop=True)
    r07["ANOMALIA"] = (
        "Cobrado R$ " + r07["VALOR"].map(lambda v: f"{v:.2f}")
        + " / Pago R$ " + r07["VALOR_PAGO"].map(lambda v: f"{v:.2f}")
        + " (diferenca R$ " + r07["DIFF_VALOR"].map(lambda v: f"{v:.2f}") + ")"
    )
    r07["SEVERIDADE"] = r07["DIFF_VALOR"].abs().map(
        lambda x: "CRITICO" if x > 500 else ("ALTO" if x > 50 else "MEDIO")
    )
    r07["REGRA"] = "R07"
    results["R07"] = {
        "titulo": "R07 – Divergência entre Valor Cobrado e Valor Pago",
        "descricao": "Diferença entre o valor faturado pelo prestador e o valor efetivamente pago pelo plano.",
        "severidade": "MEDIO",
        "df": r07,
        "impacto": r07["DIFF_VALOR"].sum(),
    }

    # ── R08: Sessão de quimio sem medicamento oncológico ────────────────────
    def is_sessao(desc):
        if not isinstance(desc, str):
            return False
        d = desc.lower()
        return any(k.lower() in d for k in SESSAO_KEYWORDS)

    def is_med_onco(desc):
        if not isinstance(desc, str):
            return False
        d = desc.upper()
        return any(k.upper() in d for k in MEDS_ONCOLOGICOS_KEYWORDS)

    r08_rows = []
    for benef, grp_b in df.groupby("BENEF"):
        for data_r, grp_d in grp_b.groupby("REALIZACAO"):
            has_sessao = grp_d["DESCRICAO"].apply(is_sessao).any()
            has_med = grp_d["DESCRICAO"].apply(is_med_onco).any()
            if has_sessao and not has_med:
                rows = grp_d[grp_d["DESCRICAO"].apply(is_sessao)].copy()
                rows["ANOMALIA"] = "Sessão de quimio/imunoterapia sem medicamento oncológico na mesma data"
                rows["SEVERIDADE"] = "MEDIO"
                rows["REGRA"] = "R08"
                r08_rows.append(rows)
    r08 = pd.concat(r08_rows) if r08_rows else pd.DataFrame()
    results["R08"] = {
        "titulo": "R08 – Sessão Oncológica sem Medicamento Correspondente",
        "descricao": "Cobrança de sessão de quimioterapia/imunoterapia sem registro de medicamento oncológico na mesma data.",
        "severidade": "MEDIO",
        "df": r08,
        "impacto": r08["VALOR"].sum() if not r08.empty else 0,
    }

    # ── R09: Alta frequência de sessões ─────────────────────────────────────
    r09_rows = []
    # Sessões oncológicas (quimio EV) mínimo 7 dias entre sessões
    sessao_ev_keywords = ["quimio", "oncol", "imunoterapia", "terapia oncol", "planejamento e 1"]
    mask_sessoes_ev = df["DESCRICAO"].str.lower().apply(
        lambda d: any(k in d for k in sessao_ev_keywords) if isinstance(d, str) else False
    )
    df_sessoes = df[mask_sessoes_ev].copy()
    for benef, grp_b in df_sessoes.groupby("BENEF"):
        datas = grp_b["REALIZACAO"].dropna().sort_values().unique()
        for i in range(1, len(datas)):
            delta = (datas[i] - datas[i - 1]).days
            if 0 < delta < 5:  # menos de 5 dias entre sessões oncológicas EV
                rows = grp_b[grp_b["REALIZACAO"].isin([datas[i - 1], datas[i]])].copy()
                rows["ANOMALIA"] = f"Intervalo de {delta} dia(s) entre sessões oncológicas (mínimo esperado: 5 dias)"
                rows["SEVERIDADE"] = "ALTO"
                rows["REGRA"] = "R09"
                r09_rows.append(rows)
    r09 = pd.concat(r09_rows) if r09_rows else pd.DataFrame()
    # remove duplicates
    if not r09.empty:
        r09 = r09.drop_duplicates(subset=["BENEF", "REALIZACAO", "SERVICO"])
    results["R09"] = {
        "titulo": "R09 – Intervalo Mínimo entre Sessões Oncológicas",
        "descricao": "Paciente com sessões de quimioterapia/imunoterapia em intervalos inferiores a 5 dias.",
        "severidade": "ALTO",
        "df": r09,
        "impacto": r09["VALOR"].sum() if not r09.empty else 0,
    }

    # ── R10: Realização posterior ao aviso ─────────────────────────────────
    r10 = df[(df["REALIZACAO"].notnull()) & (df["DT_AVISO"].notnull()) &
             (df["REALIZACAO"] > df["DT_AVISO"])].copy().reset_index(drop=True)
    r10["ANOMALIA"] = (
        "Data de realizacao (" + r10["REALIZACAO"].dt.strftime("%d/%m/%Y")
        + ") posterior ao aviso (" + r10["DT_AVISO"].dt.strftime("%d/%m/%Y") + ")"
    )
    r10["SEVERIDADE"] = "MEDIO"
    r10["REGRA"] = "R10"
    results["R10"] = {
        "titulo": "R10 – Realização Posterior ao Aviso/Autorização",
        "descricao": "Data de realização do procedimento é posterior à data de aviso ao plano, sugerindo inconsistência no faturamento.",
        "severidade": "MEDIO",
        "df": r10,
        "impacto": r10["VALOR"].sum(),
    }

    # ── R11: Procedimento oncológico em criança (<18 anos) ──────────────────
    meds_onco_mask = df["DESCRICAO"].apply(is_med_onco)
    r11 = df[meds_onco_mask & (df["IDADE"].notnull()) & (df["IDADE"] < 18)].copy().reset_index(drop=True)
    r11["ANOMALIA"] = (
        "Medicamento oncologico de alta complexidade para paciente com "
        + r11["IDADE"].astype(int).astype(str) + " anos"
    )
    r11["SEVERIDADE"] = "ALTO"
    r11["REGRA"] = "R11"
    results["R11"] = {
        "titulo": "R11 – Medicamento Oncológico em Paciente Pediátrico",
        "descricao": "Medicamentos oncológicos de alta complexidade (quimio/biológicos/checkpoint inhibitors) prescritos para pacientes menores de 18 anos.",
        "severidade": "ALTO",
        "df": r11,
        "impacto": r11["VALOR"].sum() if not r11.empty else 0,
    }

    # ── R12: Alta concentração de guias por prestador num único dia ─────────
    r12_rows = []
    grp_prest = df.groupby(["CPF_CNPJ_PRESTADOR_EXECUTOR", "REALIZACAO"])
    for (prest, data_r), g in grp_prest:
        benef_count = g["BENEF"].nunique()
        if benef_count >= 10:  # ≥10 pacientes distintos no mesmo dia → suspeito
            g2 = g.copy()
            g2["ANOMALIA"] = (
                f"Prestador {prest} atendeu {benef_count} beneficiários distintos em {data_r.date() if pd.notnull(data_r) else 'N/A'}"
            )
            g2["SEVERIDADE"] = "MEDIO"
            g2["REGRA"] = "R12"
            r12_rows.append(g2)
    r12 = pd.concat(r12_rows) if r12_rows else pd.DataFrame()
    results["R12"] = {
        "titulo": "R12 – Alta Concentração de Atendimentos por Prestador em um Dia",
        "descricao": "Prestador executou serviços para ≥10 beneficiários distintos em uma única data – possível superfaturamento ou guias clone.",
        "severidade": "MEDIO",
        "df": r12,
        "impacto": r12["VALOR"].sum() if not r12.empty else 0,
    }

    # ── R13: Valor total zero pago com cobrança ──────────────────────────────
    r13 = df[(df["VALOR"] > 0) & (df["VALOR_PAGO"] == 0)].copy().reset_index(drop=True)
    r13["ANOMALIA"] = "Cobrado R$ " + r13["VALOR"].map(lambda v: f"{v:.2f}") + " mas valor pago = R$ 0,00"
    r13["SEVERIDADE"] = "BAIXO"
    r13["REGRA"] = "R13"
    results["R13"] = {
        "titulo": "R13 – Item Cobrado com Valor Pago Zero",
        "descricao": "Itens faturados pelo prestador mas com pagamento zero pelo plano – pode indicar glosa não tratada ou cobrança indevida.",
        "severidade": "BAIXO",
        "df": r13,
        "impacto": r13["VALOR"].sum() if not r13.empty else 0,
    }

    # ── R14: Paciente com volume total > percentil 99 ────────────────────────
    valor_por_benef = df.groupby("BENEF")["VALOR"].sum()
    p99 = valor_por_benef.quantile(0.99)
    benefs_alto = valor_por_benef[valor_por_benef > p99].index
    r14 = df[df["BENEF"].isin(benefs_alto)].copy().reset_index(drop=True)
    r14["TOTAL_BENEF"] = r14["BENEF"].map(valor_por_benef)
    r14["ANOMALIA"] = (
        "Beneficiario " + r14["BENEF"].astype(str)
        + " com custo total R$ " + r14["TOTAL_BENEF"].map(lambda v: f"{v:,.2f}")
        + f" (P99 = R$ {p99:,.2f})"
    )
    r14["SEVERIDADE"] = "ALTO"
    r14["REGRA"] = "R14"
    results["R14"] = {
        "titulo": "R14 – Beneficiário com Custo Outlier (Acima P99)",
        "descricao": "Beneficiários cujo custo total no período supera o percentil 99 dos demais – requer revisão individualizada.",
        "severidade": "ALTO",
        "df": r14,
        "impacto": r14["VALOR"].sum() if not r14.empty else 0,
    }

    # ── R15: Medicamento de alto custo com QTDE = 0 ─────────────────────────
    r15 = df[(df["QTDE"] == 0) & (df["VALOR"] > 0)].copy().reset_index(drop=True)
    r15["ANOMALIA"] = "Quantidade zero com valor faturado - item sem quantidade definida"
    r15["SEVERIDADE"] = "ALTO"
    r15["REGRA"] = "R15"
    results["R15"] = {
        "titulo": "R15 – Faturamento com Quantidade Zero",
        "descricao": "Itens com QTDE = 0 mas com valor cobrado – inconsistência de faturamento que pode esconder superfaturamento.",
        "severidade": "ALTO",
        "df": r15,
        "impacto": r15["VALOR"].sum() if not r15.empty else 0,
    }

    return results


# ─────────────────────────────────────────────
#  HELPERS DE DISPLAY
# ─────────────────────────────────────────────
SEV_COLOR = {
    "CRITICO": "#dc3545",
    "ALTO": "#fd7e14",
    "MEDIO": "#ffc107",
    "BAIXO": "#0d6efd",
}

SEV_ORDER = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAIXO": 3}

COLS_DISPLAY = [
    "REGRA", "SEVERIDADE", "BENEF", "SEXO", "IDADE",
    "SERVICO", "DESCRICAO", "QTDE", "REALIZACAO", "DT_AVISO",
    "CREDENCIADO_LOCAL_EXECUTOR", "VALOR", "VALOR_PAGO",
    "DIFF_VALOR", "PRECO_UNIT", "ANOMALIA",
]


def badge(sev: str) -> str:
    colors = {
        "CRITICO": ("#dc3545", "white"),
        "ALTO": ("#fd7e14", "white"),
        "MEDIO": ("#ffc107", "#212529"),
        "BAIXO": ("#0d6efd", "white"),
    }
    bg, fg = colors.get(sev, ("#6c757d", "white"))
    return f'<span style="background:{bg};color:{fg};border-radius:4px;padding:2px 8px;font-size:0.75rem;font-weight:700">{sev}</span>'


def fmt_currency(v):
    return f"R$ {v:,.2f}" if pd.notnull(v) else "–"


def _df_to_html_table(df_in: pd.DataFrame, cols: list) -> str:
    """Converte DataFrame em tabela HTML estilizada."""
    df_t = df_in[[c for c in cols if c in df_in.columns]].copy()

    # Formatar colunas de data
    for dc in ["REALIZACAO", "DT_AVISO"]:
        if dc in df_t.columns:
            df_t[dc] = pd.to_datetime(df_t[dc], errors="coerce").apply(
                lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else ""
            )

    # Formatar colunas numéricas
    for nc in ["VALOR", "VALOR_PAGO", "DIFF_VALOR"]:
        if nc in df_t.columns:
            df_t[nc] = df_t[nc].apply(
                lambda v: f"R$ {v:,.2f}" if pd.notnull(v) else ""
            )
    if "PRECO_UNIT" in df_t.columns:
        df_t["PRECO_UNIT"] = df_t["PRECO_UNIT"].apply(
            lambda v: f"R$ {v:,.4f}" if pd.notnull(v) else ""
        )

    sev_colors = {
        "CRITICO": "#f8d7da", "ALTO": "#ffe5d0",
        "MEDIO": "#fff3cd",   "BAIXO": "#cfe2ff",
    }

    rows_html = ""
    for _, row in df_t.iterrows():
        sev = str(row.get("SEVERIDADE", "")).strip().upper() if "SEVERIDADE" in df_t.columns else ""
        bg = sev_colors.get(sev, "")
        style = f' style="background:{bg}"' if bg else ""
        cells = "".join(
            f"<td>{'' if pd.isnull(v) else v}</td>" for v in row
        )
        rows_html += f"<tr{style}>{cells}</tr>\n"

    headers = "".join(f"<th>{c}</th>" for c in df_t.columns)
    return (
        '<div style="overflow-x:auto;margin-bottom:20px">'
        '<table class="audit-table">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table></div>"
    )


def export_html(df: pd.DataFrame, audit_results: dict) -> bytes:
    """Gera relatório HTML completo e autocontido com gráficos e tabelas."""
    from plotly.io import to_html as pio_to_html

    plotly_cdn = '<script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>'

    def fig_html(fig, first=False) -> str:
        return pio_to_html(
            fig,
            full_html=False,
            include_plotlyjs="cdn" if first else False,
            config={"responsive": True, "displayModeBar": True},
        )

    sections = []
    first_chart = True

    # ── 1. GRÁFICOS DE VISÃO GERAL ─────────────────────────────────────────
    # Pizza grupo TISS
    fig_grupo = px.pie(
        df.groupby("GRUPO")["VALOR"].sum().reset_index(),
        names="GRUPO", values="VALOR",
        title="Distribuição do Valor por Grupo TISS", hole=0.4,
    )
    fig_grupo.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))

    # Top 10 medicamentos
    top10 = (
        df[df["VALOR"] > 100].groupby("DESCRICAO")["VALOR"]
        .sum().nlargest(10).reset_index()
    )
    top10["DESCRICAO"] = top10["DESCRICAO"].str[:55]
    fig_top10 = px.bar(
        top10, x="VALOR", y="DESCRICAO", orientation="h",
        title="Top 10 Itens por Valor Total",
        color="VALOR", color_continuous_scale="Reds",
        labels={"VALOR": "Valor Total (R$)", "DESCRICAO": "Item"},
    )
    fig_top10.update_layout(
        height=380, showlegend=False,
        yaxis=dict(autorange="reversed"),
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=50, b=20),
    )

    visao_html = (
        "<section id='visao'>"
        "<h2>Visao Geral do Arquivo</h2>"
        "<div class='chart-grid'>"
        f"<div class='chart-cell'>{fig_html(fig_grupo, first=True)}</div>"
        f"<div class='chart-cell'>{fig_html(fig_top10)}</div>"
        "</div></section>"
    )
    first_chart = False
    sections.append(visao_html)

    # ── 2. RESUMO DAS REGRAS ───────────────────────────────────────────────
    sev_label = {"CRITICO": "CRITICO", "ALTO": "ALTO", "MEDIO": "MEDIO", "BAIXO": "BAIXO"}
    sev_bg = {
        "CRITICO": "#f8d7da", "ALTO": "#ffe5d0",
        "MEDIO": "#fff3cd",   "BAIXO": "#cfe2ff",
    }
    summary_rows_html = ""
    for key, r in audit_results.items():
        n = len(r["df"])
        sev = r["severidade"].upper()
        bg = sev_bg.get(sev, "")
        impacto_txt = f"R$ {r['impacto']:,.2f}" if pd.notnull(r["impacto"]) else "–"
        summary_rows_html += (
            f'<tr style="background:{bg}">'
            f"<td>{r['titulo']}</td>"
            f'<td><strong>{sev}</strong></td>'
            f"<td style='text-align:center'><strong>{n}</strong></td>"
            f"<td style='text-align:right'>{impacto_txt}</td>"
            "</tr>\n"
        )

    resumo_html = (
        "<section id='resumo'>"
        "<h2>Resumo das Regras de Auditoria</h2>"
        "<table class='audit-table'>"
        "<thead><tr><th>Regra</th><th>Severidade</th><th>Ocorrencias</th><th>Impacto (R$)</th></tr></thead>"
        f"<tbody>{summary_rows_html}</tbody>"
        "</table>"
    )

    # Gráfico severidade
    df_sev_counts = pd.DataFrame([
        {"Severidade": r["severidade"].upper(), "Ocorrencias": len(r["df"])}
        for r in audit_results.values()
    ]).groupby("Severidade")["Ocorrencias"].sum().reset_index()
    df_sev_counts["Ordem"] = df_sev_counts["Severidade"].map(
        {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAIXO": 3}
    )
    df_sev_counts = df_sev_counts.sort_values("Ordem")
    fig_sev = px.bar(
        df_sev_counts, x="Severidade", y="Ocorrencias",
        title="Anomalias por Severidade", color="Severidade",
        color_discrete_map={
            "CRITICO": "#dc3545", "ALTO": "#fd7e14",
            "MEDIO": "#ffc107",   "BAIXO": "#0d6efd",
        },
    )
    fig_sev.update_layout(height=320, showlegend=False, margin=dict(l=20, r=20, t=50, b=20))

    # Gráfico impacto por regra
    df_imp = pd.DataFrame([
        {"Regra": r["titulo"][:50], "Impacto": r["impacto"], "Severidade": r["severidade"].upper()}
        for r in audit_results.values() if r["impacto"] > 0
    ]).nlargest(8, "Impacto")
    fig_imp = px.bar(
        df_imp, x="Impacto", y="Regra", orientation="h",
        title="Top Regras por Impacto Financeiro",
        color="Severidade",
        color_discrete_map={
            "CRITICO": "#dc3545", "ALTO": "#fd7e14",
            "MEDIO": "#ffc107",   "BAIXO": "#0d6efd",
        },
    )
    fig_imp.update_layout(
        height=350, showlegend=False,
        yaxis=dict(autorange="reversed"),
        margin=dict(l=20, r=20, t=50, b=20),
    )

    resumo_html += (
        "<div class='chart-grid'>"
        f"<div class='chart-cell'>{fig_html(fig_sev)}</div>"
        f"<div class='chart-cell'>{fig_html(fig_imp)}</div>"
        "</div></section>"
    )
    sections.append(resumo_html)

    # ── 3. DETALHE POR REGRA ───────────────────────────────────────────────
    icon_map = {"CRITICO": "🔴", "ALTO": "🟠", "MEDIO": "🟡", "BAIXO": "🔵"}
    detail_html = "<section id='detalhes'><h2>Detalhamento por Regra</h2>"
    for key, r in audit_results.items():
        sev = r["severidade"].upper()
        icon = icon_map.get(sev, "⚪")
        n = len(r["df"])
        impacto_txt = f"R$ {r['impacto']:,.2f}" if pd.notnull(r["impacto"]) else "–"
        bg = sev_bg.get(sev, "#f8f9fa")
        sev_col = SEV_COLOR.get(sev, "#6c757d")
        detail_html += (
            f'<div class="regra-block" style="border-left:5px solid {sev_col}">'
            f"<h3>{icon} {r['titulo']}</h3>"
            f"<p><strong>Descricao:</strong> {r['descricao']}</p>"
            f"<p><strong>Severidade:</strong> "
            f"<span style='background:{sev_col};color:white;"
            f"padding:2px 8px;border-radius:4px;font-weight:700'>{sev}</span> &nbsp;"
            f"<strong>Ocorrencias:</strong> {n} &nbsp;"
            f"<strong>Impacto:</strong> {impacto_txt}</p>"
        )
        if n == 0:
            detail_html += "<p style='color:#198754'>✅ Nenhuma anomalia detectada.</p>"
        else:
            detail_html += _df_to_html_table(r["df"], COLS_DISPLAY)

            # Gráfico específico para R14
            if key == "R14" and not r["df"].empty:
                top_benef = (
                    r["df"].groupby("BENEF")["TOTAL_BENEF"].first()
                    .sort_values(ascending=False).head(10).reset_index()
                )
                fig_r14 = px.bar(
                    top_benef, x="BENEF", y="TOTAL_BENEF",
                    title="Top Beneficiarios por Custo Total",
                    labels={"TOTAL_BENEF": "Valor Total (R$)", "BENEF": "Beneficiario"},
                    color="TOTAL_BENEF", color_continuous_scale="Oranges",
                )
                fig_r14.update_layout(
                    height=320, coloraxis_showscale=False,
                    margin=dict(l=20, r=20, t=50, b=20),
                )
                detail_html += fig_html(fig_r14)

        detail_html += "</div>"
    detail_html += "</section>"
    sections.append(detail_html)

    # ── 4. ANALISES COMPLEMENTARES ────────────────────────────────────────
    comp_html = "<section id='complementar'><h2>Analises Complementares</h2>"

    # Dispersão de preço unitário
    meds_multi = (
        df[df["PRECO_UNIT"].notnull() & (df["VALOR"] > 500)]
        .groupby("DESCRICAO").filter(lambda x: len(x) >= 2)
    )
    if not meds_multi.empty:
        top_meds_idx = meds_multi.groupby("DESCRICAO")["VALOR"].sum().nlargest(15).index
        df_box = meds_multi[meds_multi["DESCRICAO"].isin(top_meds_idx)].copy()
        df_box["DESC_CURTA"] = df_box["DESCRICAO"].str[:45] + "..."
        fig_box = px.box(
            df_box, x="DESC_CURTA", y="PRECO_UNIT",
            title="Dispersao de Preco Unitario – Top 15 Itens de Alto Custo",
            points="all", color="DESC_CURTA",
            labels={"PRECO_UNIT": "Preco Unitario (R$)", "DESC_CURTA": "Medicamento"},
        )
        fig_box.update_layout(
            height=500, showlegend=False, xaxis_tickangle=-45,
            margin=dict(l=20, r=20, t=50, b=180),
        )
        comp_html += f"<h3>Dispersao de Preco Unitario</h3>{fig_html(fig_box)}"

    # Evolução temporal
    df_time = df.copy()
    df_time["MES"] = df_time["REALIZACAO"].dt.to_period("M").astype(str)
    df_time_grp = df_time.groupby(["MES", "GRUPO"])["VALOR"].sum().reset_index()
    fig_time = px.bar(
        df_time_grp, x="MES", y="VALOR", color="GRUPO",
        title="Valor Total por Mes e Grupo TISS",
        labels={"VALOR": "Valor (R$)", "MES": "Mes"},
    )
    fig_time.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20))
    comp_html += f"<h3>Evolucao Temporal</h3>{fig_html(fig_time)}"

    # Prestadores
    df_prest = (
        df.groupby("CREDENCIADO_LOCAL_EXECUTOR")
        .agg(Total=("VALOR", "sum"), Registros=("VALOR", "count"), Benefs=("BENEF", "nunique"))
        .sort_values("Total", ascending=False).head(20).reset_index()
    )
    df_prest["PREST_CURTO"] = df_prest["CREDENCIADO_LOCAL_EXECUTOR"].str[:45]
    fig_prest = px.bar(
        df_prest, x="Total", y="PREST_CURTO", orientation="h",
        title="Top 20 Prestadores por Valor Total",
        color="Total", color_continuous_scale="Oranges",
        labels={"Total": "Valor Total (R$)", "PREST_CURTO": "Prestador"},
    )
    fig_prest.update_layout(
        height=560, showlegend=False, coloraxis_showscale=False,
        yaxis=dict(autorange="reversed"), margin=dict(l=20, r=20, t=50, b=20),
    )
    comp_html += f"<h3>Analise por Prestador</h3>{fig_html(fig_prest)}"

    # Distribuição por beneficiário
    valor_benef = df.groupby("BENEF")["VALOR"].sum().reset_index()
    fig_hist = px.histogram(
        valor_benef, x="VALOR", nbins=50,
        title="Distribuicao de Custo Total por Beneficiario",
        labels={"VALOR": "Custo Total (R$)", "count": "Qtd Beneficiarios"},
        color_discrete_sequence=["#0d6efd"],
    )
    fig_hist.update_layout(height=360, margin=dict(l=20, r=20, t=50, b=20))
    comp_html += f"<h3>Distribuicao por Beneficiario</h3>{fig_html(fig_hist)}"

    # Tabela top beneficiários (P95+)
    p95 = valor_benef["VALOR"].quantile(0.95)
    df_top_benef = (
        valor_benef[valor_benef["VALOR"] >= p95]
        .sort_values("VALOR", ascending=False)
        .rename(columns={"BENEF": "Beneficiario", "VALOR": "Custo Total"})
    )
    df_top_benef["Custo Total"] = df_top_benef["Custo Total"].map(lambda v: f"R$ {v:,.2f}")
    comp_html += (
        "<h3>Beneficiarios com Custo Acima do P95</h3>"
        + _df_to_html_table(df_top_benef, list(df_top_benef.columns))
    )

    comp_html += "</section>"
    sections.append(comp_html)

    # ── KPIs de cabeçalho ─────────────────────────────────────────────────
    total_anom = sum(len(r["df"]) for r in audit_results.values())
    total_imp = sum(r["impacto"] for r in audit_results.values() if pd.notnull(r["impacto"]))
    criticos = sum(1 for r in audit_results.values() if len(r["df"]) > 0 and r["severidade"] == "CRITICO")
    dt_min = df["REALIZACAO"].min().strftime("%d/%m/%Y")
    dt_max = df["REALIZACAO"].max().strftime("%d/%m/%Y")

    kpi_html = f"""
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-val">{len(df):,}</div><div class="kpi-lbl">Total Registros</div></div>
      <div class="kpi-card"><div class="kpi-val">{df["BENEF"].nunique():,}</div><div class="kpi-lbl">Beneficiarios</div></div>
      <div class="kpi-card"><div class="kpi-val">R$ {df["VALOR"].sum():,.2f}</div><div class="kpi-lbl">Valor Total</div></div>
      <div class="kpi-card kpi-danger"><div class="kpi-val">{total_anom:,}</div><div class="kpi-lbl">Total Anomalias</div></div>
      <div class="kpi-card kpi-danger"><div class="kpi-val">{criticos}</div><div class="kpi-lbl">Regras Criticas</div></div>
      <div class="kpi-card kpi-danger"><div class="kpi-val">R$ {total_imp:,.2f}</div><div class="kpi-lbl">Impacto Financeiro</div></div>
    </div>
    <p style="color:#6c757d;font-size:0.9rem">Periodo: {dt_min} a {dt_max}</p>
    """

    # ── MENU DE NAVEGAÇÃO ─────────────────────────────────────────────────
    nav_links = "".join(
        f'<a href="#{key.lower()}">{r["titulo"].split("–")[0].strip()}</a> '
        for key, r in audit_results.items()
    )
    nav_html = (
        '<nav class="toc">'
        '<a href="#visao">Visao Geral</a> | '
        '<a href="#resumo">Resumo Regras</a> | '
        '<a href="#detalhes">Detalhamento</a> | '
        '<a href="#complementar">Analises Complementares</a>'
        "</nav>"
    )

    # ── ÂNCORAS por regra ─────────────────────────────────────────────────
    for key in audit_results:
        sections[2] = sections[2].replace(
            f'<div class="regra-block"',
            f'<div id="{key.lower()}" class="regra-block"', 1
        )

    # ── MONTAR HTML FINAL ─────────────────────────────────────────────────
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auditoria Medica – Quimio | EPAGRI</title>
{plotly_cdn}
<style>
  :root {{
    --red: #dc3545; --orange: #fd7e14; --yellow: #ffc107;
    --blue: #0d6efd; --green: #198754; --gray: #6c757d;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Segoe UI", Arial, sans-serif;
    background: #f0f2f5; color: #212529; font-size: 14px;
  }}
  header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
    color: white; padding: 32px 40px 24px; margin-bottom: 28px;
  }}
  header h1 {{ font-size: 1.9rem; font-weight: 700; margin-bottom: 6px; }}
  header p  {{ color: #adb5bd; font-size: 0.95rem; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 0 24px 48px; }}
  .toc {{
    background: white; border-radius: 10px; padding: 14px 20px;
    margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
    font-size: 0.85rem;
  }}
  .toc a {{ color: var(--blue); text-decoration: none; margin-right: 12px; }}
  .toc a:hover {{ text-decoration: underline; }}
  .kpi-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px; margin-bottom: 28px;
  }}
  .kpi-card {{
    background: white; border-radius: 10px; padding: 18px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,.08); border-top: 4px solid var(--blue);
  }}
  .kpi-card.kpi-danger {{ border-top-color: var(--red); }}
  .kpi-val {{ font-size: 1.5rem; font-weight: 700; color: #212529; }}
  .kpi-lbl {{ font-size: 0.8rem; color: var(--gray); margin-top: 4px; }}
  section {{ margin-bottom: 40px; }}
  h2 {{
    font-size: 1.3rem; font-weight: 700; color: #1a1a2e;
    border-bottom: 3px solid var(--blue); padding-bottom: 8px;
    margin-bottom: 20px;
  }}
  h3 {{ font-size: 1.05rem; font-weight: 600; margin: 24px 0 12px; color: #212529; }}
  .chart-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;
  }}
  @media (max-width: 900px) {{ .chart-grid {{ grid-template-columns: 1fr; }} }}
  .chart-cell {{
    background: white; border-radius: 10px; padding: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,.08);
  }}
  .regra-block {{
    background: white; border-radius: 10px; padding: 20px 24px;
    margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
  }}
  .regra-block h3 {{ margin-top: 0; font-size: 1.1rem; color: #1a1a2e; }}
  .regra-block p {{ margin-bottom: 8px; line-height: 1.5; }}
  .audit-table {{
    width: 100%; border-collapse: collapse; font-size: 0.8rem;
  }}
  .audit-table thead tr {{
    background: #1a1a2e; color: white; text-align: left;
  }}
  .audit-table th, .audit-table td {{
    padding: 7px 10px; border: 1px solid #dee2e6;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 320px;
  }}
  .audit-table tbody tr:hover {{ background: rgba(0,0,0,.04) !important; }}
  footer {{
    text-align: center; padding: 24px; color: var(--gray);
    font-size: 0.82rem; border-top: 1px solid #dee2e6; margin-top: 40px;
  }}
  @media print {{
    header {{ background: #1a1a2e !important; -webkit-print-color-adjust: exact; }}
    .toc {{ display: none; }}
    .regra-block {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
<header>
  <h1>Sistema de Auditoria Medica – Quimioterapia & Alto Custo</h1>
  <p>EPAGRI | Gerado em {ts} | Arquivo: quimio_uso_total_01-04-2026.xls</p>
</header>
<div class="container">
  {nav_html}
  {kpi_html}
  {"".join(sections)}
</div>
<footer>
  Sistema de Auditoria Medica v1.0 | Desenvolvido com Python + Streamlit + Plotly | EPAGRI<br>
  Gerado em {ts}
</footer>
</body>
</html>"""

    return html.encode("utf-8")


def export_excel(audit_results: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_rows = []
        for key, r in audit_results.items():
            df_r = r["df"]
            n = len(df_r)
            summary_rows.append({
                "Regra": r["titulo"],
                "Severidade": r["severidade"],
                "Qtd Anomalias": n,
                "Impacto Financeiro (R$)": round(r["impacto"], 2),
            })
            if n > 0:
                cols = [c for c in COLS_DISPLAY if c in df_r.columns]
                df_r[cols].to_excel(writer, sheet_name=key[:31], index=False)
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Resumo", index=False)
    return buf.getvalue()


# ─────────────────────────────────────────────
#  INTERFACE PRINCIPAL
# ─────────────────────────────────────────────
def main():
    st.title("🏥 Sistema de Auditoria Médica")
    st.caption("Quimioterapia & Medicamentos de Alto Custo – Análise de Anomalias com Regras Clínicas")

    # ── SIDEBAR ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configurações")
        uploaded = st.file_uploader(
            "Carregar arquivo XLS/XLSX", type=["xls", "xlsx"]
        )
        use_default = st.checkbox("Usar arquivo padrão (quimio_uso_total_01-04-2026.xls)", value=True)

        st.markdown("---")
        st.subheader("🔎 Filtros Globais")
        sev_filter = st.multiselect(
            "Severidade",
            ["CRITICO", "ALTO", "MEDIO", "BAIXO"],
            default=["CRITICO", "ALTO", "MEDIO", "BAIXO"],
        )

        st.markdown("---")
        st.subheader("📖 Legenda de Severidade")
        for sev, color in SEV_COLOR.items():
            st.markdown(
                f'<span style="background:{color};color:{"white" if sev != "MEDIO" else "#212529"};'
                f'border-radius:4px;padding:2px 8px;font-size:0.8rem;font-weight:700">{sev}</span>',
                unsafe_allow_html=True,
            )

    # ── CARREGAR DADOS ────────────────────────────────────────────────────────
    default_path = None
    if use_default and uploaded is None:
        import os
        default_path = os.path.join(
            os.path.dirname(__file__), "quimio_uso_total_01-04-2026.xls"
        )

    df = load_data(uploaded_file=uploaded, default_path=default_path)

    if df is None:
        st.info("⬆️ Faça upload de um arquivo XLS ou marque a opção de arquivo padrão.")
        return

    # ── MÉTRICAS GERAIS ───────────────────────────────────────────────────────
    st.subheader("📊 Visão Geral do Arquivo")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total de Registros", f"{len(df):,}")
    col2.metric("Beneficiários", f"{df['BENEF'].nunique():,}")
    col3.metric("Valor Total", fmt_currency(df["VALOR"].sum()))
    col4.metric("Valor Pago Total", fmt_currency(df["VALOR_PAGO"].sum()))
    col5.metric("Período", f"{df['REALIZACAO'].min().strftime('%d/%m/%Y')} – {df['REALIZACAO'].max().strftime('%d/%m/%Y')}")

    # Gráficos de visão geral
    col_a, col_b = st.columns(2)
    with col_a:
        fig_grupo = px.pie(
            df.groupby("GRUPO")["VALOR"].sum().reset_index(),
            names="GRUPO", values="VALOR",
            title="Distribuição do Valor por Grupo TISS",
            hole=0.4,
        )
        fig_grupo.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_grupo, use_container_width=True)
    with col_b:
        top10_meds = (
            df[df["VALOR"] > 100]
            .groupby("DESCRICAO")["VALOR"]
            .sum()
            .nlargest(10)
            .reset_index()
        )
        top10_meds["DESCRICAO"] = top10_meds["DESCRICAO"].str[:50] + "..."
        fig_top = px.bar(
            top10_meds, x="VALOR", y="DESCRICAO", orientation="h",
            title="Top 10 Itens por Valor Total",
            color="VALOR", color_continuous_scale="Reds",
        )
        fig_top.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10),
                               yaxis=dict(autorange="reversed"),
                               coloraxis_showscale=False)
        st.plotly_chart(fig_top, use_container_width=True)

    # ── AUDITORIA ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🔍 Auditoria de Anomalias")

    with st.spinner("Executando regras de auditoria médica..."):
        audit_results = run_audit(df)

    # Resumo das regras
    total_anomalias = sum(len(r["df"]) for r in audit_results.values())
    total_impacto = sum(r["impacto"] for r in audit_results.values() if pd.notnull(r["impacto"]))
    regras_criticas = sum(1 for r in audit_results.values() if len(r["df"]) > 0 and r["severidade"] == "CRITICO")

    c1, c2, c3 = st.columns(3)
    c1.metric("🚨 Total de Anomalias", f"{total_anomalias:,}")
    c2.metric("🔴 Regras Críticas com Ocorrências", f"{regras_criticas}")
    c3.metric("💰 Impacto Financeiro Estimado", fmt_currency(total_impacto))

    # Tabela resumo
    summary_data = []
    for key, r in audit_results.items():
        n = len(r["df"])
        if r["severidade"] in sev_filter:
            summary_data.append({
                "Regra": r["titulo"],
                "Severidade": r["severidade"],
                "Ocorrências": n,
                "Impacto (R$)": round(r["impacto"], 2) if pd.notnull(r["impacto"]) else 0,
            })

    df_summary = pd.DataFrame(summary_data)
    df_summary = df_summary.sort_values(
        ["Severidade", "Ocorrências"],
        key=lambda s: s.map(SEV_ORDER) if s.name == "Severidade" else -s,
    )

    st.markdown("#### Resumo das Regras de Auditoria")
    st.dataframe(
        df_summary.style
        .apply(lambda row: [
            f"background-color: {SEV_COLOR.get(row['Severidade'], '#fff')}22"
            for _ in row
        ], axis=1)
        .format({"Impacto (R$)": "R$ {:,.2f}"}),
        use_container_width=True, hide_index=True,
    )

    # Gráfico de anomalias por severidade
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        df_sev = df_summary.groupby("Severidade")["Ocorrências"].sum().reset_index()
        df_sev["Ordem"] = df_sev["Severidade"].map(SEV_ORDER)
        df_sev = df_sev.sort_values("Ordem")
        fig_sev = px.bar(
            df_sev, x="Severidade", y="Ocorrências",
            title="Anomalias por Severidade",
            color="Severidade",
            color_discrete_map={
                "CRITICO": "#dc3545", "ALTO": "#fd7e14",
                "MEDIO": "#ffc107", "BAIXO": "#0d6efd"
            },
        )
        fig_sev.update_layout(height=300, showlegend=False,
                               margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_sev, use_container_width=True)

    with col_g2:
        df_impacto = df_summary[df_summary["Impacto (R$)"] > 0].nlargest(8, "Impacto (R$)")
        df_impacto["Regra_curta"] = df_impacto["Regra"].str[:40] + "..."
        fig_imp = px.bar(
            df_impacto, x="Impacto (R$)", y="Regra_curta", orientation="h",
            title="Top Regras por Impacto Financeiro",
            color="Severidade",
            color_discrete_map={
                "CRITICO": "#dc3545", "ALTO": "#fd7e14",
                "MEDIO": "#ffc107", "BAIXO": "#0d6efd"
            },
        )
        fig_imp.update_layout(height=300, showlegend=False,
                               yaxis=dict(autorange="reversed"),
                               margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_imp, use_container_width=True)

    # ── DETALHE POR REGRA ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 Detalhamento por Regra")

    for key, r in audit_results.items():
        if r["severidade"] not in sev_filter:
            continue
        df_r = r["df"]
        n = len(df_r)

        sev = r["severidade"]
        icon = {"CRITICO": "🔴", "ALTO": "🟠", "MEDIO": "🟡", "BAIXO": "🔵"}.get(sev, "⚪")

        with st.expander(
            f"{icon} {r['titulo']} — {n} ocorrência(s) | Impacto: {fmt_currency(r['impacto'])}",
            expanded=(n > 0 and sev in ["CRITICO", "ALTO"]),
        ):
            st.markdown(
                f"**Descrição:** {r['descricao']}  \n"
                f"**Severidade:** {badge(sev)}",
                unsafe_allow_html=True,
            )

            if n == 0:
                st.success("✅ Nenhuma anomalia detectada para esta regra.")
                continue

            cols_show = [c for c in COLS_DISPLAY if c in df_r.columns]
            df_show = df_r[cols_show].copy()

            # Formatar datas para exibição
            for dc in ["REALIZACAO", "DT_AVISO"]:
                if dc in df_show.columns:
                    df_show[dc] = df_show[dc].apply(
                        lambda x: x.strftime("%d/%m/%Y") if pd.notnull(x) else ""
                    )

            st.dataframe(
                df_show.style.format(
                    {"VALOR": "R$ {:,.2f}", "VALOR_PAGO": "R$ {:,.2f}",
                     "DIFF_VALOR": "R$ {:,.2f}", "PRECO_UNIT": "R$ {:,.4f}"},
                    na_rep="–"
                ),
                use_container_width=True,
                hide_index=True,
                height=min(400, 60 + 35 * n),
            )

            # Mini-análise específica por regra
            if key == "R02" and not df_r.empty:
                st.markdown("**Casos críticos – divergência de valor:**")
                casos = df_r.groupby(["BENEF", "SERVICO", "REALIZACAO"])["VALOR"].apply(list).reset_index()
                st.dataframe(casos, use_container_width=True, hide_index=True)

            if key == "R14" and not df_r.empty:
                top_benef = df_r.groupby("BENEF")["TOTAL_BENEF"].first().sort_values(ascending=False).head(10)
                fig_benef = px.bar(
                    top_benef.reset_index(),
                    x="BENEF", y="TOTAL_BENEF",
                    title="Top Beneficiários por Custo Total",
                    labels={"TOTAL_BENEF": "Valor Total (R$)", "BENEF": "Beneficiário"},
                )
                fig_benef.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_benef, use_container_width=True)

    # ── ANÁLISES COMPLEMENTARES ───────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📈 Análises Complementares")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Dispersão de Preço Unitário",
        "Evolução Temporal",
        "Análise por Prestador",
        "Distribuição por Beneficiário",
    ])

    with tab1:
        meds_multi = (
            df[df["PRECO_UNIT"].notnull() & (df["VALOR"] > 500)]
            .groupby("DESCRICAO")
            .filter(lambda x: len(x) >= 2)
        )
        if not meds_multi.empty:
            top_meds = meds_multi.groupby("DESCRICAO")["VALOR"].sum().nlargest(15).index
            df_plot = meds_multi[meds_multi["DESCRICAO"].isin(top_meds)].copy()
            df_plot["DESC_CURTA"] = df_plot["DESCRICAO"].str[:45] + "..."
            fig_box = px.box(
                df_plot, x="DESC_CURTA", y="PRECO_UNIT",
                title="Dispersão de Preço Unitário – Top 15 Itens de Alto Custo",
                points="all", color="DESC_CURTA",
                labels={"PRECO_UNIT": "Preço Unitário (R$)", "DESC_CURTA": "Medicamento"},
            )
            fig_box.update_layout(
                height=480, showlegend=False,
                xaxis_tickangle=-45,
                margin=dict(l=10, r=10, t=50, b=150),
            )
            st.plotly_chart(fig_box, use_container_width=True)

    with tab2:
        df_time = df.copy()
        df_time["MES"] = df_time["REALIZACAO"].dt.to_period("M").astype(str)
        df_time_grp = df_time.groupby(["MES", "GRUPO"])["VALOR"].sum().reset_index()
        fig_time = px.bar(
            df_time_grp, x="MES", y="VALOR", color="GRUPO",
            title="Valor Total por Mês e Grupo TISS",
            labels={"VALOR": "Valor (R$)", "MES": "Mês"},
        )
        fig_time.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_time, use_container_width=True)

    with tab3:
        df_prest = (
            df.groupby("CREDENCIADO_LOCAL_EXECUTOR")
            .agg(Total=("VALOR", "sum"), Registros=("VALOR", "count"), Benefs=("BENEF", "nunique"))
            .sort_values("Total", ascending=False)
            .head(20)
            .reset_index()
        )
        df_prest["PREST_CURTO"] = df_prest["CREDENCIADO_LOCAL_EXECUTOR"].str[:40]
        fig_prest = px.bar(
            df_prest, x="Total", y="PREST_CURTO", orientation="h",
            title="Top 20 Prestadores por Valor Total",
            color="Total", color_continuous_scale="Oranges",
            labels={"Total": "Valor Total (R$)", "PREST_CURTO": "Prestador"},
        )
        fig_prest.update_layout(
            height=520, showlegend=False,
            yaxis=dict(autorange="reversed"),
            coloraxis_showscale=False,
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig_prest, use_container_width=True)

    with tab4:
        valor_benef = df.groupby("BENEF")["VALOR"].sum().reset_index()
        fig_hist = px.histogram(
            valor_benef, x="VALOR", nbins=50,
            title="Distribuição de Custo Total por Beneficiário",
            labels={"VALOR": "Custo Total (R$)", "count": "Qtd Beneficiários"},
            color_discrete_sequence=["#0d6efd"],
        )
        fig_hist.update_layout(height=340, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_hist, use_container_width=True)

        p95 = valor_benef["VALOR"].quantile(0.95)
        st.dataframe(
            valor_benef[valor_benef["VALOR"] >= p95]
            .sort_values("VALOR", ascending=False)
            .assign(VALOR=lambda d: d["VALOR"].map(lambda v: f"R$ {v:,.2f}"))
            .rename(columns={"BENEF": "Beneficiário", "VALOR": "Custo Total"}),
            use_container_width=True, hide_index=True,
        )

    # ── EXPORTAR ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📤 Exportar Relatório")

    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        if st.button("📊 Gerar Relatório Excel", type="primary", use_container_width=True):
            with st.spinner("Gerando Excel..."):
                excel_bytes = export_excel(audit_results)
            st.download_button(
                label="⬇️ Baixar Relatório Excel",
                data=excel_bytes,
                file_name=f"auditoria_medica_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with col_exp2:
        if st.button("🌐 Gerar Relatório HTML", type="secondary", use_container_width=True):
            with st.spinner("Gerando HTML com todos os gráficos e tabelas..."):
                html_bytes = export_html(df, audit_results)
            st.download_button(
                label="⬇️ Baixar Relatório HTML",
                data=html_bytes,
                file_name=f"auditoria_medica_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                mime="text/html",
                use_container_width=True,
            )
            st.info(
                "O arquivo HTML é autocontido — basta abrir no navegador. "
                "Todos os gráficos são interativos (zoom, hover, download PNG). "
                "Compatível com impressão/PDF via Ctrl+P."
            )

    st.markdown(
        "<br><small style='color:#6c757d'>Sistema de Auditoria Médica v1.0 | "
        "Desenvolvido com Python + Streamlit | EPAGRI</small>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
