"""
Script de teste para o indice de busca (data/processed/indice_busca.pkl).

Uso:
    python src/testar_busca.py "sua pergunta aqui"
"""

import sys

from utils_busca import carregar_indice, buscar

NUMERO_RESULTADOS = 5


def main():
    if len(sys.argv) < 2:
        print('Uso: python src/testar_busca.py "sua pergunta aqui"')
        sys.exit(1)

    pergunta = sys.argv[1]
    indice = carregar_indice()
    resultados = buscar(pergunta, indice, top_n=NUMERO_RESULTADOS)

    print(f'Pergunta: "{pergunta}"')
    print(f"Chunks indexados: {indice['matriz_tfidf'].shape[0]}")
    print()

    for posicao, resultado in enumerate(resultados, start=1):
        print(f"--- Resultado {posicao} (score={resultado['score']:.3f}) ---")
        print(f"Fonte: {resultado['fonte']} | Titulo: {resultado['titulo']}")
        print(f"Data: {resultado['data_publicacao']} | URL: {resultado['url_original']}")
        print(f"Trecho: {resultado['texto_chunk'][:300]}...")
        print()


if __name__ == "__main__":
    main()
