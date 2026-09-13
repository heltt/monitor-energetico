"""
Passo 2 do pipeline: le os documentos brutos em data/raw/ (incluindo
subpastas, como data/raw/ons/ e data/raw/dou/), separa os metadados
do cabecalho (FONTE, TIPO_DOCUMENTO, etc.) do texto do documento, e
monta uma tabela unica salva em data/processed/.

Formato esperado de cada arquivo em data/raw/ (ou subpastas):

    FONTE: ...
    TIPO_DOCUMENTO: ...
    NUMERO_ATO: ...
    (linha em branco)
    RESUMO_EXECUTIVO: (ou TEXTO_COMPLETO:)
    <texto do documento>
"""

import os
import pandas as pd

PASTA_ENTRADA = os.path.join("data", "raw")
ARQUIVO_SAIDA = os.path.join("data", "processed", "metadados_documentos.csv")

# Chaves de metadado que sabemos que podem aparecer no cabecalho dos arquivos
CHAVES_METADADO = [
    "FONTE",
    "TIPO_DOCUMENTO",
    "NUMERO_ATO",
    "DATA_PUBLICACAO",
    "DATA_COLETA",
    "URL_ORIGINAL",
    "TEMA",
    "TITULO",
    "CATEGORIA_ORIGEM",
]

# Rotulos que podem aparecer como a primeira linha do corpo do texto
# (nao sao metadado, entao sao removidos do inicio do texto)
ROTULOS_DE_CORPO = ["RESUMO_EXECUTIVO:", "TEXTO_COMPLETO:", "TEXTO:"]


def listar_arquivos_txt(pasta_raiz):
    """Percorre pasta_raiz e todas as subpastas, devolvendo o caminho
    completo de cada arquivo .txt encontrado, em ordem estavel."""
    caminhos = []
    for pasta_atual, _subpastas, arquivos in os.walk(pasta_raiz):
        for nome_arquivo in arquivos:
            if nome_arquivo.endswith(".txt"):
                caminhos.append(os.path.join(pasta_atual, nome_arquivo))
    return sorted(caminhos)


def parse_documento(caminho_arquivo, pasta_raiz):
    """Le um arquivo .txt e devolve um dicionario com metadados + texto."""
    with open(caminho_arquivo, encoding="utf-8") as f:
        linhas = f.read().splitlines()

    metadados = {}
    indice_fim_cabecalho = len(linhas)

    for i, linha in enumerate(linhas):
        if linha.strip() == "":
            # Linha em branco marca o fim do cabecalho de metadados
            indice_fim_cabecalho = i
            break

        if ":" in linha:
            chave, _, valor = linha.partition(":")
            chave = chave.strip()
            if chave in CHAVES_METADADO:
                metadados[chave] = valor.strip()

    # Tudo depois da linha em branco e considerado o corpo do texto
    linhas_corpo = linhas[indice_fim_cabecalho + 1:]

    # Remove uma eventual linha de rotulo (ex: "TEXTO_COMPLETO:") no inicio do corpo
    if linhas_corpo and linhas_corpo[0].strip() in ROTULOS_DE_CORPO:
        linhas_corpo = linhas_corpo[1:]

    texto = "\n".join(linhas_corpo).strip()

    # Caminho relativo (ex.: "ons/algum_arquivo.txt") para saber de qual
    # subpasta/fonte o documento veio, mesmo com nomes de arquivo parecidos
    caminho_relativo = os.path.relpath(caminho_arquivo, pasta_raiz)

    metadados["arquivo"] = caminho_relativo
    metadados["texto"] = texto
    metadados["num_caracteres"] = len(texto)

    return metadados


def main():
    registros = []

    for caminho in listar_arquivos_txt(PASTA_ENTRADA):
        registros.append(parse_documento(caminho, PASTA_ENTRADA))

    df = pd.DataFrame(registros)

    # Garante que todas as colunas de metadado existam, mesmo que vazias
    colunas_ordenadas = ["arquivo"] + CHAVES_METADADO + ["num_caracteres", "texto"]
    for coluna in colunas_ordenadas:
        if coluna not in df.columns:
            df[coluna] = ""
    df = df[colunas_ordenadas]

    os.makedirs(os.path.dirname(ARQUIVO_SAIDA), exist_ok=True)
    df.to_csv(ARQUIVO_SAIDA, index=False)

    print(f"{len(df)} documentos processados.")
    print(f"Tabela salva em: {ARQUIVO_SAIDA}")
    print()
    print("Contagem por FONTE:")
    print(df["FONTE"].value_counts().to_string())


if __name__ == "__main__":
    main()
