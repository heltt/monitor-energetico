"""
Passo 3c: extracao dos Procedimentos de Rede do ONS.

Essa pagina carrega a lista de modulos/submodulos via JavaScript
(SharePoint), entao um requests.get() simples nao encontra nada --
precisamos de um navegador de verdade para renderizar a pagina antes
de procurar os links.

Dependencias:
    pip install playwright
    playwright install chromium      # baixa o navegador (uma vez so)
"""

import os
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

sys.path.append(os.path.dirname(__file__))
from utils_extracao import (
    eh_documento_relevante,
    deduplicar_links_por_url,
    baixar_e_extrair_texto_pdf,
    salvar_documento,
)

URL_PROCEDIMENTOS_REDE = "https://www.ons.org.br/paginas/sobre-o-ons/procedimentos-de-rede/vigentes"
TEMA = "procedimentos_de_rede,transmissao,transicao_energetica"

# Dominio base aceito para os links de documento. Os PDFs reais sao
# servidos por um subdominio de proxy (proxyportais.ons.org.br), entao
# aceitamos qualquer subdominio de ons.org.br -- nao so o dominio exato
# da pagina (www.ons.org.br).
DOMINIO_BASE_ONS = "ons.org.br"


def listar_links_pdf_renderizados(url_pagina):
    """Abre a pagina num navegador headless, espera o JavaScript
    carregar o conteudo, e retorna os links de PDF encontrados."""
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        pagina = navegador.new_page()
        pagina.goto(url_pagina, wait_until="networkidle", timeout=60000)

        # Da um tempo extra para garantir que listas carregadas de forma
        # assincrona (comum em SharePoint) ja tenham aparecido no DOM
        pagina.wait_for_timeout(3000)

        elementos_link = pagina.query_selector_all("a[href$='.pdf']")
        links = [
            (elemento.inner_text().strip(), elemento.get_attribute("href"))
            for elemento in elementos_link
        ]

        navegador.close()

    dominio_pagina = urlparse(url_pagina).netloc
    links_deduplicados = deduplicar_links_por_url(links, dominio_pagina)

    links_filtrados = [
        (texto, url_pdf)
        for texto, url_pdf in links_deduplicados
        if eh_documento_relevante(texto, url_pdf, DOMINIO_BASE_ONS)
    ]

    return links_filtrados


def main():
    print(f"Renderizando pagina: {URL_PROCEDIMENTOS_REDE}")
    links = listar_links_pdf_renderizados(URL_PROCEDIMENTOS_REDE)
    print(f"{len(links)} documentos relevantes encontrados apos filtro.")

    for titulo, url_pdf in links:
        print(f"Baixando: {titulo} -> {url_pdf}")
        try:
            texto = baixar_e_extrair_texto_pdf(url_pdf)
            caminho_salvo = salvar_documento(
                fonte="ONS",
                tipo_documento="Procedimento de Rede",
                titulo=titulo,
                url_pdf=url_pdf,
                tema=TEMA,
                texto=texto,
                subpasta="ons",
            )
            print(f"  Salvo em: {caminho_salvo}")
        except Exception as erro:
            print(f"  ERRO ao processar este documento: {erro}")


if __name__ == "__main__":
    main()
