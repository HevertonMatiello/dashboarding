import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="Dashboard Wedy",
    layout="wide"
)

# =========================
# CAMINHO DO ARQUIVO
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
ARQUIVO_DADOS = BASE_DIR / "base_clientes_wedy.xlsx"


# =========================
# FUNÇÕES AUXILIARES
# =========================
def formatar_moeda(valor):
    if pd.isna(valor):
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def classificar_health_score(score):
    if score >= 80:
        return "Saudável"
    if score >= 50:
        return "Em atenção"
    return "Em risco"


def score_uso(minutos):
    if pd.isna(minutos):
        return 0
    return min((float(minutos) / 15) * 35, 35)


def score_ativacao(playlist_aprovada):
    if str(playlist_aprovada).strip().lower() == "sim":
        return 20
    return 0


def score_etapa(etapa):
    etapa = str(etapa).strip().lower()

    mapa = {
        "onboarding": 5,
        "ativação": 10,
        "ativacao": 10,
        "ativo": 15,
        "churn": 0
    }

    return mapa.get(etapa, 0)


def score_ajustes(qtd_ajustes):
    if pd.isna(qtd_ajustes):
        return 0
    return max(10 - (float(qtd_ajustes) * 3), 0)


def score_tickets(qtd_tickets):
    if pd.isna(qtd_tickets):
        return 0
    return max(10 - (float(qtd_tickets) * 3), 0)


def score_relacionamento(ultimo_contato):
    if pd.isna(ultimo_contato):
        return 0

    hoje = pd.Timestamp.today().normalize()
    dias_sem_contato = (hoje - pd.to_datetime(ultimo_contato).normalize()).days

    if dias_sem_contato <= 7:
        return 10
    if dias_sem_contato <= 30:
        return 7
    if dias_sem_contato <= 60:
        return 4
    return 0


def calcular_health_score(row):
    churn = str(row.get("Churn?", "")).strip().lower()

    if churn == "sim":
        return 0.0

    total = (
        score_uso(row.get("Minutos de uso")) +
        score_ativacao(row.get("Playlist aprovada")) +
        score_etapa(row.get("Etapa")) +
        score_ajustes(row.get("Quantidade de ajustes")) +
        score_tickets(row.get("Quantidade de tickets")) +
        score_relacionamento(row.get("Último contato"))
    )

    return round(min(total, 100), 2)


# =========================
# LEITURA DA BASE
# =========================
@st.cache_data
def carregar_dados():
    if not ARQUIVO_DADOS.exists():
        st.error(f"Arquivo não encontrado: {ARQUIVO_DADOS}")
        st.stop()

    df = pd.read_excel(ARQUIVO_DADOS)

    # Ajuste para colunas que possam vir com nome numérico
    colunas_renomeadas = {}
    for col in df.columns:
        if str(col).strip() == "1000":
            colunas_renomeadas[col] = "MRR"

    if colunas_renomeadas:
        df = df.rename(columns=colunas_renomeadas)

    # Caso a coluna MRR ainda não exista, tenta localizar
    if "MRR" not in df.columns:
        for col in df.columns:
            if str(col).strip().lower() in ["mrr", "receita mensal", "valor mensal"]:
                df = df.rename(columns={col: "MRR"})
                break

    # Garante colunas esperadas
    colunas_esperadas = [
        "Nome",
        "Empresa",
        "Segmento",
        "Etapa",
        "Minutos de uso",
        "Playlist aprovada",
        "Quantidade de ajustes",
        "Quantidade de tickets",
        "Cliente Ativo?",
        "Churn?",
        "Último contato",
        "Tipo de cliente",
        "MRR"
    ]

    for coluna in colunas_esperadas:
        if coluna not in df.columns:
            df[coluna] = np.nan

    # Conversões
    for col in ["Último contato", "Data de criação", "Atualizado em"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    colunas_numericas = [
        "Minutos de uso",
        "Quantidade de ajustes",
        "Quantidade de tickets",
        "MRR"
    ]

    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calcula health score
    df["Health Score"] = df.apply(calcular_health_score, axis=1)
    df["Status Health"] = df["Health Score"].apply(classificar_health_score)

    return df


df = carregar_dados()

# =========================
# TÍTULO
# =========================
st.title("Dashboard de Health Score dos Clientes")
st.caption("Visão analítica da base fake com cálculo de health score e indicadores de risco")

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Filtros")

segmentos = sorted([x for x in df["Segmento"].dropna().unique()])
etapas = sorted([x for x in df["Etapa"].dropna().unique()])
tipos_cliente = sorted([x for x in df["Tipo de cliente"].dropna().unique()])

filtro_segmento = st.sidebar.multiselect(
    "Segmento",
    options=segmentos,
    default=segmentos
)

filtro_etapa = st.sidebar.multiselect(
    "Etapa",
    options=etapas,
    default=etapas
)

filtro_tipo = st.sidebar.multiselect(
    "Tipo de cliente",
    options=tipos_cliente,
    default=tipos_cliente
)

df_filtrado = df.copy()

if filtro_segmento:
    df_filtrado = df_filtrado[df_filtrado["Segmento"].isin(filtro_segmento)]

if filtro_etapa:
    df_filtrado = df_filtrado[df_filtrado["Etapa"].isin(filtro_etapa)]

if filtro_tipo:
    df_filtrado = df_filtrado[df_filtrado["Tipo de cliente"].isin(filtro_tipo)]

# =========================
# KPIS
# =========================
total_clientes = len(df_filtrado)
clientes_ativos = (
    df_filtrado["Cliente Ativo?"].astype(str).str.strip().str.lower() == "sim"
).sum()

clientes_churn = (
    df_filtrado["Churn?"].astype(str).str.strip().str.lower() == "sim"
).sum()

mrr_total = df_filtrado["MRR"].sum(skipna=True)
uso_medio = df_filtrado["Minutos de uso"].mean()
health_medio = df_filtrado["Health Score"].mean()

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("Clientes", total_clientes)
c2.metric("Ativos", int(clientes_ativos))
c3.metric("Churn", int(clientes_churn))
c4.metric("MRR Total", formatar_moeda(mrr_total))
c5.metric("Uso Médio", f"{0 if pd.isna(uso_medio) else uso_medio:.2f} min")
c6.metric("Health Médio", f"{0 if pd.isna(health_medio) else health_medio:.2f}")

# =========================
# EXPLICAÇÃO DO SCORE
# =========================
st.markdown("## Metodologia do Health Score")

with st.expander("Ver cálculo do health score"):
    st.markdown(
        """
        **Composição do score**

        Uso do produto  
        até 35 pontos com base em minutos de uso

        Ativação  
        20 pontos se a playlist foi aprovada

        Etapa da jornada  
        até 15 pontos conforme a fase do cliente

        Ajustes  
        até 10 pontos, sendo que menos ajustes gera score maior

        Tickets  
        até 10 pontos, sendo que menos tickets gera score maior

        Relacionamento  
        até 10 pontos com base na recência do último contato

        **Regra especial**

        Se o cliente estiver em churn, o health score é zerado.
        """
    )

# =========================
# GRÁFICOS
# =========================
st.markdown("## Análises")

col1, col2 = st.columns(2)

with col1:
    media_por_etapa = (
        df_filtrado.groupby("Etapa", as_index=False)["Health Score"]
        .mean()
        .sort_values("Health Score", ascending=False)
    )

    fig_etapa = px.bar(
        media_por_etapa,
        x="Etapa",
        y="Health Score",
        text_auto=".2f",
        title="Health Score médio por etapa"
    )
    st.plotly_chart(fig_etapa, use_container_width=True)

with col2:
    media_por_segmento = (
        df_filtrado.groupby("Segmento", as_index=False)["Health Score"]
        .mean()
        .sort_values("Health Score", ascending=False)
    )

    fig_segmento = px.bar(
        media_por_segmento,
        x="Segmento",
        y="Health Score",
        text_auto=".2f",
        title="Health Score médio por segmento"
    )
    st.plotly_chart(fig_segmento, use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    churn_segmento = df_filtrado.copy()
    churn_segmento["Churn Num"] = np.where(
        churn_segmento["Churn?"].astype(str).str.strip().str.lower() == "sim",
        1,
        0
    )

    churn_agrupado = (
        churn_segmento.groupby("Segmento", as_index=False)["Churn Num"]
        .mean()
    )
    churn_agrupado["Taxa de Churn"] = churn_agrupado["Churn Num"] * 100

    fig_churn = px.bar(
        churn_agrupado,
        x="Segmento",
        y="Taxa de Churn",
        text_auto=".2f",
        title="Taxa de churn por segmento"
    )
    st.plotly_chart(fig_churn, use_container_width=True)

with col4:
    fig_hist = px.histogram(
        df_filtrado,
        x="Health Score",
        nbins=20,
        title="Distribuição do Health Score"
    )
    st.plotly_chart(fig_hist, use_container_width=True)

st.markdown("## Relação entre uso e health score")

fig_scatter = px.scatter(
    df_filtrado,
    x="Minutos de uso",
    y="Health Score",
    color="Status Health",
    hover_data=["Nome", "Empresa", "Segmento", "Etapa"],
    title="Minutos de uso x Health Score"
)
st.plotly_chart(fig_scatter, use_container_width=True)

# =========================
# CLIENTES EM RISCO
# =========================
st.markdown("## Clientes em risco")

clientes_risco = df_filtrado[df_filtrado["Status Health"] == "Em risco"].copy()
clientes_risco = clientes_risco.sort_values("Health Score", ascending=True)

colunas_risco = [
    "Nome",
    "Empresa",
    "Segmento",
    "Etapa",
    "Minutos de uso",
    "Quantidade de ajustes",
    "Quantidade de tickets",
    "MRR",
    "Health Score",
    "Status Health"
]

st.dataframe(
    clientes_risco[colunas_risco],
    use_container_width=True,
    height=300
)

# =========================
# BASE COMPLETA
# =========================
st.markdown("## Base detalhada")

colunas_exibir = [
    "Nome",
    "Empresa",
    "Segmento",
    "Tipo de cliente",
    "Etapa",
    "Minutos de uso",
    "Playlist aprovada",
    "Quantidade de ajustes",
    "Quantidade de tickets",
    "Cliente Ativo?",
    "Churn?",
    "Último contato",
    "MRR",
    "Health Score",
    "Status Health"
]

st.dataframe(
    df_filtrado[colunas_exibir].sort_values("Health Score", ascending=False),
    use_container_width=True,
    height=500
)

# =========================
# DOWNLOAD CSV
# =========================
st.markdown("## Exportação")

csv = df_filtrado.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Baixar base tratada em CSV",
    data=csv,
    file_name="base_health_score_wedy.csv",
    mime="text/csv"
)
