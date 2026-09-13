# Copiloto Regulatório Inteligente

Protótipo desenvolvido para o Hackathon IA 2026 (COPPE/UFRJ), na ótica de uma
empresa transmissora de energia (ex.: TAESA). Combina um painel com as
publicações regulatórias mais recentes do setor elétrico brasileiro, um grafo
de relações entre normas, e um chat que responde perguntas com base nesses
documentos, sempre citando a fonte — e resolvendo, na medida do possível, a
sobreposição entre versões de uma mesma norma.

Une os desafios "Copiloto Regulatório" (foco do MVP) e "Inteligência
Competitiva" (extensão futura) do hackathon.

## Como funciona

1. **Extração**: coleta documentos do ONS (Procedimentos de Rede, via
   Playwright) e do DOU (publicações filtradas por relevância ao setor
   elétrico, a partir de um ZIP baixado manualmente — o acesso automatizado ao
   `in.gov.br` é bloqueado por `robots.txt`).
2. **Metadados**: consolida todos os documentos brutos em uma única tabela
   (fonte, tipo, data, título, URL original, texto completo).
3. **Chunking**: corta os textos em pedaços menores, respeitando parágrafos
   quando possível.
4. **Índice de busca**: vetoriza os chunks com TF-IDF (scikit-learn) para
   busca por similaridade, sem depender de um modelo de embeddings externo.
5. **Wiki de normas do ONS**: os títulos dos submódulos do ONS trazem embutida
   uma chave de agrupamento (`número-SIGLA`, ex.: `2.10-RQ`) que identifica
   todas as revisões do MESMO assunto regulatório ao longo do tempo. Para
   submódulos com mais de uma versão conhecida, o Gemini gera uma página
   consolidada (resumo da versão vigente + histórico de revisões anteriores),
   resolvendo de antemão qual versão vale — em vez de deixar o modelo
   adivinhar isso na hora de responder, a partir de chunks concorrentes de
   versões diferentes.
6. **Grafo temporal de normas**: modela relações ENTRE normas diferentes (não
   só revisões do mesmo submódulo), considerando TODAS as fontes. Duas
   relações são extraídas por regex, sem gastar nenhuma chamada de IA:
   `sucede` (entre versões do mesmo submódulo do ONS) e `cita` (quando um
   documento menciona outra norma por número — Resolução, Lei, Decreto,
   Portaria, Submódulo). Isso permite perguntas estruturais que a wiki não
   responde ("quais normas citam a Resolução X") e enriquece o chat com
   normas relacionadas, mesmo que a busca por palavra-chave não as tenha
   recuperado diretamente.
7. **Geração de resposta (RAG)**: expande a pergunta do usuário em variações
   com vocabulário técnico (via Gemini, já que a busca TF-IDF só entende
   correspondência literal de palavras), busca os chunks mais relevantes para
   todas as variações, troca chunks de submódulos com página na wiki pela
   versão consolidada, acrescenta contexto do grafo de normas relacionadas, e
   pede ao Gemini para responder citando o trecho numerado que sustenta cada
   afirmação — admitindo explicitamente quando a informação disponível não
   for suficiente.
8. **Interface (Streamlit)**: painel com as publicações mais recentes
   (filtrável por fonte, com gráfico de publicações por mês), uma aba de
   grafo de normas (normas mais citadas + explorador de vizinhança), e chat
   com histórico e trechos citados.

## Stack

`requests` / `BeautifulSoup` / `Playwright` / `pdfplumber` para extração,
`pandas` para metadados, `scikit-learn` (TF-IDF) para busca, `streamlit` +
`altair` para a interface, e a API gratuita do **Google Gemini**
(`google-genai`) para expansão de consulta, construção da wiki e geração de
resposta — sem custo, usando a camada gratuita do Google AI Studio. O grafo
de normas usa só `pandas` + expressões regulares (nenhuma chamada de IA).

**Nota sobre LLM local:** consideramos rodar um LLM local (via Ollama) para a
construção da wiki, especificamente para não gastar cota da camada gratuita
do Gemini. Na prática, um modelo de 8B rodando só em CPU (sem GPU dedicada
boa) levava ~10 minutos por página — inviável para o volume de submódulos do
ONS. Voltamos a usar o Gemini também nessa etapa, com uma pequena pausa entre
chamadas. Fica como nota para quem for reproduzir isso com hardware mais
forte (GPU dedicada com VRAM suficiente tornaria essa abordagem viável).

**Nota sobre nomes de modelo do Gemini:** nomes de modelo com número de
versão fixo (ex.: `gemini-3.6-flash`) podem ficar indisponíveis para novos
usuários ou ter cotas gratuitas diárias muito baixas (encontramos um caso de
apenas 20 requisições/dia) sem aviso prévio. Preferimos usar aliases como
`gemini-flash-lite-latest`, que sempre apontam para a versão Flash-Lite mais
atual disponível — mais estável e com cota gratuita mais generosa. Se algo
parar de funcionar, confira o nome de modelo atual em
https://aistudio.google.com/ e ajuste via a variável de ambiente
`GEMINI_MODEL`.

## Configuração

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Gere uma chave gratuita em https://aistudio.google.com/apikey e configure:
```bash
export GEMINI_API_KEY="sua-chave-aqui"
```

## Rodando o pipeline (em ordem)

```bash
# 1. Extrai os Procedimentos de Rede do ONS
python src/extrair_ons_procedimentos_rede.py

# 2. Processa um ZIP de publicações do DOU (baixado manualmente em
#    in.gov.br/dados-abertos/base-de-dados/publicacoes-do-dou)
python src/processar_zip_dou.py caminho/para/o/arquivo.zip

# 3. Consolida tudo em uma tabela de metadados
python src/extrair_metadados.py

# 4. Corta os documentos em chunks
python src/gerar_chunks.py

# 5. Constrói o índice de busca TF-IDF
python src/construir_indice_busca.py

# 6. Constrói a wiki de normas do ONS (submódulos com múltiplas versões)
python src/construir_wiki_ons.py

# 7. Constrói o grafo temporal de normas (citação + sucessão, todas as fontes)
python src/construir_grafo_normas.py

# 8. (opcional) Testa buscas manualmente pelo terminal
python src/testar_busca.py "sua pergunta aqui"

# 9. (opcional) Testa a geração de resposta com IA pelo terminal
python src/gerar_resposta.py "sua pergunta aqui"

# 10. Sobe a interface completa
streamlit run app/painel.py
```

Os passos 1–7 só precisam ser refeitos quando a base de documentos mudar.

## Estrutura

```
copiloto-regulatorio/
├── requirements.txt
├── data/
│   ├── raw/              # documentos brutos extraídos (texto + metadados no cabeçalho)
│   │   ├── ons/          # Procedimentos de Rede (ONS)
│   │   └── dou/          # publicações relevantes do DOU
│   ├── processed/
│   │   ├── metadados_documentos.csv
│   │   ├── chunks.csv
│   │   └── indice_busca.pkl
│   ├── wiki/
│   │   └── ons/          # páginas consolidadas por submódulo (numero-SIGLA.md)
│   └── grafo/
│       ├── nos.csv        # um no por documento + referencias externas citadas
│       └── arestas.csv    # origem_id, destino_id, tipo_relacao (cita/sucede), data
├── src/
│   ├── utils_extracao.py           # funções compartilhadas de extração/scraping
│   ├── extrair_ons_procedimentos_rede.py
│   ├── processar_zip_dou.py
│   ├── extrair_metadados.py
│   ├── gerar_chunks.py
│   ├── construir_indice_busca.py
│   ├── utils_busca.py              # funções compartilhadas de busca (TF-IDF)
│   ├── utils_normas_ons.py         # parsing de titulos do ONS (ano/mes, numero-SIGLA)
│   ├── construir_wiki_ons.py       # gera as páginas consolidadas por submódulo
│   ├── construir_grafo_normas.py   # gera o grafo de citacao/sucessao (todas as fontes)
│   ├── utils_grafo.py              # funções compartilhadas de consulta ao grafo
│   ├── testar_busca.py             # teste manual de busca pelo terminal
│   └── gerar_resposta.py           # RAG: expansão + wiki + grafo + resposta com citação
└── app/
    └── painel.py          # interface Streamlit (painel + gráfico mensal + grafo + chat)
```

## Limitações conhecidas

- **Busca por TF-IDF é literal**: não entende sinônimos nem temas abstratos
  (ex.: "transição energética" não aparece no texto dos documentos técnicos).
  Mitigado parcialmente pela expansão de consulta com IA, mas perguntas muito
  genéricas ainda podem trazer chunks pouco relevantes no ranking final.
- **Wiki cobre só o ONS por enquanto**: o DOU não tem uma numeração de
  submódulo equivalente para agrupar revisões da mesma forma.
- **Grafo só extrai `cita` e `sucede`**: relações mais sofisticadas -- uma
  norma REVOGAR ou ALTERAR outra, não só citá-la -- exigiriam um LLM lendo os
  dois textos para confirmar a relação; não implementado ainda.
- **Citações a "Submódulo N" sem sufixo são ambíguas**: quando um documento
  cita "Submódulo 2.11" sem indicar o tipo (RQ, PR, OP...), o grafo cria uma
  referência genérica àquele número, sem apontar para uma versão específica.
- **ANEEL**: fonte pausada por ora — o site oficial tem proteção anti-bot, e
  a alternativa (lista manual de atos conhecidos) não foi priorizada. Isso
  significa que a maioria das citações a Resoluções ANEEL no grafo aparecem
  como "referência externa" (sem texto completo) por enquanto.
- **MME, EPE, CCEE**: não implementadas nesta fase.
- **Atualização diária do DOU**: o download automatizado do `in.gov.br` é
  bloqueado por `robots.txt`; o fluxo atual depende de download manual do ZIP.
  Para produção, alternativas incluem BD Pro (Base dos Dados), APIs de
  terceiros pagas, ou contato direto com a Imprensa Nacional.

## Possíveis extensões futuras

- Busca semântica com embeddings, para superar a limitação de correspondência
  literal do TF-IDF.
- Usar um LLM para classificar arestas `cita` do grafo em relações mais
  específicas (`altera`, `revoga`, `regulamenta`), a partir da leitura dos
  dois textos envolvidos.
- Reativar a fonte ANEEL (via lista manual de atos ou investigação do
  bloqueio anti-bot do site oficial) -- resolveria automaticamente boa parte
  das referências externas já mapeadas no grafo.
- Visualização interativa do grafo (não só listas/gráfico de barras) para a
  demo do hackathon.
- Extensão "Inteligência Competitiva": análise comparativa entre agentes do
  setor a partir dos mesmos documentos.
