"""
Passo 5 do pipeline: geracao de resposta com citacao de fonte (RAG),
usando a API gratuita do Google Gemini.

Fluxo:
1. Recebe a pergunta do usuario.
2. Pede ao Gemini para expandir a pergunta em algumas buscas alternativas,
   usando vocabulario tecnico/regulatorio mais provavel de aparecer no
   texto literal dos documentos (necessario porque a busca por TF-IDF,
   usada no passo 3, so entende correspondencia literal de palavras, nao
   sinonimos ou termos tematicos abstratos como "transicao energetica").
3. Busca os chunks mais relevantes no indice TF-IDF para a pergunta
   original E para cada busca alternativa, juntando e removendo
   duplicatas.
4. Para chunks do ONS cujo submodulo tem uma pagina consolidada na
   wiki (gerada por construir_wiki_ons.py, para submodulos com mais
   de uma versao conhecida), troca o chunk bruto pela pagina -- que
   ja aponta a versao vigente e o historico de revisoes, em vez de
   deixar o Gemini adivinhar qual versao, entre varias concorrentes,
   e a valida.
5. Monta um prompt para o Gemini contendo esses chunks/paginas, cada
   um numerado e identificado pela fonte/titulo/data.
6. Pede ao modelo para responder SOMENTE com base nesses chunks,
   citando de qual trecho numerado veio cada afirmacao, e avisando
   quando a informacao fornecida nao for suficiente.

Uso:
    python src/gerar_resposta.py "sua pergunta aqui"

Requer a variavel de ambiente GEMINI_API_KEY configurada (chave
gratuita, gerada em https://aistudio.google.com/apikey).
"""

import os
import re
import sys

from google import genai
from google.genai import types

from utils_busca import carregar_indice, buscar
from utils_normas_ons import extrair_modulo_sufixo_do_titulo

PASTA_WIKI_ONS = os.path.join("data", "wiki", "ons")

NUMERO_CHUNKS_POR_CONSULTA = 4
NUMERO_CHUNKS_CONTEXTO = 6
# Modelo da camada gratuita do Google AI Studio. Se este nome de modelo
# parar de funcionar (a lista de modelos gratuitos muda com o tempo),
# confira o nome atual em https://aistudio.google.com/ e ajuste aqui
# ou via a variavel de ambiente GEMINI_MODEL. Usado tanto na expansao
# da pergunta quanto na resposta final.
MODELO = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")

PROMPT_EXPANSAO = """Voce ajuda um sistema de busca por palavras-chave (TF-IDF, \
sem entendimento de sinonimos ou significado) a encontrar documentos \
regulatorios do setor eletrico brasileiro (ONS, ANEEL, DOU).

Dada a pergunta de um usuario, gere de 3 a 4 buscas alternativas, curtas, \
usando termos tecnicos e regulatorios especificos que provavelmente aparecem \
no TEXTO LITERAL dos documentos. Evite termos genericos ou tematicos \
abstratos (como "transicao energetica" ou "sustentabilidade"); prefira \
nomes tecnicos concretos (exemplos: "geracao eolica e fotovoltaica", \
"fontes renovaveis variaveis", "curtailment", "geracao distribuida", \
"armazenamento de energia", "conexao ao sistema de transmissao"), \
adaptados ao assunto da pergunta.

Responda APENAS com uma busca por linha, sem numeracao e sem explicacao.
"""

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
4. A pergunta pode usar termos tematicos amplos (ex.: "transicao \
energetica") que nao aparecem literalmente nos documentos, que costumam \
usar vocabulario tecnico especifico. Reconheca essa relacao: trechos \
sobre geracao eolica e fotovoltaica, armazenamento de energia, \
curtailment, geracao distribuida ou conexao de fontes renovaveis SAO \
exemplos concretos do tema perguntado, mesmo sem a expressao exata. So \
diga que falta informacao se os trechos realmente nao tratarem, nem \
tecnicamente, do assunto perguntado.
"""


def expandir_pergunta(pergunta, cliente):
    """Pede ao Gemini buscas alternativas com vocabulario mais tecnico.
    Se a chamada falhar por qualquer motivo, degrada graciosamente
    devolvendo uma lista vazia (a busca segue usando so a pergunta
    original) -- mas avisa no terminal, para o problema nao passar
    despercebido."""
    try:
        resposta = cliente.models.generate_content(
            model=MODELO,
            config=types.GenerateContentConfig(system_instruction=PROMPT_EXPANSAO),
            contents=pergunta,
        )
        linhas = [linha.strip("-• \t") for linha in resposta.text.splitlines()]
        return [linha for linha in linhas if linha]
    except Exception as erro:
        print(f"[aviso] Falha ao expandir a pergunta ({erro}). Usando so a pergunta original.", file=sys.stderr)
        return []


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


def buscar_chunks_com_expansao(pergunta, indice, cliente):
    """Busca chunks para a pergunta original e para variacoes tecnicas
    geradas pelo Gemini, juntando os resultados e removendo duplicatas
    (mantendo, para cada chunk, o maior score obtido entre as buscas)."""
    consultas_expandidas = expandir_pergunta(pergunta, cliente)
    consultas = [pergunta] + consultas_expandidas

    chunks_por_id = {}
    for consulta in consultas:
        for chunk in buscar(consulta, indice, top_n=NUMERO_CHUNKS_POR_CONSULTA):
            chunk_id = chunk["chunk_id"]
            if chunk_id not in chunks_por_id or chunk["score"] > chunks_por_id[chunk_id]["score"]:
                chunks_por_id[chunk_id] = chunk

    chunks_relevantes = sorted(chunks_por_id.values(), key=lambda c: c["score"], reverse=True)
    return chunks_relevantes[:NUMERO_CHUNKS_CONTEXTO], consultas_expandidas


def carregar_pagina_wiki(grupo):
    """Le a pagina da wiki de um submodulo do ONS (numero-SIGLA), se ela
    existir. Devolve None se nao houver pagina gerada para esse grupo
    (ex.: submodulos com uma unica versao conhecida nao tem pagina --
    ver construir_wiki_ons.py)."""
    nome_arquivo = re.sub(r"[^a-zA-Z0-9_.-]", "_", grupo) + ".md"
    caminho = os.path.join(PASTA_WIKI_ONS, nome_arquivo)
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def substituir_por_paginas_wiki(chunks_relevantes):
    """Para chunks do ONS cujo submodulo tem multiplas versoes (e,
    portanto, uma pagina consolidada na wiki), troca o chunk bruto pelo
    conteudo da pagina -- que ja aponta a versao vigente e o historico
    de revisoes, em vez de deixar o Gemini adivinhar qual versao, entre
    varios chunks concorrentes, e a que vale.

    Se dois chunks recuperados pertencerem ao mesmo submodulo, a pagina
    da wiki entra so uma vez (nao faz sentido repetir a mesma pagina
    duas vezes no prompt)."""
    resultado = []
    grupos_ja_incluidos = set()

    for chunk in chunks_relevantes:
        if chunk["fonte"] != "ONS":
            resultado.append(chunk)
            continue

        grupo = extrair_modulo_sufixo_do_titulo(chunk["titulo"])
        pagina = carregar_pagina_wiki(grupo) if grupo else None

        if pagina is None:
            resultado.append(chunk)
            continue

        if grupo in grupos_ja_incluidos:
            continue

        grupos_ja_incluidos.add(grupo)
        chunk_wiki = dict(chunk)
        chunk_wiki["texto_chunk"] = pagina
        chunk_wiki["titulo"] = f"{chunk['titulo']} (pagina consolidada da wiki -- submodulo {grupo})"
        resultado.append(chunk_wiki)

    return resultado


def gerar_resposta(pergunta, indice, cliente):
    chunks_relevantes, consultas_expandidas = buscar_chunks_com_expansao(pergunta, indice, cliente)
    chunks_relevantes = substituir_por_paginas_wiki(chunks_relevantes)

    resposta = cliente.models.generate_content(
        model=MODELO,
        config=types.GenerateContentConfig(system_instruction=PROMPT_SISTEMA),
        contents=montar_prompt_usuario(pergunta, chunks_relevantes),
    )

    return resposta.text, chunks_relevantes, consultas_expandidas


def main():
    if len(sys.argv) < 2:
        print('Uso: python src/gerar_resposta.py "sua pergunta aqui"')
        sys.exit(1)

    pergunta = sys.argv[1]
    indice = carregar_indice()
    cliente = genai.Client()  # le GEMINI_API_KEY (ou GOOGLE_API_KEY) do ambiente

    resposta, chunks_relevantes, consultas_expandidas = gerar_resposta(pergunta, indice, cliente)

    print(f'Pergunta: "{pergunta}"')
    if consultas_expandidas:
        print("Buscas alternativas usadas:")
        for consulta in consultas_expandidas:
            print(f"  - {consulta}")
    print()
    print("Resposta:")
    print(resposta)
    print()
    print("Trechos usados no contexto:")
    for i, chunk in enumerate(chunks_relevantes, start=1):
        print(f"  [Trecho {i}] {chunk['fonte']} - {chunk['titulo']} - {chunk['url_original']}")


if __name__ == "__main__":
    main()
