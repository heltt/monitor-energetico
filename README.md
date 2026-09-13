# Copiloto Regulatório Inteligente — Protótipo

Protótipo mínimo de um copiloto regulatório para o setor elétrico brasileiro,
combinando dados da ANEEL e do ONS, com foco no ângulo de uma empresa de
transmissão (transição energética, conexão à rede, curtailment).

## Estrutura

- `data/raw/` — documentos brutos coletados (ANEEL e ONS), em texto estruturado
  com metadados no cabeçalho (fonte, tipo, data, tema, url original).
- `src/` — código do pipeline (extração, chunking, busca, geração de resposta).
- `app/` — dashboard e chatbot (Streamlit).

## Etapas do desenvolvimento

1. Extração e organização dos documentos (`data/raw/`) — em andamento
2. Chunking dos textos
3. Índice de busca (TF-IDF)
4. Geração de resposta com citação (LLM/RAG)
5. Dashboard + chat (Streamlit)

## Fontes utilizadas nesta fase

- ANEEL: Resoluções Normativas (Biblioteca Virtual)
- ONS: Procedimentos de Rede / FAQ de Curtailment

Cada arquivo em `data/raw/` contém metadados no cabeçalho no formato:
```
FONTE: ...
TIPO_DOCUMENTO: ...
NUMERO_ATO: ...
DATA_PUBLICACAO: ...
TEMA: ...
TITULO: ...

RESUMO_EXECUTIVO / TEXTO_COMPLETO: ...
```
