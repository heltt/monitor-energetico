"""
Funcoes compartilhadas pelos scripts de extracao (ONS, ANEEL, etc.):
baixar PDF, extrair texto, aplicar o filtro de relevancia (Camada 1)
e salvar no formato padrao usado em data/raw/.

Manter essa logica em um lugar so garante que todos os scripts de
extracao usem o MESMO criterio de selecao de documentos.
"""

import os
import io
import re
import requests
import pdfplumber
from urllib.parse import urlparse, parse_qs, unquote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

PASTA_SAIDA = os.path.join("data", "raw")

# Textos de link genericos/nao-informativos: quando o texto do link e
# um desses (ou vazio), usamos o nome do arquivo na URL como titulo
# em vez do texto do link.
TERMOS_LINK_GENERICOS = {
    "baixar",
    "download",
    "clique aqui",
    "acesse aqui",
    "ver documento",
    "documento",
    "pdf",
}

# Termos que indicam que o PDF NAO e um documento regulatorio/tecnico
# do setor eletrico, mesmo estando hospedado no site da fonte
# (ex.: politica de privacidade, termos de uso, cookies).
TERMOS_EXCLUIDOS = [
    "politica de protecao de dados",
    "termos de uso",
    "politica de privacidade",
    "cookies",
    "lgpd",
]


def remover_acentos(texto):
    """Normalizacao simples para comparar textos sem depender de acentuacao."""
    substituicoes = str.maketrans("áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ", "aaaaeeioooucAAAAEEIOOOUC")
    return texto.translate(substituicoes)


def eh_documento_relevante(texto_link, url_pdf, dominio_base_permitido):
    """Filtro de relevancia (Camada 1): o link precisa apontar para um
    (sub)dominio do dominio base permitido (ex.: "ons.org.br" aceita
    tanto "www.ons.org.br" quanto "proxyportais.ons.org.br", mas
    rejeita dominios totalmente diferentes) e nao pode conter nenhum
    dos termos institucionais excluidos no texto do link."""
    dominio_do_link = urlparse(url_pdf).netloc
    if dominio_do_link and not dominio_do_link.endswith(dominio_base_permitido):
        return False

    texto_normalizado = remover_acentos(texto_link.lower())
    for termo in TERMOS_EXCLUIDOS:
        if termo in texto_normalizado:
            return False

    return True


def titulo_a_partir_da_url(url):
    """Quando o link nao tem texto visivel, monta um titulo a partir
    do nome do arquivo na URL. Trata tambem o caso de URLs de proxy
    (ex.: proxyportais.ons.org.br), onde o nome do arquivo real fica
    dentro do parametro de query '?url=...' em vez do caminho normal."""
    partes = urlparse(url)
    parametros = parse_qs(partes.query)

    if "url" in parametros:
        caminho_interno = unquote(parametros["url"][0])
    else:
        caminho_interno = unquote(partes.path)

    nome_arquivo = caminho_interno.rsplit("/", 1)[-1]
    nome_sem_extensao = re.sub(r"\.pdf$", "", nome_arquivo, flags=re.IGNORECASE)

    return nome_sem_extensao.strip() or "documento_sem_titulo"


def texto_e_informativo(texto):
    """Retorna False para texto vazio ou generico demais (ex.: 'Baixar',
    'Download'), que nao serve como titulo de documento."""
    texto_normalizado = remover_acentos(texto.strip().lower())
    return bool(texto_normalizado) and texto_normalizado not in TERMOS_LINK_GENERICOS


def deduplicar_links_por_url(links, dominio_base):
    """Recebe uma lista de (texto_link, href) e devolve uma lista
    (texto_link, url_absoluta) deduplicada por URL, ja com o texto
    mais informativo escolhido quando ha mais de um link para o
    mesmo PDF (ex.: titulo e botao 'BAIXAR'). Quando nenhum dos links
    para aquele PDF tem texto informativo (vazio ou generico como
    'Baixar'), usa o nome do arquivo extraido da propria URL como
    titulo (garante nomes unicos, em vez de todos carem no mesmo
    titulo generico)."""
    documentos_por_url = {}

    for texto, href in links:
        if href.startswith("/"):
            href = f"https://{dominio_base}" + href

        texto = texto.strip()

        if texto_e_informativo(texto):
            if href not in documentos_por_url or not texto_e_informativo(documentos_por_url[href]) \
                    or len(texto) > len(documentos_por_url[href]):
                documentos_por_url[href] = texto
        elif href not in documentos_por_url:
            documentos_por_url[href] = ""  # marca que ainda nao tem texto informativo

    # Para URLs que nunca receberam um texto informativo, usa o nome do arquivo
    for href, texto in documentos_por_url.items():
        if not texto_e_informativo(texto):
            documentos_por_url[href] = titulo_a_partir_da_url(href)

    # IMPORTANTE: documentos_por_url e {url: texto}, entao invertemos
    # a ordem aqui para devolver (texto, url) como o resto do codigo espera
    return [(texto, url) for url, texto in documentos_por_url.items()]


def baixar_e_extrair_texto_pdf(url_pdf):
    """Baixa um PDF e retorna o texto extraido de todas as paginas."""
    resposta = requests.get(url_pdf, headers=HEADERS, timeout=60)
    resposta.raise_for_status()

    texto_paginas = []
    with pdfplumber.open(io.BytesIO(resposta.content)) as pdf:
        for pagina in pdf.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto_paginas.append(texto_pagina)

    return "\n".join(texto_paginas)


def nome_arquivo_seguro(texto, prefixo):
    import re
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    texto = texto.strip("_")[:60]
    return f"{prefixo}_{texto}.txt"


def salvar_documento(fonte, tipo_documento, titulo, url_pdf, tema, texto, subpasta=None):
    pasta_destino = os.path.join(PASTA_SAIDA, subpasta) if subpasta else PASTA_SAIDA
    os.makedirs(pasta_destino, exist_ok=True)
    nome_arquivo = nome_arquivo_seguro(titulo, fonte.lower())
    caminho = os.path.join(pasta_destino, nome_arquivo)

    conteudo = (
        f"FONTE: {fonte}\n"
        f"TIPO_DOCUMENTO: {tipo_documento}\n"
        f"TITULO: {titulo}\n"
        f"URL_ORIGINAL: {url_pdf}\n"
        f"TEMA: {tema}\n"
        f"\n"
        f"TEXTO_COMPLETO:\n"
        f"{texto}\n"
    )

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)

    return caminho
