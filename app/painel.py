"""
Interface do Copiloto Regulatorio Inteligente: um painel com as
publicacoes mais recentes (ONS, ANEEL, DOU) e um chat que responde
perguntas com base nesses documentos, citando a fonte.

Rodar (a partir da raiz do repositorio) com:
    streamlit run app/painel.py
"""

import os
import re
import sys

import altair as alt
import pandas as pd
import streamlit as st

# Permite importar os modulos de src/ (utils_busca.py, gerar_resposta.py)
# sem transformar o projeto em um pacote Python formal, seguindo o
# mesmo padrao de import ja usado entre os scripts de src/.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from utils_busca import carregar_indice  # noqa: E402
from gerar_resposta import gerar_resposta  # noqa: E402
from google import genai  # noqa: E402

CAMINHO_METADADOS = os.path.join("data", "processed", "metadados_documentos.csv")

# Muitos titulos de submodulos do ONS trazem a data de revisao no proprio
# nome, no formato "AAAA.MM" (ex.: "Submodulo 2.4-OP_2024.10" -> outubro
# de 2024). Esse padrao captura ano e mes desses casos.
PADRAO_ANO_MES_TITULO = re.compile(r"(20\d{2})\.(0[1-9]|1[0-2])\b")

st.set_page_config(page_title="Copiloto Regulatorio Inteligente", layout="wide")


def extrair_ano_mes_do_titulo(titulo):
    """Extrai ano e mes de titulos no padrao usado pelo ONS (ex.:
    'Submodulo 2.4-OP_2024.10' -> ano=2024, mes=10). Devolve (None, None)
    se o padrao nao for encontrado."""
    if not titulo:
        return None, None
    encontrado = PADRAO_ANO_MES_TITULO.search(titulo)
    if not encontrado:
        return None, None
    return int(encontrado.group(1)), int(encontrado.group(2))


def montar_ano_mes_dia(linha):
    """Decide a data efetiva de um documento: usa a data de publicacao
    quando disponivel (ex.: DOU, que tem data completa); senao, tenta
    extrair ano/mes do titulo (ex.: submodulos do ONS), deixando o dia
    como desconhecido nesse segundo caso."""
    if pd.notna(linha["DATA_PUBLICACAO_DT"]):
        data = linha["DATA_PUBLICACAO_DT"]
        return pd.Series({"ANO": data.year, "MES": data.month, "DIA": data.day})

    ano, mes = extrair_ano_mes_do_titulo(linha["TITULO"])
    return pd.Series({"ANO": ano, "MES": mes, "DIA": None})


@st.cache_data
def carregar_metadados():
    df = pd.read_csv(CAMINHO_METADADOS, keep_default_na=False)
    df["DATA_PUBLICACAO_DT"] = pd.to_datetime(df["DATA_PUBLICACAO"], errors="coerce", dayfirst=True)

    df[["ANO", "MES", "DIA"]] = df.apply(montar_ano_mes_dia, axis=1)
    df["ANO"] = df["ANO"].astype("Int64")
    df["MES"] = df["MES"].astype("Int64")
    df["DIA"] = df["DIA"].astype("Int64")

    # Rotulo "AAAA-MM" usado para agrupar e exibir o grafico por mes.
    # Fica vazio (None) quando nem a data de publicacao nem o titulo
    # trazem uma data identificavel.
    df["PERIODO"] = df.apply(
        lambda linha: f"{int(linha['ANO']):04d}-{int(linha['MES']):02d}"
        if pd.notna(linha["ANO"]) and pd.notna(linha["MES"])
        else None,
        axis=1,
    )

    return df


@st.cache_resource
def carregar_indice_busca():
    return carregar_indice()


@st.cache_resource
def carregar_cliente_gemini():
    return genai.Client()


st.title("⚡ Copiloto Regulatorio Inteligente")
st.caption("Transicao energetica no setor eletrico brasileiro — ONS, ANEEL e DOU")

aba_painel, aba_chat = st.tabs(["📊 Painel de Normas", "💬 Chat"])

# ----------------------------------------------------------------------
# Aba 1: painel com as publicacoes mais recentes, filtravel por fonte
# ----------------------------------------------------------------------
with aba_painel:
    df_metadados = carregar_metadados()

    fontes_disponiveis = sorted(df_metadados["FONTE"].unique())
    colunas_metricas = st.columns(len(fontes_disponiveis) + 1)
    colunas_metricas[0].metric("Total de documentos", len(df_metadados))
    for coluna, fonte in zip(colunas_metricas[1:], fontes_disponiveis):
        coluna.metric(fonte, (df_metadados["FONTE"] == fonte).sum())

    st.divider()
    st.subheader("📈 Publicações por mês")

    df_com_periodo = df_metadados.dropna(subset=["PERIODO"])
    quantidade_sem_data = len(df_metadados) - len(df_com_periodo)

    contagem_por_mes = (
        df_com_periodo.groupby("PERIODO").size().reset_index(name="quantidade").sort_values("PERIODO")
    )

    selecao_mes = alt.selection_point(fields=["PERIODO"], name="selecao_mes")
    grafico_mensal = (
        alt.Chart(contagem_por_mes)
        .mark_bar()
        .encode(
            x=alt.X("PERIODO:N", sort=None, title="Mês"),
            y=alt.Y("quantidade:Q", title="Quantidade de documentos"),
            color=alt.condition(selecao_mes, alt.value("#1f77b4"), alt.value("#c6dbef")),
            tooltip=[alt.Tooltip("PERIODO:N", title="Mês"), alt.Tooltip("quantidade:Q", title="Documentos")],
        )
        .add_params(selecao_mes)
    )

    evento_grafico = st.altair_chart(grafico_mensal, on_select="rerun", use_container_width=True)

    mes_selecionado = None
    if evento_grafico and evento_grafico.selection and evento_grafico.selection.get("selecao_mes"):
        pontos_selecionados = evento_grafico.selection["selecao_mes"]
        if pontos_selecionados:
            mes_selecionado = pontos_selecionados[0]["PERIODO"]

    if mes_selecionado:
        df_do_mes = df_com_periodo[df_com_periodo["PERIODO"] == mes_selecionado]
        st.markdown(f"**{len(df_do_mes)} documento(s) de {mes_selecionado}:**")
        st.dataframe(
            df_do_mes[["FONTE", "TITULO", "DATA_PUBLICACAO", "TEMA", "URL_ORIGINAL"]],
            use_container_width=True,
            hide_index=True,
            column_config={"URL_ORIGINAL": st.column_config.LinkColumn("Link")},
        )
    else:
        st.caption("Clique em uma barra do gráfico para ver os documentos daquele mês.")

    if quantidade_sem_data:
        st.caption(
            f"{quantidade_sem_data} documento(s) sem data identificável "
            "(nem na publicação, nem no título) não aparecem neste gráfico."
        )

    st.divider()

    fontes_selecionadas = st.multiselect("Filtrar por fonte", fontes_disponiveis, default=fontes_disponiveis)

    df_filtrado = df_metadados[df_metadados["FONTE"].isin(fontes_selecionadas)]
    df_filtrado = df_filtrado.sort_values("DATA_PUBLICACAO_DT", ascending=False, na_position="last")

    st.caption(
        "Ordenado por data de publicacao (documentos sem data conhecida, "
        "como alguns submodulos do ONS, aparecem no final)."
    )

    st.dataframe(
        df_filtrado[["FONTE", "TITULO", "DATA_PUBLICACAO", "TEMA", "URL_ORIGINAL"]],
        use_container_width=True,
        hide_index=True,
        column_config={"URL_ORIGINAL": st.column_config.LinkColumn("Link")},
    )

# ----------------------------------------------------------------------
# Aba 2: chat com resposta gerada a partir dos documentos, com citacao
# ----------------------------------------------------------------------
with aba_chat:
    try:
        cliente = carregar_cliente_gemini()
    except Exception as erro:
        st.error(
            "Nao foi possivel conectar com a API do Gemini. Confira se a "
            "variavel de ambiente GEMINI_API_KEY esta configurada no "
            f"terminal onde voce rodou o Streamlit.\n\nDetalhe: {erro}"
        )
        st.stop()

    indice = carregar_indice_busca()

    if "historico_chat" not in st.session_state:
        st.session_state.historico_chat = []

    for pergunta_anterior, resposta_anterior in st.session_state.historico_chat:
        with st.chat_message("user"):
            st.write(pergunta_anterior)
        with st.chat_message("assistant"):
            st.write(resposta_anterior)

    pergunta = st.chat_input("Pergunte sobre regulacao do setor eletrico...")

    if pergunta:
        with st.chat_message("user"):
            st.write(pergunta)

        with st.chat_message("assistant"):
            with st.spinner("Buscando nos documentos e gerando resposta..."):
                resposta, chunks_relevantes, consultas_expandidas = gerar_resposta(pergunta, indice, cliente)
            st.write(resposta)
            with st.expander("Ver como a resposta foi gerada"):
                if consultas_expandidas:
                    st.markdown("**Buscas alternativas usadas:** " + ", ".join(consultas_expandidas))
                for i, chunk in enumerate(chunks_relevantes, start=1):
                    st.markdown(f"**[Trecho {i}]** {chunk['fonte']} — {chunk['titulo']}")
                    if chunk["url_original"]:
                        st.markdown(f"[Abrir documento original]({chunk['url_original']})")
                    st.text(chunk["texto_chunk"][:500] + "...")

        st.session_state.historico_chat.append((pergunta, resposta))
