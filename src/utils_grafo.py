"""
Modulo compartilhado para carregar e consultar o grafo de normas
(gerado por construir_grafo_normas.py) -- usado tanto pelo painel
(app/painel.py) quanto pela geracao de resposta com IA
(gerar_resposta.py).
"""

import os
import re

import pandas as pd

CAMINHO_NOS_GRAFO = os.path.join("data", "grafo", "nos.csv")
CAMINHO_ARESTAS_GRAFO = os.path.join("data", "grafo", "arestas.csv")

# Referencias externas (normas citadas mas ainda sem texto completo no
# nosso corpus) tem como ID um codigo interno normalizado (ex.:
# "ANEEL-REN-583"). Esses padroes convertem esse codigo num rotulo
# legivel em portugues (ex.: "ANEEL Resolucao Normativa no 583"), para
# nao vazar codigos internos em respostas do chat ou na interface.
PADROES_ROTULO_LEGIVEL = [
    (re.compile(r"^ANEEL-REN-(\d+)$"), "ANEEL Resolução Normativa nº {}"),
    (re.compile(r"^ANEEL-REH-(\d+)$"), "ANEEL Resolução Homologatória nº {}"),
    (re.compile(r"^ANEEL-DESPACHO-(\d+)$"), "ANEEL Despacho nº {}"),
    (re.compile(r"^DECRETO-(\d+)$"), "Decreto nº {}"),
    (re.compile(r"^LEI-(\d+)$"), "Lei nº {}"),
    (re.compile(r"^PORTARIA-(\d+)$"), "Portaria nº {}"),
    (re.compile(r"^ONS-SUBMODULO-(\d+\.\d+)$"), "ONS Submódulo {} (sufixo do tipo de documento não identificado na citação)"),
]


def rotulo_legivel(identificador):
    """Converte o ID normalizado de uma referencia externa num rotulo
    legivel em portugues. Se o ID nao corresponder a nenhum padrao
    conhecido, devolve o proprio ID sem alteracao."""
    for padrao, template in PADROES_ROTULO_LEGIVEL:
        encontrado = padrao.match(identificador)
        if encontrado:
            return template.format(encontrado.group(1))
    return identificador


def carregar_grafo():
    """Le os nos e arestas do grafo de normas. Devolve (None, None) se
    o grafo ainda nao foi gerado, para quem usa degradar graciosamente
    em vez de quebrar."""
    if not os.path.exists(CAMINHO_NOS_GRAFO) or not os.path.exists(CAMINHO_ARESTAS_GRAFO):
        return None, None
    df_nos = pd.read_csv(CAMINHO_NOS_GRAFO, keep_default_na=False)
    df_arestas = pd.read_csv(CAMINHO_ARESTAS_GRAFO, keep_default_na=False)
    return df_nos, df_arestas


def titulos_relacionados(id_documento, df_nos, df_arestas, tipo_relacao="cita"):
    """Para um tipo de relacao (por padrao, 'cita'), devolve uma tupla
    (titulos_que_este_documento_referencia, titulos_que_referenciam_este_documento).
    Documentos reais usam o titulo de verdade; referencias externas sem
    titulo proprio (titulo == id, ver construir_grafo_normas.py) usam
    um rotulo legivel derivado do codigo interno, em vez do codigo cru."""
    titulo_por_id = dict(zip(df_nos["id"], df_nos["titulo"]))

    def rotulo(id_norma):
        titulo = titulo_por_id.get(id_norma)
        if titulo is None or titulo == id_norma:
            return rotulo_legivel(id_norma)
        return titulo

    arestas_do_tipo = df_arestas[df_arestas["tipo_relacao"] == tipo_relacao]

    ids_referenciados = arestas_do_tipo[arestas_do_tipo["origem_id"] == id_documento]["destino_id"]
    ids_que_referenciam = arestas_do_tipo[arestas_do_tipo["destino_id"] == id_documento]["origem_id"]

    referenciados = [rotulo(i) for i in ids_referenciados]
    referenciadores = [rotulo(i) for i in ids_que_referenciam]

    return referenciados, referenciadores
