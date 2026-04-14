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


def obter_nome_coluna_id(df):
    possibilidades = [
        "ID do cliente",
        "Id do cliente",
        "ID Cliente",
        "Id Cliente",
        "id_cliente",
        "cliente_id",
        "ID",
        "Id",
        "id"
    ]

    for coluna in possibilidades:
        if coluna in df.columns:
            return coluna

    return None


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

    # Detecta coluna de ID
    coluna_id = obter_nome_coluna_id(df)
    if coluna_id and coluna_id != "ID do cliente":
        df = df.rename(columns={coluna_id: "ID do cliente"})

    # Garante colunas esperadas
    colunas_esperadas = [
        "ID do cliente",
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

    # Padroniza ID
    df["ID do cliente"] = df["ID do cliente"].astype(str).str.strip()

    # Calcula health score
    df["Health Score"] = df.apply(calcular_health_score, axis=1)
    df["Status Health"] = df["Health Score"].apply(classificar_health_score)

    return df


df = carregar_dados()

# =========================
# TÍTULO
# =========================
st.title("Dashboard de Health Score dos Clientes")
st.caption("Visão analítica da carteira e análise individual de clientes com base no health score")

# =========================
# SELETOR DE VISÃO
# =========================
modo_visao = st.radio(
    "Selecione a visão",
    ["Visão da carteira", "Visão do cliente"],
    horizontal=True
)

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Filtros")

segmentos = sorted([x for x in df["Segmento"].dropna().unique()])
etapas = sorted([x for x in df["Etapa"].dropna().unique()])
tipos_cliente = sorted([x for x in df["Tipo de cliente"].dropna().unique()])
lista_ids = sorted([x for x in df["ID do cliente"].dropna().unique() if str(x).strip() not in ["", "nan", "None"]])

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

filtro_id = st.sidebar.selectbox(
    "Buscar cliente por ID",
    options=["Todos"] + lista_ids
)

df_filtrado = df.copy()

if filtro_segmento:
    df_filtrado = df_filtrado[df_filtrado["Segmento"].isin(filtro_segmento)]

if filtro_etapa:
    df_filtrado = df_filtrado[df_filtrado["Etapa"].isin(filtro_etapa)]

if filtro_tipo:
    df_filtrado = df_filtrado[df_filtrado["Tipo de cliente"].isin(filtro_tipo)]

df_cliente = df_filtrado.copy()
if filtro_id != "Todos":
    df_cliente = df_cliente[df_cliente["ID do cliente"] == filtro_id]

# =========================
# VISÃO DA CARTEIRA
# =========================
if modo_visao == "Visão da carteira":
    st.markdown("## Visão da carteira")

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

    st.markdown("## Análises gerais")

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
    color_discrete_map={
        "Saudável": "#2ecc71",
        "Em atenção": "#f39c12",
        "Em risco": "#e74c3c"
    },
    hover_data=["ID do cliente", "Nome", "Empresa", "Segmento", "Etapa"],
    title="Minutos de uso x Health Score"
)
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("## Clientes em risco")

    clientes_risco = df_filtrado[df_filtrado["Status Health"] == "Em risco"].copy()
    clientes_risco = clientes_risco.sort_values("Health Score", ascending=True)

    colunas_risco = [
        "ID do cliente",
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

    st.markdown("## Base detalhada da carteira")

    colunas_exibir = [
        "ID do cliente",
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

    st.markdown("## Exportação")

    csv = df_filtrado.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Baixar base da carteira em CSV",
        data=csv,
        file_name="base_health_score_wedy_carteira.csv",
        mime="text/csv"
    )

# =========================
# VISÃO DO CLIENTE
# =========================
if modo_visao == "Visão do cliente":
    st.markdown("## Visão do cliente")

    if filtro_id == "Todos":
        st.info("Selecione um ID do cliente no filtro lateral para visualizar a análise individual.")
    elif df_cliente.empty:
        st.warning("Nenhum cliente encontrado para esse ID dentro dos filtros aplicados.")
    else:
        cliente = df_cliente.iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ID do Cliente", cliente.get("ID do cliente", ""))
        c2.metric("Cliente", cliente.get("Nome", ""))
        c3.metric("Empresa", cliente.get("Empresa", ""))
        c4.metric("Health Score", f"{cliente.get('Health Score', 0):.2f}")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Status", cliente.get("Status Health", ""))
        c6.metric("Etapa", cliente.get("Etapa", ""))
        c7.metric(
            "Minutos de uso",
            f"{0 if pd.isna(cliente.get('Minutos de uso')) else cliente.get('Minutos de uso'):.2f}"
        )
        c8.metric("MRR", formatar_moeda(cliente.get("MRR", 0)))

        st.markdown("## Indicadores do cliente")

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Playlist aprovada", cliente.get("Playlist aprovada", ""))
        d2.metric(
            "Quantidade de ajustes",
            f"{0 if pd.isna(cliente.get('Quantidade de ajustes')) else int(cliente.get('Quantidade de ajustes'))}"
        )
        d3.metric(
            "Quantidade de tickets",
            f"{0 if pd.isna(cliente.get('Quantidade de tickets')) else int(cliente.get('Quantidade de tickets'))}"
        )
        d4.metric("Cliente Ativo?", cliente.get("Cliente Ativo?", ""))

        st.markdown("## Detalhamento do cliente")

        detalhe_cliente = pd.DataFrame([{
            "ID do cliente": cliente.get("ID do cliente", ""),
            "Nome": cliente.get("Nome", ""),
            "Empresa": cliente.get("Empresa", ""),
            "Segmento": cliente.get("Segmento", ""),
            "Tipo de cliente": cliente.get("Tipo de cliente", ""),
            "Etapa": cliente.get("Etapa", ""),
            "Cliente Ativo?": cliente.get("Cliente Ativo?", ""),
            "Churn?": cliente.get("Churn?", ""),
            "Playlist aprovada": cliente.get("Playlist aprovada", ""),
            "Minutos de uso": cliente.get("Minutos de uso", np.nan),
            "Quantidade de ajustes": cliente.get("Quantidade de ajustes", np.nan),
            "Quantidade de tickets": cliente.get("Quantidade de tickets", np.nan),
            "Último contato": cliente.get("Último contato", ""),
            "MRR": cliente.get("MRR", np.nan),
            "Health Score": cliente.get("Health Score", np.nan),
            "Status Health": cliente.get("Status Health", "")
        }])

        st.dataframe(
            detalhe_cliente,
            use_container_width=True,
            height=150
        )

        st.markdown("## Comparativo do cliente com a carteira")

        media_health_carteira = df_filtrado["Health Score"].mean()
        media_uso_carteira = df_filtrado["Minutos de uso"].mean()
        media_mrr_carteira = df_filtrado["MRR"].mean()

        comp1, comp2, comp3 = st.columns(3)
        comp1.metric(
            "Health Score do cliente vs média da carteira",
            f"{cliente.get('Health Score', 0):.2f}",
            delta=f"{cliente.get('Health Score', 0) - (0 if pd.isna(media_health_carteira) else media_health_carteira):.2f}"
        )
        comp2.metric(
            "Uso do cliente vs média da carteira",
            f"{0 if pd.isna(cliente.get('Minutos de uso')) else cliente.get('Minutos de uso'):.2f} min",
            delta=f"{(0 if pd.isna(cliente.get('Minutos de uso')) else cliente.get('Minutos de uso')) - (0 if pd.isna(media_uso_carteira) else media_uso_carteira):.2f}"
        )
        comp3.metric(
            "MRR do cliente vs média da carteira",
            formatar_moeda(cliente.get("MRR", 0)),
            delta=f"{(0 if pd.isna(cliente.get('MRR')) else cliente.get('MRR')) - (0 if pd.isna(media_mrr_carteira) else media_mrr_carteira):.2f}"
        )

        st.markdown("## Posição do cliente no scatter da carteira")

        fig_scatter_cliente = px.scatter(
            df_filtrado,
            x="Minutos de uso",
            y="Health Score",
            color="Status Health",
            hover_data=["ID do cliente", "Nome", "Empresa", "Segmento", "Etapa"],
            title="Posicionamento do cliente na carteira"
        )

        fig_scatter_cliente.add_scatter(
            x=[cliente.get("Minutos de uso", 0)],
            y=[cliente.get("Health Score", 0)],
            mode="markers+text",
            text=[str(cliente.get("Nome", "Cliente selecionado"))],
            textposition="top center",
            marker=dict(size=16, symbol="diamond"),
            name="Cliente selecionado"
        )

        st.plotly_chart(fig_scatter_cliente, use_container_width=True)
