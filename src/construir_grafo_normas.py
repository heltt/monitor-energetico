"""
Constroi um grafo temporal de relacoes entre normas do setor eletrico,
considerando TODAS as fontes do corpus (ONS, DOU, e futuramente ANEEL).

Diferente da wiki (construir_wiki_ons.py), que so resume/consolida
REVISOES do MESMO submodulo do ONS, este grafo modela relacoes ENTRE
normas diferentes -- permitindo perguntas estruturais que a wiki nao
responde, como "o que estava em vigor nesta data" ou "quais normas
citam a Resolucao X".

Duas relacoes sao extraidas por regex, SEM gastar nenhuma chamada de
IA:
- "sucede": entre versoes consecutivas do MESMO submodulo do ONS
  (reaproveita o agrupamento numero-SIGLA usado na wiki).
- "cita": quando o texto de QUALQUER documento (de qualquer fonte)
  menciona explicitamente outra norma por numero (Resolucao, Lei,
  Decreto, Portaria, Submodulo).

Relacoes mais sofisticadas -- uma norma REVOGA ou ALTERA outra, nao so
cita -- exigiriam um LLM lendo os dois textos para confirmar a relacao;
isso fica como proxima etapa, nao implementada aqui.

Saida: dois CSVs em data/grafo/
- nos.csv: um no por documento (id, fonte, tipo, titulo, data) + um no
  por referencia externa citada mas ainda sem texto completo no nosso
  corpus (fonte = "referencia_externa")
- arestas.csv: origem_id, destino_id, tipo_relacao, data

Uso:
    python src/construir_grafo_normas.py
"""

import os
import re

import pandas as pd

from utils_normas_ons import extrair_ano_mes_do_titulo, extrair_modulo_sufixo_do_titulo

CAMINHO_METADADOS = os.path.join("data", "processed", "metadados_documentos.csv")
PASTA_SAIDA = os.path.join("data", "grafo")


def normalizar_numero_com_separador_de_milhar(numero_bruto):
    """Remove pontos de milhar para normalizar numeros citados de
    formas diferentes (ex.: '1.030' e '1030' viram o mesmo ID)."""
    return numero_bruto.replace(".", "")


# Padroes de citacao: (regex, template do ID normalizado, funcao de
# normalizacao do numero capturado). Resolucoes/Leis/Decretos usam
# ponto como separador de milhar (ex.: "1.030" = mil e trinta), entao
# o ponto e removido. Submodulos do ONS usam ponto como notacao
# modulo.submodulo (ex.: "2.10" = modulo 2, submodulo 10) -- NAO pode
# remover o ponto nesse caso, ou "2.10" viraria "210".
PADROES_CITACAO = [
    (re.compile(r"Resolu[cç][aã]o\s+Normativa\s+n[ºo°]?\.?\s*([\d.]+)", re.IGNORECASE), "ANEEL-REN-{}", normalizar_numero_com_separador_de_milhar),
    (re.compile(r"Resolu[cç][aã]o\s+Homologat[oó]ria\s+n[ºo°]?\.?\s*([\d.]+)", re.IGNORECASE), "ANEEL-REH-{}", normalizar_numero_com_separador_de_milhar),
    (re.compile(r"Despacho\s+n[ºo°]?\.?\s*([\d.]+)", re.IGNORECASE), "ANEEL-DESPACHO-{}", normalizar_numero_com_separador_de_milhar),
    (re.compile(r"Decreto\s+n[ºo°]?\.?\s*([\d.]+)", re.IGNORECASE), "DECRETO-{}", normalizar_numero_com_separador_de_milhar),
    (re.compile(r"\bLei\s+n[ºo°]?\.?\s*([\d.]+)", re.IGNORECASE), "LEI-{}", normalizar_numero_com_separador_de_milhar),
    (re.compile(r"Portaria\s+n[ºo°]?\.?\s*([\d.]+)", re.IGNORECASE), "PORTARIA-{}", normalizar_numero_com_separador_de_milhar),
    (re.compile(r"Subm[oó]dulo\s*(\d+\.\d+)", re.IGNORECASE), "ONS-SUBMODULO-{}", lambda numero: numero),
]


def extrair_citacoes(texto):
    """Devolve o conjunto de IDs normalizados de normas citadas no
    texto de um documento (sem duplicatas dentro do mesmo texto)."""
    citacoes = set()
    for padrao, template, normalizar in PADROES_CITACAO:
        for numero_bruto in padrao.findall(texto):
            citacoes.add(template.format(normalizar(numero_bruto)))
    return citacoes


def montar_nos_documentos(df):
    """Um no por documento do corpus, de qualquer fonte."""
    return [
        {
            "id": linha["arquivo"],
            "fonte": linha["FONTE"],
            "tipo": "documento",
            "titulo": linha["TITULO"],
            "data": linha["DATA_PUBLICACAO"],
        }
        for _, linha in df.iterrows()
    ]


def montar_arestas_sucessao(df_ons):
    """Aresta 'sucede' entre versoes consecutivas do mesmo submodulo do
    ONS (reaproveita o mesmo agrupamento usado na wiki)."""
    grupos = {}
    for _, linha in df_ons.iterrows():
        grupo = extrair_modulo_sufixo_do_titulo(linha["TITULO"])
        if grupo is None:
            continue
        ano, mes = extrair_ano_mes_do_titulo(linha["TITULO"])
        if ano is None or mes is None:
            continue
        grupos.setdefault(grupo, []).append(((ano, mes), linha))

    arestas = []
    for versoes in grupos.values():
        versoes.sort(key=lambda item: item[0])
        for (data_anterior, doc_anterior), (data_nova, doc_novo) in zip(versoes, versoes[1:]):
            arestas.append({
                "origem_id": doc_novo["arquivo"],
                "destino_id": doc_anterior["arquivo"],
                "tipo_relacao": "sucede",
                "data": doc_novo["DATA_PUBLICACAO"] or f"{data_nova[0]}.{data_nova[1]:02d}",
            })
    return arestas


def montar_arestas_citacao(df):
    """Aresta 'cita' de cada documento para cada norma mencionada no
    seu texto. O destino normalmente e uma referencia externa (norma
    citada mas ainda sem texto completo no nosso corpus)."""
    arestas = []
    referencias_externas = set()

    for _, linha in df.iterrows():
        for destino_id in extrair_citacoes(linha["texto"]):
            arestas.append({
                "origem_id": linha["arquivo"],
                "destino_id": destino_id,
                "tipo_relacao": "cita",
                "data": linha["DATA_PUBLICACAO"],
            })
            referencias_externas.add(destino_id)

    return arestas, referencias_externas


def montar_nos_referencia_externa(referencias_externas):
    return [
        {"id": ref_id, "fonte": "referencia_externa", "tipo": "norma_citada_sem_texto_completo",
         "titulo": ref_id, "data": ""}
        for ref_id in sorted(referencias_externas)
    ]


def main():
    df = pd.read_csv(CAMINHO_METADADOS, keep_default_na=False)

    nos_documentos = montar_nos_documentos(df)

    df_ons = df[df["FONTE"] == "ONS"]
    arestas_sucessao = montar_arestas_sucessao(df_ons)

    arestas_citacao, referencias_externas = montar_arestas_citacao(df)
    nos_referencia_externa = montar_nos_referencia_externa(referencias_externas)

    df_nos = pd.DataFrame(nos_documentos + nos_referencia_externa)
    df_arestas = pd.DataFrame(arestas_sucessao + arestas_citacao)

    os.makedirs(PASTA_SAIDA, exist_ok=True)
    df_nos.to_csv(os.path.join(PASTA_SAIDA, "nos.csv"), index=False)
    df_arestas.to_csv(os.path.join(PASTA_SAIDA, "arestas.csv"), index=False)

    print(f"{len(df_nos)} nos ({len(nos_documentos)} documentos + {len(nos_referencia_externa)} referencias externas)")
    print(f"{len(df_arestas)} arestas ({len(arestas_sucessao)} de sucessao + {len(arestas_citacao)} de citacao)")
    print(f"Salvo em: {PASTA_SAIDA}")


if __name__ == "__main__":
    main()
