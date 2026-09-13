"""
Constroi uma "wiki" de normas do ONS: agrupa todas as revisoes do MESMO
submodulo (numero + sigla, ex.: "2.10-RQ", extraido do titulo) e usa o
Gemini para gerar, a partir da versao mais recente, uma pagina com o
conteudo vigente resumido + historico de revisoes anteriores.

Isso ataca o problema de sobreposicao/revisao de normas: em vez do chat
receber trechos soltos de varias versoes concorrentes do mesmo
submodulo (e ter que adivinhar qual e a vigente), ele passa a receber
uma pagina ja consolidada, deixando claro qual e a versao atual.

Documentos cujo titulo NAO segue o padrao "numero-SIGLA" (ex.: titulos
descritivos, sem numeracao de submodulo) viram uma pagina propria, sem
historico -- assim nenhum documento fica de fora da wiki.

NOTA: inicialmente esta etapa foi pensada para rodar com um LLM local
(Ollama), evitando gastar chamadas da API gratuita do Gemini. Na
pratica, um modelo de 8B rodando so na CPU (sem GPU dedicada boa) se
mostrou tempo demais (~10 min por pagina) para o volume de documentos
do ONS -- entao voltamos a usar o Gemini aqui tambem, com uma pequena
pausa entre chamadas para respeitar o limite de taxa gratuito.

Uso:
    python src/construir_wiki_ons.py
"""

import os
import re
import time

from google import genai
from google.genai import types
import pandas as pd

from utils_normas_ons import extrair_ano_mes_do_titulo, extrair_modulo_sufixo_do_titulo

CAMINHO_METADADOS = os.path.join("data", "processed", "metadados_documentos.csv")
PASTA_SAIDA = os.path.join("data", "wiki", "ons")

MODELO = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
# Pausa entre chamadas, para respeitar o limite de requisicoes por
# minuto da camada gratuita do Google AI Studio.
PAUSA_ENTRE_CHAMADAS_SEGUNDOS = 4

# Limite de caracteres do texto enviado ao modelo: documentos muito
# longos podem perder detalhes de paginas finais no resumo, mas isso
# e aceitavel para o MVP.
LIMITE_CARACTERES_TEXTO = 12000

PROMPT_SISTEMA_WIKI = """Voce organiza documentos tecnicos do setor eletrico \
brasileiro (ONS) em paginas de referencia curtas e claras, em portugues.

Dado o texto de um documento (a versao MAIS RECENTE de um submodulo do ONS) \
e uma lista de versoes anteriores conhecidas (so as datas, sem o texto \
delas), escreva uma pagina com EXATAMENTE este formato:

## Resumo
(3 a 6 frases resumindo, em linguagem clara, as regras vigentes descritas \
no texto fornecido)

## Historico de revisoes
(uma linha por versao anterior conhecida, no formato "- <data>: versao \
anterior deste submodulo"; se nao houver nenhuma, escreva "Nenhuma versao \
anterior conhecida.")

Baseie-se SOMENTE no texto fornecido. Nao invente informacao que nao esta \
no texto.
"""


def slug_arquivo(caminho_arquivo):
    """Transforma um caminho de arquivo em um identificador seguro para
    nome de arquivo (sem acentos, espacos ou caracteres especiais)."""
    base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", base)


def montar_grupos(df_ons):
    """Agrupa os documentos do ONS por 'numero-SIGLA' extraido do titulo.
    Documentos cujo titulo nao segue esse padrao viram seu proprio grupo
    (um grupo de 1 documento so, sem historico)."""
    grupos = {}
    for _, linha in df_ons.iterrows():
        grupo = extrair_modulo_sufixo_do_titulo(linha["TITULO"])
        if grupo is None:
            grupo = f"documento::{slug_arquivo(linha['arquivo'])}"
        grupos.setdefault(grupo, []).append(linha)
    return grupos


def escolher_versao_mais_recente(documentos_do_grupo):
    """Escolhe o documento com ano/mes mais recente do grupo, e devolve
    tambem a lista de datas (ano, mes) das versoes anteriores. Se nenhum
    documento do grupo tiver data identificavel, usa o primeiro da lista
    (ordem arbitraria) e historico vazio."""
    documentos_com_data = []
    for doc in documentos_do_grupo:
        ano, mes = extrair_ano_mes_do_titulo(doc["TITULO"])
        if ano is not None and mes is not None:
            documentos_com_data.append(((ano, mes), doc))

    if not documentos_com_data:
        return documentos_do_grupo[0], []

    documentos_com_data.sort(key=lambda item: item[0])
    _, doc_mais_recente = documentos_com_data[-1]
    historico = [data for data, _ in documentos_com_data[:-1]]
    return doc_mais_recente, historico


def gerar_pagina_wiki(cliente, doc_mais_recente, historico):
    texto = doc_mais_recente["texto"][:LIMITE_CARACTERES_TEXTO]

    if historico:
        linhas_historico = "\n".join(f"- {ano}.{mes:02d}" for ano, mes in historico)
    else:
        linhas_historico = "Nenhuma versao anterior conhecida."

    prompt_usuario = (
        f"Titulo do documento (versao mais recente): {doc_mais_recente['TITULO']}\n\n"
        f"Versoes anteriores conhecidas (so datas):\n{linhas_historico}\n\n"
        f"Texto do documento:\n{texto}"
    )

    resposta = cliente.models.generate_content(
        model=MODELO,
        config=types.GenerateContentConfig(system_instruction=PROMPT_SISTEMA_WIKI),
        contents=prompt_usuario,
    )

    return resposta.text


def main():
    df = pd.read_csv(CAMINHO_METADADOS, keep_default_na=False)
    df_ons = df[df["FONTE"] == "ONS"]

    if df_ons.empty:
        print("Nenhum documento do ONS encontrado em", CAMINHO_METADADOS)
        return

    grupos = montar_grupos(df_ons)
    grupos_com_sobreposicao = {
        grupo: docs for grupo, docs in grupos.items() if len(docs) >= 2
    }
    print(
        f"{len(df_ons)} documentos do ONS agrupados em {len(grupos)} grupos "
        f"({len(grupos_com_sobreposicao)} com mais de uma versao -- so esses "
        "precisam de pagina na wiki; os demais ja sao inambiguos)."
    )

    os.makedirs(PASTA_SAIDA, exist_ok=True)
    cliente = genai.Client()  # le GEMINI_API_KEY (ou GOOGLE_API_KEY) do ambiente

    for i, (grupo, documentos_do_grupo) in enumerate(grupos_com_sobreposicao.items(), start=1):
        doc_mais_recente, historico = escolher_versao_mais_recente(documentos_do_grupo)
        print(
            f"[{i}/{len(grupos_com_sobreposicao)}] Gerando pagina para '{grupo}' "
            f"({len(documentos_do_grupo)} versao(oes) encontrada(s))..."
        )

        try:
            pagina = gerar_pagina_wiki(cliente, doc_mais_recente, historico)
        except Exception as erro:
            print(f"  [aviso] Falha ao gerar pagina para '{grupo}': {erro}. Pulando.")
            continue

        nome_arquivo = re.sub(r"[^a-zA-Z0-9_.-]", "_", grupo) + ".md"
        caminho_saida = os.path.join(PASTA_SAIDA, nome_arquivo)
        with open(caminho_saida, "w", encoding="utf-8") as f:
            f.write(f"# {grupo}\n\n")
            f.write(f"Fonte (versao vigente): {doc_mais_recente['TITULO']}\n\n")
            f.write(pagina)

        time.sleep(PAUSA_ENTRE_CHAMADAS_SEGUNDOS)

    print(f"\nPaginas da wiki salvas em: {PASTA_SAIDA}")


if __name__ == "__main__":
    main()
