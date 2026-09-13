"""
Passo 3 do pipeline: le a tabela de metadados/texto completo
(data/processed/metadados_documentos.csv) e corta cada documento em
pedacos menores (chunks), salvando em data/processed/chunks.csv.

Por que cortar em pedacos:
- Documentos grandes (ex.: submodulos do ONS em PDF) sao grandes
  demais para indexar ou mandar inteiros para um LLM.
- Pedacos menores permitem que a busca (proximo passo) encontre o
  TRECHO especifico relevante para a pergunta, nao o documento
  inteiro.

Estrategia de corte:
1. Divide o texto em paragrafos (por linha em branco).
2. Agrupa paragrafos consecutivos ate atingir o tamanho maximo de um
   chunk, tentando nao cortar no meio de um paragrafo.
3. Se um paragrafo sozinho for maior que o tamanho maximo (comum em
   PDFs extraidos sem quebras de paragrafo claras), corta ele em
   pedacos de tamanho fixo, com sobreposicao entre eles (para nao
   perder contexto na fronteira do corte).
"""

import os
import pandas as pd

ARQUIVO_ENTRADA = os.path.join("data", "processed", "metadados_documentos.csv")
ARQUIVO_SAIDA = os.path.join("data", "processed", "chunks.csv")

TAMANHO_MAXIMO_CHUNK = 1500  # caracteres
SOBREPOSICAO = 200  # caracteres, usado so no corte forcado de paragrafo gigante


def dividir_paragrafo_gigante(paragrafo, tamanho_maximo, sobreposicao):
    """Corta um paragrafo maior que o tamanho maximo em pedacos de
    tamanho fixo, com sobreposicao entre pedacos consecutivos."""
    pedacos = []
    inicio = 0
    while inicio < len(paragrafo):
        fim = inicio + tamanho_maximo
        pedacos.append(paragrafo[inicio:fim])
        inicio = fim - sobreposicao if fim < len(paragrafo) else fim
    return pedacos


def gerar_chunks_de_texto(texto, tamanho_maximo=TAMANHO_MAXIMO_CHUNK, sobreposicao=SOBREPOSICAO):
    """Recebe o texto completo de um documento e devolve uma lista de
    chunks (strings)."""
    paragrafos = [p.strip() for p in texto.split("\n") if p.strip()]

    chunks = []
    chunk_atual = ""

    for paragrafo in paragrafos:
        # Paragrafo sozinho ja maior que o limite: corta ele em pedacos
        # fixos, primeiro fechando o chunk atual se houver algo nele
        if len(paragrafo) > tamanho_maximo:
            if chunk_atual:
                chunks.append(chunk_atual)
                chunk_atual = ""
            chunks.extend(dividir_paragrafo_gigante(paragrafo, tamanho_maximo, sobreposicao))
            continue

        # Adicionar este paragrafo ultrapassaria o limite: fecha o
        # chunk atual e comeca um novo com este paragrafo
        if chunk_atual and len(chunk_atual) + len(paragrafo) + 1 > tamanho_maximo:
            chunks.append(chunk_atual)
            chunk_atual = paragrafo
        else:
            chunk_atual = f"{chunk_atual}\n{paragrafo}" if chunk_atual else paragrafo

    if chunk_atual:
        chunks.append(chunk_atual)

    return chunks


def main():
    df_documentos = pd.read_csv(ARQUIVO_ENTRADA, keep_default_na=False)

    registros_chunks = []

    for _, documento in df_documentos.iterrows():
        texto = documento["texto"]
        if not texto or not texto.strip():
            continue

        chunks = gerar_chunks_de_texto(texto)

        for indice, texto_chunk in enumerate(chunks):
            registros_chunks.append({
                "chunk_id": f"{documento['arquivo']}::chunk{indice}",
                "arquivo": documento["arquivo"],
                "fonte": documento["FONTE"],
                "tipo_documento": documento["TIPO_DOCUMENTO"],
                "titulo": documento["TITULO"],
                "data_publicacao": documento["DATA_PUBLICACAO"],
                "url_original": documento["URL_ORIGINAL"],
                "tema": documento["TEMA"],
                "chunk_index": indice,
                "texto_chunk": texto_chunk,
                "num_caracteres": len(texto_chunk),
            })

    df_chunks = pd.DataFrame(registros_chunks)

    os.makedirs(os.path.dirname(ARQUIVO_SAIDA), exist_ok=True)
    df_chunks.to_csv(ARQUIVO_SAIDA, index=False)

    print(f"{len(df_documentos)} documentos -> {len(df_chunks)} chunks gerados.")
    print(f"Tabela salva em: {ARQUIVO_SAIDA}")
    print()
    print("Tamanho medio de chunk (caracteres):", round(df_chunks["num_caracteres"].mean(), 1))
    print("Chunks por documento (media):", round(len(df_chunks) / len(df_documentos), 1))


if __name__ == "__main__":
    main()
