# Copiloto Regulatório Inteligente

Protótipo desenvolvido para o Hackathon IA 2026 (COPPE/UFRJ), na ótica de uma
empresa transmissora de energia (ex.: TAESA). Combina um painel com as
publicações regulatórias mais recentes do setor elétrico brasileiro e um chat
que responde perguntas com base nesses documentos, sempre citando a fonte.

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
5. **Geração de resposta (RAG)**: expande a pergunta do usuário em variações
   com vocabulário técnico (via Gemini, já que a busca TF-IDF só entende
   correspondência literal de palavras), busca os chunks mais relevantes para
   todas as variações, e pede ao Gemini para responder citando o trecho
   numerado que sustenta cada afirmação — admitindo explicitamente quando a
   informação disponível não for suficiente.
6. **Interface (Streamlit)**: painel com as publicações mais recentes
   (filtrável por fonte) + chat com histórico e trechos citados.

## Stack

`requests` / `BeautifulSoup` / `Playwright` / `pdfplumber` para extração,
`pandas` para metadados, `scikit-learn` (TF-IDF) para busca, `streamlit` para
a interface, e a API gratuita do **Google Gemini** (`google-genai`) para
geração de resposta — sem custo, usando a camada gratuita do Google AI
Studio.

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

# 6. (opcional) Testa buscas manualmente pelo terminal
python src/testar_busca.py "sua pergunta aqui"

# 7. (opcional) Testa a geração de resposta com IA pelo terminal
python src/gerar_resposta.py "sua pergunta aqui"

# 8. Sobe a interface completa
streamlit run app/painel.py
```

Os passos 1–5 só precisam ser refeitos quando a base de documentos mudar.

## Estrutura

```
copiloto-regulatorio/
├── requirements.txt
├── data/
│   ├── raw/              # documentos brutos extraídos (texto + metadados no cabeçalho)
│   │   ├── ons/          # Procedimentos de Rede (ONS)
│   │   └── dou/          # publicações relevantes do DOU
│   └── processed/
│       ├── metadados_documentos.csv
│       ├── chunks.csv
│       └── indice_busca.pkl
├── src/
│   ├── utils_extracao.py           # funções compartilhadas de extração/scraping
│   ├── extrair_ons_procedimentos_rede.py
│   ├── processar_zip_dou.py
│   ├── extrair_metadados.py
│   ├── gerar_chunks.py
│   ├── construir_indice_busca.py
│   ├── utils_busca.py              # funções compartilhadas de busca (TF-IDF)
│   ├── testar_busca.py             # teste manual de busca pelo terminal
│   └── gerar_resposta.py           # RAG: expansão de consulta + resposta com citação
└── app/
    └── painel.py          # interface Streamlit (painel + chat)
```

## Limitações conhecidas

- **Busca por TF-IDF é literal**: não entende sinônimos nem temas abstratos
  (ex.: "transição energética" não aparece no texto dos documentos técnicos).
  Mitigado parcialmente pela expansão de consulta com IA no passo de geração
  de resposta, mas ainda pode falhar em perguntas muito genéricas.
- **ANEEL**: fonte pausada por ora — o site oficial tem proteção anti-bot, e
  a alternativa (lista manual de atos conhecidos) não foi priorizada.
- **MME, EPE, CCEE**: não implementadas nesta fase.
- **Atualização diária do DOU**: o download automatizado do `in.gov.br` é
  bloqueado por `robots.txt`; o fluxo atual depende de download manual do ZIP.
  Para produção, alternativas incluem BD Pro (Base dos Dados), APIs de
  terceiros pagas, ou contato direto com a Imprensa Nacional.

## Possíveis extensões futuras

- Busca semântica com embeddings, para superar a limitação de correspondência
  literal do TF-IDF.
- Reativar a fonte ANEEL (via lista manual de atos ou investigação do
  bloqueio anti-bot do site oficial).
- Extensão "Inteligência Competitiva": análise comparativa entre agentes do
  setor a partir dos mesmos documentos.
