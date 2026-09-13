"""
Passo 5 do pipeline: geracao de resposta com citacao de fonte (RAG),
usando a API gratuita do Google Gemini.

Fluxo:
1. Recebe a pergunta do usuario.
2. Busca os chunks mais relevantes no indice TF-IDF (utils_busca.buscar).
3. Monta um prompt para o Gemini contendo esses chunks, cada um
   numerado e identificado pela fonte/titulo/data.
4. Pede ao modelo para responder SOMENTE com base nesses chunks,
   citando de qual trecho numerado veio cada afirmacao, e avisando
   quando a informacao fornecida nao for suficiente.

Uso:
    python src/gerar_resposta.py "sua pergunta aqui"

Requer a variavel de ambiente GEMINI_API_KEY configurada (chave
gratuita, gerada em https://aistudio.google.com/apikey).
"""

import os
import sys

from google import genai
from google.genai import types

from utils_busca import carregar_indice, buscar

NUMERO_CHUNKS_CONTEXTO = 6
# Modelo da camada gratuita do Google AI Studio. Se este nome de modelo
# parar de funcionar (a lista de modelos gratuitos muda com o tempo),
# confira o nome atual em https://aistudio.google.com/ e ajuste aqui
# ou via a variavel de ambiente GEMINI_MODEL.
MODELO = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

PROMPT_SISTEMA = """Voce e um copiloto regulatorio para o setor eletrico \
brasileiro, usado por uma empresa transmissora de energia. Sua funcao e \
responder perguntas sobre regulacao do setor eletrico (ONS, ANEEL, DOU e \
orgaos relacionados) usando EXCLUSIVAMENTE os trechos de documentos \
fornecidos abaixo, sem completar com conhecimento proprio sobre o assunto.

Regras obrigatorias:
1. Toda afirmacao factual da resposta deve vir acompanhada da referencia \
ao trecho numerado que a sustenta, no formato [Trecho N].
2. Se os trechos fornecidos nao contiverem informacao suficiente para \
responder com confianca, diga isso explicitamente em vez de completar a \
resposta com suposicoes.
3. Seja direto e objetivo. Nao repita o texto dos trechos na integra; \
sintetize com suas proprias palavras.
"""


def montar_prompt_usuario(pergunta, chunks_relevantes):
    blocos = []
    for i, chunk in enumerate(chunks_relevantes, start=1):
        cabecalho = f"[Trecho {i}] Fonte: {chunk['fonte']}"
        if chunk["titulo"]:
            cabecalho += f" | {chunk['titulo']}"
        if chunk["data_publicacao"]:
            cabecalho += f" | Data: {chunk['data_publicacao']}"
        blocos.append(f"{cabecalho}\n{chunk['texto_chunk']}")

    contexto = "\n\n".join(blocos)

    return f"Trechos de documentos disponiveis:\n\n{contexto}\n\nPergunta: {pergunta}"


def gerar_resposta(pergunta, indice, cliente):
    chunks_relevantes = buscar(pergunta, indice, top_n=NUMERO_CHUNKS_CONTEXTO)

    resposta = cliente.models.generate_content(
        model=MODELO,
        config=types.GenerateContentConfig(system_instruction=PROMPT_SISTEMA),
        contents=montar_prompt_usuario(pergunta, chunks_relevantes),
    )

    return resposta.text, chunks_relevantes


def main():
    if len(sys.argv) < 2:
        print('Uso: python src/gerar_resposta.py "sua pergunta aqui"')
        sys.exit(1)

    pergunta = sys.argv[1]
    indice = carregar_indice()
    cliente = genai.Client()  # le GEMINI_API_KEY (ou GOOGLE_API_KEY) do ambiente

    resposta, chunks_relevantes = gerar_resposta(pergunta, indice, cliente)

    print(f'Pergunta: "{pergunta}"')
    print()
    print("Resposta:")
    print(resposta)
    print()
    print("Trechos usados no contexto:")
    for i, chunk in enumerate(chunks_relevantes, start=1):
        print(f"  [Trecho {i}] {chunk['fonte']} - {chunk['titulo']} - {chunk['url_original']}")


if __name__ == "__main__":
    main()
