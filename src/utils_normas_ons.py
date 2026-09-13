"""
Modulo compartilhado para interpretar padroes nos titulos dos documentos
do ONS, usado tanto pelo painel (app/painel.py) quanto pela construcao
da wiki de normas (construir_wiki_ons.py).

Os titulos dos submodulos do ONS seguem (na maioria dos casos) o padrao:
    "Submódulo <numero>-<SIGLA>_<ano>.<mes>"
    ex.: "Submódulo 2.10-RQ_2023.10"

De onde extraimos duas coisas uteis:
- ano/mes de revisao (usado no grafico do painel)
- numero do submodulo + sigla do tipo de documento (usado para agrupar
  todas as revisoes do MESMO assunto regulatorio na wiki, ja que a
  sigla parece indicar o tipo de documento dentro do modulo -- ex.:
  RQ = Requisitos, PR = Procedimento, OP = Operacao, RS = Relatorio/
  Resultado, CR = Criterios. Essa e uma suposicao baseada no padrao
  observado nos dados; pode precisar de ajuste.
"""

import re

# Ano e mes de revisao (ex.: "2024.10" -> ano=2024, mes=10)
PADRAO_ANO_MES_TITULO = re.compile(r"(20\d{2})\.(0[1-9]|1[0-2])\b")

# Numero do submodulo + sigla do tipo de documento (ex.: "2.10-RQ").
# Sem \b no final: o "_" que normalmente vem depois da sigla (ex.:
# "2.10-RQ_2023.10") conta como caractere de palavra para o regex,
# entao um \b ali nunca fecharia o match.
PADRAO_MODULO_SUFIXO = re.compile(r"(\d+\.\d+)-([A-Za-z]{2,3})")


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


def extrair_modulo_sufixo_do_titulo(titulo):
    """Extrai a chave de agrupamento 'numero-SIGLA' de um titulo do ONS
    (ex.: 'Submódulo 2.10-RQ_2023.10' -> '2.10-RQ'). Devolve None se o
    padrao nao for encontrado (ex.: titulos que nao seguem a convencao
    de nomenclatura dos submodulos)."""
    if not titulo:
        return None
    encontrado = PADRAO_MODULO_SUFIXO.search(titulo)
    if not encontrado:
        return None
    numero, sigla = encontrado.groups()
    return f"{numero}-{sigla.upper()}"
