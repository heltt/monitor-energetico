"""
Processa um ZIP diario do DOU (baixado manualmente de
in.gov.br/dados-abertos) e extrai so as publicacoes relacionadas ao
setor eletrico/energia (ANEEL, Ministerio de Minas e Energia, etc.),
salvando cada uma no formato padrao em data/raw/dou/.

Formato do XML de cada publicacao (uma por arquivo):
    <article ... artCategory="Ministerio/Orgao/Subordinada" pubDate="..." ...>
      <body>
        <Identifica><![CDATA[titulo]]></Identifica>
        <Ementa><![CDATA[...]]></Ementa>
        <Texto><![CDATA[<p>...</p>]]></Texto>
      </body>
    </article>

Uso:
    python src/processar_zip_dou.py caminho/para/o/arquivo.zip
"""

import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(__file__))
from utils_extracao import remover_acentos

PASTA_SAIDA = os.path.join("data", "raw", "dou")

# Termos que identificam publicacoes do setor eletrico/energia no
# campo artCategory (que traz o caminho institucional do orgao que
# publicou). Comparacao e feita sem acentos e em minusculas.
TERMOS_RELEVANTES = [
    "agencia nacional de energia eletrica",
    "aneel",
    "ministerio de minas e energia",
    "operador nacional do sistema eletrico",
    "camara de comercializacao de energia eletrica",
    "empresa de pesquisa energetica",
]


def categoria_e_relevante(art_category):
    categoria_normalizada = remover_acentos(art_category.lower())
    return any(termo in categoria_normalizada for termo in TERMOS_RELEVANTES)


def limpar_html(texto_html):
    """Remove tags HTML do campo Texto, preservando quebras de paragrafo."""
    sopa = BeautifulSoup(texto_html or "", "html.parser")
    paragrafos = [p.get_text(strip=True) for p in sopa.find_all("p")]
    if paragrafos:
        return "\n".join(paragrafos)
    return sopa.get_text(strip=True)


def extrair_texto_cdata(elemento_pai, tag):
    """Le o texto de uma tag (pode vir vazia) dentro do <body>."""
    elemento = elemento_pai.find(tag)
    if elemento is None or elemento.text is None:
        return ""
    return elemento.text.strip()


def nome_arquivo_seguro(titulo, id_materia):
    import re
    base = re.sub(r"[^a-z0-9]+", "_", titulo.lower()).strip("_")[:50]
    return f"dou_{id_materia}_{base}.txt"


def processar_artigo_xml(conteudo_xml):
    """Recebe o conteudo de um arquivo XML e devolve um dict com os
    dados extraidos, ou None se a publicacao nao for relevante."""
    raiz = ET.fromstring(conteudo_xml)
    artigo = raiz.find("article")
    if artigo is None:
        return None

    art_category = artigo.get("artCategory", "")
    if not categoria_e_relevante(art_category):
        return None

    corpo = artigo.find("body")
    if corpo is None:
        return None

    identifica = extrair_texto_cdata(corpo, "Identifica")
    ementa = extrair_texto_cdata(corpo, "Ementa")
    texto_html = extrair_texto_cdata(corpo, "Texto")
    texto_limpo = limpar_html(texto_html)

    titulo = identifica or artigo.get("name", "documento_sem_titulo")

    return {
        "id_materia": artigo.get("idMateria", "sem_id"),
        "titulo": titulo,
        "tipo_documento": artigo.get("artType", "Publicacao DOU"),
        "categoria": art_category,
        "data_publicacao": artigo.get("pubDate", ""),
        "secao": artigo.get("pubName", ""),
        "url_original": artigo.get("pdfPage", ""),
        "ementa": ementa,
        "texto": texto_limpo,
    }


def salvar_documento(dados):
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    nome_arquivo = nome_arquivo_seguro(dados["titulo"], dados["id_materia"])
    caminho = os.path.join(PASTA_SAIDA, nome_arquivo)

    conteudo = (
        f"FONTE: DOU\n"
        f"TIPO_DOCUMENTO: {dados['tipo_documento']}\n"
        f"TITULO: {dados['titulo']}\n"
        f"DATA_PUBLICACAO: {dados['data_publicacao']}\n"
        f"URL_ORIGINAL: {dados['url_original']}\n"
        f"TEMA: dou,{dados['secao']}\n"
        f"CATEGORIA_ORIGEM: {dados['categoria']}\n"
        f"\n"
        f"TEXTO_COMPLETO:\n"
        f"EMENTA: {dados['ementa']}\n\n"
        f"{dados['texto']}\n"
    )

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)

    return caminho


def main():
    if len(sys.argv) < 2:
        print("Uso: python src/processar_zip_dou.py caminho/para/o/arquivo.zip")
        sys.exit(1)

    caminho_zip = sys.argv[1]
    total_processados = 0
    total_relevantes = 0
    contagem_por_categoria = {}
    titulos_por_categoria = {}

    with zipfile.ZipFile(caminho_zip) as zip_arquivo:
        arquivos_xml = [nome for nome in zip_arquivo.namelist() if nome.lower().endswith(".xml")]
        print(f"{len(arquivos_xml)} arquivos XML encontrados no ZIP.")

        for nome_arquivo in arquivos_xml:
            total_processados += 1
            try:
                with zip_arquivo.open(nome_arquivo) as f:
                    conteudo_xml = f.read()

                dados = processar_artigo_xml(conteudo_xml)
                if dados:
                    salvar_documento(dados)
                    total_relevantes += 1

                    categoria = dados["categoria"]
                    contagem_por_categoria[categoria] = contagem_por_categoria.get(categoria, 0) + 1
                    titulos_por_categoria.setdefault(categoria, []).append(dados["titulo"])

            except ET.ParseError as erro:
                print(f"  Aviso: erro ao ler XML {nome_arquivo}: {erro}")

    print()
    print(f"Total de arquivos processados: {total_processados}")
    print(f"Total de publicacoes relevantes salvas: {total_relevantes}")
    print()
    print("Resumo por categoria (artCategory), do mais frequente ao menos frequente:")
    for categoria, contagem in sorted(contagem_por_categoria.items(), key=lambda x: -x[1]):
        print(f"\n  [{contagem} publicacoes] {categoria}")
        for titulo_exemplo in titulos_por_categoria[categoria][:3]:
            print(f"      - {titulo_exemplo[:90]}")


if __name__ == "__main__":
    main()
