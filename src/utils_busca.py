"""
Modulo compartilhado de busca: carrega o indice TF-IDF salvo por
construir_indice_busca.py e oferece a funcao de busca por
similaridade, usada tanto pelo script de teste manual
(testar_busca.py) quanto pela geracao de resposta com IA
(gerar_resposta.py) e futuramente pelo dashboard.
"""

import os
import pickle

from sklearn.metrics.pairwise import cosine_similarity

ARQUIVO_INDICE = os.path.join("data", "processed", "indice_busca.pkl")
NUMERO_RESULTADOS_PADRAO = 5


def carregar_indice(caminho=ARQUIVO_INDICE):
    with open(caminho, "rb") as f:
        return pickle.load(f)


def buscar(pergunta, indice, top_n=NUMERO_RESULTADOS_PADRAO):
    """Devolve os top_n chunks mais similares a pergunta, ordenados do
    mais para o menos relevante."""
    vetorizador = indice["vetorizador"]
    matriz_tfidf = indice["matriz_tfidf"]
    df_chunks = indice["chunks"]

    vetor_pergunta = vetorizador.transform([pergunta])
    similaridades = cosine_similarity(vetor_pergunta, matriz_tfidf)[0]

    indices_ordenados = similaridades.argsort()[::-1][:top_n]

    resultados = []
    for indice_chunk in indices_ordenados:
        linha = df_chunks.iloc[indice_chunk]
        resultados.append({
            "chunk_id": linha["chunk_id"],
            "arquivo": linha["arquivo"],
            "score": similaridades[indice_chunk],
            "fonte": linha["fonte"],
            "titulo": linha["titulo"],
            "data_publicacao": linha["data_publicacao"],
            "url_original": linha["url_original"],
            "texto_chunk": linha["texto_chunk"],
        })

    return resultados
