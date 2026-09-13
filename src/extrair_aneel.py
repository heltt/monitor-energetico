"""
Passo 3b: extracao de documentos da ANEEL.

Diferente do ONS, a Biblioteca Virtual da ANEEL e uma pagina de busca
(mais fragil de raspar). Em vez disso, este script usa o padrao de
URL que a ANEEL usa para os PDFs dos atos normativos:

    https://www2.aneel.gov.br/cedoc/{tipo}{ano}{numero}.pdf

Exemplos reais confirmados:
    Resolucao Normativa 1.003/2022 -> ren20221003.pdf
    Portaria 7.030/2025            -> prt20257030.pdf

Ou seja: voce informa uma lista dos atos que quer (tipo, numero, ano),
e o script monta a URL, baixa o PDF e extrai o texto.

Dependencias:
    pip install requests pdfplumber
"""

import os
import requests
import pdfplumber
import io

PASTA_SAIDA = os.path.join("data", "raw")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# Mapeia o "tipo" usado na URL da ANEEL para um nome legivel
TIPOS_ATO = {
    "ren": "Resolucao Normativa",
    "prt": "Portaria",
    "rea": "Resolucao Autorizativa",
}

# ------------------------------------------------------------------
# LISTA DE ATOS PARA BAIXAR
# Adicione ou remova itens aqui conforme os documentos que voces
# decidirem que sao relevantes (ex.: os que mapeamos na conversa).
# ------------------------------------------------------------------
ATOS_PARA_BAIXAR = [
    # (tipo, numero, ano, tema)
    ("ren", 1030, 2022, "curtailment"),
    ("ren", 1122, 2025, "transmissao,conexao_rede"),
    ("ren", 1069, 2023, "transmissao,conexao_rede"),
    ("prt", 7030, 2025, "agenda_regulatoria"),
]


def montar_url(tipo, numero, ano):
    return f"https://www2.aneel.gov.br/cedoc/{tipo}{ano}{numero}.pdf"


def baixar_e_extrair_texto_pdf(url_pdf):
    resposta = requests.get(url_pdf, headers=HEADERS, timeout=60)
    resposta.raise_for_status()

    texto_paginas = []
    with pdfplumber.open(io.BytesIO(resposta.content)) as pdf:
        for pagina in pdf.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto_paginas.append(texto_pagina)

    return "\n".join(texto_paginas)


def salvar_documento(tipo, numero, ano, tema, url_pdf, texto):
    os.makedirs(PASTA_SAIDA, exist_ok=True)

    tipo_legivel = TIPOS_ATO.get(tipo, tipo)
    numero_formatado = f"{numero}/{ano}"
    nome_arquivo = f"aneel_{tipo}_{numero}_{ano}.txt"
    caminho = os.path.join(PASTA_SAIDA, nome_arquivo)

    conteudo = (
        f"FONTE: ANEEL\n"
        f"TIPO_DOCUMENTO: {tipo_legivel}\n"
        f"NUMERO_ATO: {tipo_legivel} no {numero_formatado}\n"
        f"URL_ORIGINAL: {url_pdf}\n"
        f"TEMA: {tema}\n"
        f"\n"
        f"TEXTO_COMPLETO:\n"
        f"{texto}\n"
    )

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)

    return caminho


def main():
    for tipo, numero, ano, tema in ATOS_PARA_BAIXAR:
        url_pdf = montar_url(tipo, numero, ano)
        print(f"Baixando {TIPOS_ATO.get(tipo, tipo)} {numero}/{ano} -> {url_pdf}")
        try:
            texto = baixar_e_extrair_texto_pdf(url_pdf)
            caminho_salvo = salvar_documento(tipo, numero, ano, tema, url_pdf, texto)
            print(f"  Salvo em: {caminho_salvo}")
        except Exception as erro:
            print(f"  ERRO ao processar este ato: {erro}")


if __name__ == "__main__":
    main()
