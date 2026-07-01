# Grant Intelligence

An agentic RAG system for exploring NSF and NIH federal grant award data. Researchers submit natural-language questions; a LangGraph agent classifies each query, routes it to the right retrieval path (semantic chunk search or Neo4j graph traversal), and synthesizes a grounded, citeable answer.

Built as both a practical research tool and a portfolio demonstration of production-grade AI engineering.

---

## Architecture

```
User query
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  LangGraph Agent  (retrieval/agent.py)              │
│                                                     │
│  1. classify_query  ──► Gemini 2.5 Flash Lite       │
│          │                                          │
│    ┌─────┴──────┐                                   │
│    ▼            ▼            ▼                      │
│  chunk       graph          none                    │
│    │            │             │                     │
│  Dense +     Neo4j         Skip                     │
│  BM25 →     Cypher         retrieval                │
│  RRF →      queries                                 │
│  Rerank                                             │
│    └────────────┴─────────────┘                     │
│                 │                                   │
│          invoke_llm  ──► Claude Sonnet (synthesis)  │
└─────────────────────────────────────────────────────┘
```

**Three retrieval paths, selected per query:**

- **chunk** — dense (BGE-M3 via HuggingFace Inference API) + sparse (BM25) retrieval, fused with RRF, reranked by `cross-encoder/ms-marco-MiniLM-L-6-v2`. Used for questions about abstract content, PI depth, framing, or award specifics.
- **graph** — LLM-generated Cypher queries over a Neo4j knowledge graph. Used for landscape analysis, funding trends, collaboration networks, and structural/aggregation questions.
- **none** — passes the conversation history directly to the synthesis LLM. Used for general knowledge questions or queries the history already answers.

---

## Stack

| Layer        | Technology                                |
| ------------ | ----------------------------------------- |
| Frontend     | React 19 + Vite (deployed on Vercel)      |
| API          | FastAPI + Uvicorn (GCP Cloud Run)         |
| Task queue   | Celery (GCP e2-micro VM via systemd)      |
| Broker       | Upstash Redis                             |
| Vector store | Pinecone (1024-dim cosine, BGE-M3)        |
| Chunk store  | Supabase (PostgreSQL via psycopg2)        |
| Graph DB     | Neo4j AuraDB                              |
| Embeddings   | BAAI/bge-m3 via HuggingFace Inference API |
| Classifier   | Google Gemini 2.5 Flash Lite              |
| Synthesis    | Anthropic Claude Sonnet                   |
| Reranker     | cross-encoder/ms-marco-MiniLM-L-6-v2      |

---

## Repository Layout

```
grant-agent/
├── api/
│   ├── api.py          # FastAPI app, lifespan, all endpoints
│   └── schemas.py      # Pydantic models for request/response
├── ingestion/
│   ├── celery_app.py   # Celery app + broker config
│   ├── injest.py       # Celery task: fetch → tag → chunk → embed → graph
│   ├── fetch_grants.py # NSF API + NIH Reporter API clients
│   ├── normalize.py    # Unified award schema (NSF + NIH → common dict)
│   ├── chunk.py        # BGE-M3-aware token chunking with metadata headers
│   ├── supabase.py     # Chunk persistence, BM25 index builder, dedup check
│   ├── pinecone_db.py  # Pinecone connection, embed via HF API, upsert/query
│   └── write_to_graph.py # Neo4j MERGE writes for all node/relationship types
├── retrieval/
│   ├── agent.py        # LangGraph graph: state, nodes, routing, compilation
│   ├── retrieve.py     # Chunk retrieval (RRF + cross-encoder) + graph helpers
│   └── system_msg.py   # All LLM prompts (classifier, synthesis, Cypher gen)
├── site/               # React frontend (Vite)
│   └── src/
│       ├── App.jsx         # Main chat UI, session persistence
│       ├── IngestPanel.jsx # Domain ingestion form + polling UI
│       ├── SourcesCard.jsx # Source citation display
│       └── api.js          # Frontend API client
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

---

## Neo4j Graph Schema

```
(:Domain {name})-[:CONTAINS]->(:Award {award_id, title, abstract, amount, year, agency, ...})
(:PI {name})-[:RECEIVED]->(:Award)
(:PI {name})-[:CO_RECEIVED]->(:Award)
(:PI)-[:AFFILIATED_WITH]->(:Institution)
(:Award)-[:HOSTED_AT]->(:Institution {name, state})
(:Award)-[:FUNDED_BY]->(:Directorate {name, agency})
(:Award)-[:TAGGED_WITH]->(:Topic {label})       ← LLM-extracted
(:Award)-[:USES_METHOD]->(:Method {name})        ← LLM-extracted
```

Topics and methods are extracted by Gemini in batches during ingestion, then written as graph nodes — enabling structural queries like "which methods appear most in awards funded by CISE" without any text search.

---

## Ingestion Pipeline

The `/injest` endpoint accepts a `DomainRequest` and dispatches a Celery task asynchronously. Progress is polled via `/poll_injest?task_id=...`.

**Pipeline steps (run in worker):**

1. Fetch awards from NSF API and/or NIH Reporter API with keyword + date filters
2. Normalize both formats to a unified award schema
3. Batch-extract topics and methods via Gemini (5 awards per call, with rate-limit backoff)
4. Chunk each abstract with BGE-M3 token-aware splitter; prepend structured metadata header
5. Deduplicate against PostgreSQL before writing; skip already-ingested award IDs
6. Write chunks to Supabase + embed and upsert to Pinecone
7. Write all graph nodes and relationships to Neo4j AuraDB

**Deduplication** is handled by querying `chunks WHERE award_id = %s LIMIT 1` — no in-memory cache.

---

## Retrieval Detail

### Chunk path

```
query → dense_retrieval (Pinecone, top_dense=top_k×4)
      → sparse_retrieval (BM25Okapi, top_sparse=top_k×4)
      → RRF fusion (k=60) over all seen chunk IDs
      → cross-encoder reranking → top_k final chunks
```

BM25 indexes are built lazily per domain and cached in `app.state.bm25_indexes` for the lifetime of the process.

### Graph path

```
query → fuzzy fulltext search (Neo4j) → candidate entities per type
      → Gemini generates N Cypher queries (JSON array)
      → safety filter: rejects mutating keywords + unscoped queries
      → execute queries → format rows as plain text for synthesis
```

All generated Cypher must start from `(:Domain {name: "<domain>"})` — unscoped queries are rejected before execution.

---

## API Endpoints

| Method | Path                    | Description                                                     |
| ------ | ----------------------- | --------------------------------------------------------------- |
| `GET`  | `/`                     | Health check                                                    |
| `GET`  | `/domains`              | List ingested domain names                                      |
| `POST` | `/injest`               | Start ingestion task; returns `task_id`                         |
| `GET`  | `/poll_injest?task_id=` | Poll Celery task status + result                                |
| `POST` | `/query`                | Run agentic query; returns response + sources + updated history |

All connections (Neo4j, Pinecone, Supabase, BM25 cache) are initialized at startup via FastAPI `lifespan` and threaded through LangGraph nodes via `RunnableConfig`.
