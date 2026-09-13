"""
Passo 3a: extracao de documentos da pagina de Curtailment do ONS.

Esta pagina e renderizada no servidor (nao depende de JavaScript para
mostrar a tabela de documentos), entao um requests.get() simples
funciona aqui -- diferente da pagina de Procedimentos de Rede
(ver extrair_ons_procedimentos_rede.py).

Dependencias:
    pip install requests beautifulsoup4 pdfplumber
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

sys.path.append(os.path.dirname(__file__))
from utils_extracao import (
    remover_acentos,
    eh_documento_relevante,
    deduplicar_links_por_url,
    baixar_e_extrair_texto_pdf,
    salvar_documento,
)

URL_PAGINA_CURTAILMENT = "https://www.ons.org.br/Paginas/faq_curtailment.aspx"
TEMA = "curtailment"
DOMINIO_BASE_ONS = "ons.org.br"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


def inferir_tipo_documento(titulo):
    """Classificacao simples baseada em palavras-chave do titulo (Camada 1).
    Uma versao mais robusta (com LLM) pode substituir isso depois, mas o
    formato de saida (campo TIPO_DOCUMENTO) permanece o mesmo."""
    titulo_normalizado = remover_acentos(titulo.lower())
    if "nota tecnica" in titulo_normalizado:
        return "Nota Tecnica"
    if "relatorio" in titulo_normalizado or "diagnostico" in titulo_normalizado:
        return "Relatorio Tecnico"
    return "Documento (ONS)"


def listar_links_pdf(url_pagina):
    resposta = requests.get(url_pagina, headers=HEADERS, timeout=30)
    resposta.raise_for_status()

    dominio_pagina = urlparse(url_pagina).netloc
    sopa = BeautifulSoup(resposta.text, "html.parser")

    links_brutos = [
        (link.get_text(strip=True), link["href"])
        for link in sopa.find_all("a", href=True)
        if link["href"].lower().endswith(".pdf")
    ]

    links_deduplicados = deduplicar_links_por_url(links_brutos, dominio_pagina)

    return [
        (texto, url_pdf)
        for texto, url_pdf in links_deduplicados
        if eh_documento_relevante(texto, url_pdf, DOMINIO_BASE_ONS)
    ]


def main():
    print(f"Buscando links de PDF em: {URL_PAGINA_CURTAILMENT}")
    links = listar_links_pdf(URL_PAGINA_CURTAILMENT)
    print(f"{len(links)} documentos relevantes encontrados apos filtro.")

    for titulo, url_pdf in links:
        print(f"Baixando: {titulo} -> {url_pdf}")
        try:
            texto = baixar_e_extrair_texto_pdf(url_pdf)
            caminho_salvo = salvar_documento(
                fonte="ONS",
                tipo_documento=inferir_tipo_documento(titulo),
                titulo=titulo,
                url_pdf=url_pdf,
                tema=TEMA,
                texto=texto,
            )
            print(f"  Salvo em: {caminho_salvo}")
        except Exception as erro:
            print(f"  ERRO ao processar este documento: {erro}")


if __name__ == "__main__":
    main()
