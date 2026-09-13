"""
Script de RECONHECIMENTO (nao e o processamento final) do ZIP mensal
do DOU baixado de in.gov.br/dados-abertos.

Como o arquivo e grande (centenas de MB) e pode conter dezenas de
milhares de arquivos, este script NAO extrai tudo -- ele so lista a
estrutura interna do ZIP (nomes de arquivo/pastas) e mostra o
conteudo de um ou dois arquivos de exemplo, para a gente entender o
formato antes de escrever o processamento completo.

Uso:
    python src/inspecionar_zip_dou.py caminho/para/o/arquivo.zip
"""

import sys
import zipfile
from collections import Counter


def main():
    if len(sys.argv) < 2:
        print("Uso: python src/inspecionar_zip_dou.py caminho/para/o/arquivo.zip")
        sys.exit(1)

    caminho_zip = sys.argv[1]

    with zipfile.ZipFile(caminho_zip) as zip_arquivo:
        lista_nomes = zip_arquivo.namelist()
        print(f"Total de itens no ZIP: {len(lista_nomes)}")
        print()

        print("Primeiros 20 itens (para ver o padrao de nomes/pastas):")
        for nome in lista_nomes[:20]:
            print(f"  {nome}")
        print()

        # Conta quantos itens existem por "pasta de primeiro nivel"
        # (ajuda a entender se e organizado por data, por secao, etc.)
        pastas_nivel_1 = Counter(nome.split("/")[0] for nome in lista_nomes if "/" in nome)
        print("Pastas de primeiro nivel encontradas (contagem de itens):")
        for pasta, contagem in pastas_nivel_1.most_common(20):
            print(f"  {pasta}: {contagem} itens")
        print()

        # Procura arquivos que parecam ser indice/sumario/metadados
        candidatos_indice = [
            nome for nome in lista_nomes
            if any(palavra in nome.lower() for palavra in ["indice", "sumario", "index", "manifest", ".json"])
        ]
        print(f"Possiveis arquivos de indice/metadados encontrados: {len(candidatos_indice)}")
        for nome in candidatos_indice[:10]:
            print(f"  {nome}")
        print()

        # Mostra o conteudo de um arquivo XML de exemplo (o primeiro que achar)
        arquivos_xml = [nome for nome in lista_nomes if nome.lower().endswith(".xml")]
        if arquivos_xml:
            exemplo = arquivos_xml[0]
            print(f"Conteudo de exemplo do primeiro .xml encontrado ({exemplo}):")
            print("-" * 80)
            with zip_arquivo.open(exemplo) as f:
                conteudo = f.read().decode("utf-8", errors="replace")
                print(conteudo[:3000])
            print("-" * 80)
        else:
            print("Nenhum arquivo .xml encontrado diretamente (pode estar em subpastas com outra extensao).")


if __name__ == "__main__":
    main()
