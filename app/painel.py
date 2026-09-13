"""
Interface do Copiloto Regulatorio Inteligente: um painel com as
publicacoes mais recentes (ONS, ANEEL, DOU) e um chat que responde
perguntas com base nesses documentos, citando a fonte.

Rodar (a partir da raiz do repositorio) com:
    streamlit run app/painel.py
"""

import os
import sys

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

st.set_page_config(page_title="Copiloto Regulatorio Inteligente", layout="wide")


@st.cache_data
def carregar_metadados():
    df = pd.read_csv(CAMINHO_METADADOS, keep_default_na=False)
    df["DATA_PUBLICACAO_DT"] = pd.to_datetime(df["DATA_PUBLICACAO"], errors="coerce")
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
