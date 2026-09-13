"""
Passo 4 do pipeline: le data/processed/chunks.csv, transforma cada
chunk em um vetor TF-IDF (frequencia de termos ponderada pela sua
raridade na colecao) e salva o indice pronto em
data/processed/indice_busca.pkl.

TF-IDF, resumido: cada chunk vira um vetor onde cada posicao
corresponde a uma palavra do vocabulario. O valor nessa posicao e
alto quando a palavra aparece muito naquele chunk mas e rara nos
outros chunks (ou seja, e uma palavra "caracteristica" daquele
chunk). Isso permite comparar a pergunta do usuario com os chunks
usando similaridade de cosseno, sem precisar de um modelo de
linguagem para gerar embeddings.

Este script so precisa ser rodado de novo quando os documentos
(data/processed/chunks.csv) mudarem.
"""

import os
import pickle

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

ARQUIVO_CHUNKS = os.path.join("data", "processed", "chunks.csv")
ARQUIVO_INDICE = os.path.join("data", "processed", "indice_busca.pkl")

# Lista basica de stopwords em portugues (artigos, preposicoes,
# conjuncoes, pronomes e verbos auxiliares muito comuns). Remover
# essas palavras do vocabulario evita que elas dominem a comparacao
# so por serem frequentes, sem carregar significado especifico.
STOPWORDS_PT = [
    "a", "à", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "as", "às",
    "com", "como", "da", "das", "de", "dela", "delas", "dele", "deles", "do",
    "dos", "e", "ela", "elas", "ele", "eles", "em", "entre", "essa", "essas",
    "esse", "esses", "esta", "está", "estamos", "estão", "estas", "este",
    "estes", "eu", "foi", "for", "foram", "fosse", "há", "isso", "isto", "já",
    "lhe", "lhes", "mais", "mas", "me", "mesmo", "meu", "meus", "minha",
    "minhas", "muito", "na", "não", "nas", "nem", "no", "nos", "nós", "nossa",
    "nossas", "nosso", "nossos", "num", "numa", "o", "os", "ou", "para", "pela",
    "pelas", "pelo", "pelos", "por", "qual", "quando", "que", "quem", "se",
    "sem", "ser", "será", "seu", "seus", "só", "sua", "suas", "também", "te",
    "tem", "têm", "tinha", "um", "uma", "umas", "uns", "você", "vocês",
]


def main():
    df_chunks = pd.read_csv(ARQUIVO_CHUNKS, keep_default_na=False)

    vetorizador = TfidfVectorizer(stop_words=STOPWORDS_PT, max_df=0.85)
    matriz_tfidf = vetorizador.fit_transform(df_chunks["texto_chunk"])

    # Guardamos so as colunas necessarias para exibir/citar um resultado
    # de busca (nao precisamos do texto completo do documento original,
    # so do chunk e de como referenciar a fonte).
    colunas_para_recuperacao = [
        "chunk_id", "arquivo", "fonte", "tipo_documento", "titulo",
        "data_publicacao", "url_original", "texto_chunk",
    ]
    df_recuperacao = df_chunks[colunas_para_recuperacao]

    indice = {
        "vetorizador": vetorizador,
        "matriz_tfidf": matriz_tfidf,
        "chunks": df_recuperacao,
    }

    os.makedirs(os.path.dirname(ARQUIVO_INDICE), exist_ok=True)
    with open(ARQUIVO_INDICE, "wb") as f:
        pickle.dump(indice, f)

    print(f"{matriz_tfidf.shape[0]} chunks indexados.")
    print(f"Vocabulario: {len(vetorizador.vocabulary_)} termos.")
    print(f"Indice salvo em: {ARQUIVO_INDICE}")


if __name__ == "__main__":
    main()
