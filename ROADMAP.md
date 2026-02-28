# Sovereign AI Hub — Full Technical Roadmap

## Product: Air-Gapped, Locally-Run AI Platform for Government & Enterprise

**Version**: 1.0 Draft
**Date**: 2026-02-28
**Codename**: Sovereign AI Hub (working title)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Value Proposition](#2-core-value-proposition)
3. [Technology Stack](#3-technology-stack)
4. [System Architecture](#4-system-architecture)
5. [Phase 0 — Foundation & Infrastructure](#5-phase-0--foundation--infrastructure-weeks-13)
6. [Phase 1 — Chat & Reasoning Engine](#6-phase-1--chat--reasoning-engine-weeks-36)
7. [Phase 2 — RAG & Knowledge Base](#7-phase-2--rag--knowledge-base-weeks-610)
8. [Phase 3 — Agentic Runtime](#8-phase-3--agentic-runtime-weeks-1016)
9. [Phase 4 — Multimodal Capabilities](#9-phase-4--multimodal-capabilities-weeks-1620)
10. [Phase 5 — Code Assistant](#10-phase-5--code-assistant-weeks-2024)
11. [Phase 6 — Security, Compliance & Governance](#11-phase-6--security-compliance--governance-weeks-2428)
12. [Phase 7 — Fine-Tuning & Model Management](#12-phase-7--fine-tuning--model-management-weeks-2832)
13. [Phase 8 — Edge Deployment](#13-phase-8--edge-deployment-weeks-3236)
14. [Deployment Strategy](#14-deployment-strategy)
15. [Model Selection Guide](#15-model-selection-guide)
16. [Risk Register](#16-risk-register)
17. [Government Sales Positioning](#17-government-sales-positioning)

---

## 1. Executive Summary

This roadmap defines the architecture and phased build plan for a fully local, air-gap-capable AI platform that delivers modern AI capabilities — chat, RAG, agentic tool use, multimodal processing, code generation — without any data leaving the deployment environment.

The platform is designed to be pitched to government agencies (DoD, IC, federal civilian) and regulated enterprises (healthcare, finance, legal) where data sovereignty is non-negotiable.

Every component runs on-premise. No API calls leave the network. Every action is auditable. Models are open-weight and swappable.

---

## 2. Core Value Proposition

| Buyer Concern | Our Answer |
|---|---|
| "Will our data leak?" | Zero external API calls. Verifiable via network audit. Full air-gap support. |
| "Are we locked into a vendor?" | Open-weight models, standard APIs, MIT/Apache licensed stack. Swap any component. |
| "Can we audit it?" | Full prompt/response audit log. Agent action trails. SBOM for every dependency. |
| "Does it scale?" | Same codebase from laptop to datacenter. vLLM horizontal scaling with GPU clusters. |
| "Is it compliant?" | NIST 800-53 control mapping. FedRAMP alignment. FIPS 140-2 encryption support. |
| "Can it actually do things?" | Full agentic runtime: tool calling, code execution, file ops, API integration, multi-step planning. |

---

## 3. Technology Stack

### 3.1 Final Stack Decisions

| Layer | Technology | License | Rationale |
|---|---|---|---|
| **LLM Serving (Production)** | vLLM | Apache 2.0 | PagedAttention, continuous batching, OpenAI-compatible API, 5-10x throughput vs naive serving |
| **LLM Serving (Laptop/Edge)** | llama.cpp | MIT | GGUF quantized models, CPU/GPU/Metal support, minimal dependencies |
| **Agent Runtime** | Custom (IronClaw-inspired) | — | Rust core for security-critical paths, MCP protocol, container isolation, TEE-ready |
| **Agent Orchestration** | LangGraph | MIT | Graph-based workflows, conditional routing, persistent state, auditable execution paths |
| **Frontend** | Next.js 15 (App Router) | MIT | SSR, streaming, TypeScript, component ecosystem |
| **API Gateway** | FastAPI (Python) | MIT | OpenAI-compatible endpoints, async, automatic OpenAPI docs |
| **Database** | PostgreSQL 16 | PostgreSQL License | Conversations, users, audit logs, agent state, JSONB for flexible schemas |
| **Vector Store** | Qdrant | Apache 2.0 | Local deployment, gRPC + REST, filtering, horizontal scaling |
| **Vector Store (Lightweight)** | ChromaDB | Apache 2.0 | Optional single-user/laptop mode |
| **Auth** | Keycloak | Apache 2.0 | SAML/OIDC, RBAC, CAC/PIV smart card support |
| **Container Runtime** | Docker / Podman | Apache 2.0 | Agent sandboxing, deployment isolation |
| **Orchestration** | Docker Compose (dev) / Kubernetes (prod) | Apache 2.0 | Single-command dev, scalable prod |
| **Edge Agent** | PicoClaw (Go) | MIT | Sub-10MB, runs on $10 hardware, tactical/field use |
| **Speech-to-Text** | Whisper.cpp | MIT | Local, fast, accurate |
| **Text-to-Speech** | Piper TTS | MIT | Local, multiple voices, low latency |
| **Image Generation** | Stable Diffusion (ComfyUI backend) | Various open | Local diffusion pipeline |
| **OCR** | Tesseract 5 | Apache 2.0 | Document processing pipeline |
| **Message Queue** | Redis Streams or NATS | BSD / Apache 2.0 | Agent task distribution, event bus |

### 3.2 Why This Stack

**vLLM + llama.cpp dual serving**: vLLM is the production workhorse — PagedAttention means efficient GPU memory, continuous batching handles concurrent users, and the OpenAI-compatible API means any client library works. llama.cpp covers the laptop/edge case where you need CPU inference or Apple Silicon Metal acceleration with quantized models.

**Custom Agent Runtime (IronClaw-inspired)**: OpenClaw has critical CVEs. NanoClaw is tied to Claude's cloud SDK. IronClaw's Rust + TEE + MCP approach is the right architecture, but tying to NEAR's cloud defeats the air-gap purpose. We take the architectural patterns (Rust security core, container isolation, MCP protocol, PostgreSQL state) and build our own.

**LangGraph for orchestration**: Agents need multi-step workflows with conditional logic, human-in-the-loop approval, and persistent state. LangGraph's directed graph model makes every execution path auditable — critical for government buyers who need to explain what the AI did and why.

**Qdrant over Pinecone**: Pinecone is cloud-only — immediately disqualified. Qdrant runs fully local, offers better filtering than ChromaDB, and scales horizontally for production.

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 15)                     │
│  ┌──────────┬───────────┬────────────┬──────────┬──────────────┐ │
│  │   Chat   │  RAG Mgmt │  Agent     │  Model   │   Admin &    │ │
│  │   UI     │  & Upload │  Builder   │  Manager │   Audit      │ │
│  └──────────┴───────────┴────────────┴──────────┴──────────────┘ │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTPS (mTLS in production)
┌────────────────────────────▼─────────────────────────────────────┐
│                     API GATEWAY (FastAPI)                         │
│  ┌─────────┬──────────┬───────────┬──────────┬────────────────┐  │
│  │  Auth   │  Rate    │  Audit    │  Route   │  OpenAI-       │  │
│  │  (JWT)  │  Limit   │  Logger   │  Handler │  Compatible    │  │
│  └─────────┴──────────┴───────────┴──────────┴────────────────┘  │
└──┬──────────┬──────────┬───────────┬──────────┬──────────────────┘
   │          │          │           │          │
   ▼          ▼          ▼           ▼          ▼
┌──────┐ ┌────────┐ ┌─────────┐ ┌────────┐ ┌──────────────────┐
│ vLLM │ │ Qdrant │ │ Agent   │ │ File   │ │   PostgreSQL     │
│  or  │ │ Vector │ │ Runtime │ │ Store  │ │                  │
│llama │ │ Store  │ │ (Rust   │ │(local) │ │ - conversations  │
│.cpp  │ │        │ │  core)  │ │        │ │ - users & roles  │
│      │ │        │ │         │ │        │ │ - audit log      │
│      │ │        │ │         │ │        │ │ - agent state    │
│      │ │        │ │         │ │        │ │ - model registry │
└──┬───┘ └────────┘ └────┬────┘ └────────┘ └──────────────────┘
   │                     │
   │              ┌──────▼──────────────────────────┐
   │              │      TOOL SANDBOX (Containers)   │
   │              │  ┌────────┐ ┌────────┐ ┌──────┐ │
   │              │  │ Code   │ │ File   │ │ API  │ │
   │              │  │ Exec   │ │ Ops    │ │ Call │ │
   │              │  │(Python)│ │        │ │      │ │
   │              │  └────────┘ └────────┘ └──────┘ │
   │              └─────────────────────────────────┘
   ▼
┌──────────────────┐
│   Model Store    │
│  (local disk)    │
│                  │
│  - GGUF files    │
│  - safetensors   │
│  - LoRA adapters │
│  - ONNX exports  │
└──────────────────┘
```

### 4.2 Data Flow — Chat with Tool Use

```
User ──▶ Next.js ──▶ FastAPI ──▶ Audit Log (PG)
                        │
                        ▼
                   Route to vLLM
                        │
                        ▼
                  LLM generates response
                  (may include tool_calls)
                        │
                   ┌────▼────┐
                   │ Has     │
                   │ tools?  │
                   └────┬────┘
                   yes  │  no
              ┌─────────┤─────────┐
              ▼                   ▼
        Agent Runtime        Stream response
        executes tools       back to user
        in sandbox
              │
              ▼
        Results fed back
        to LLM for next
        reasoning step
              │
              ▼
        (loop until done
         or human approval
         required)
              │
              ▼
        Final response ──▶ Audit Log ──▶ User
```

### 4.3 Data Flow — RAG Query

```
User query ──▶ FastAPI ──▶ Embed query (local embedding model)
                                │
                                ▼
                          Qdrant: vector similarity search
                          + PostgreSQL: BM25 keyword search
                                │
                                ▼
                          Hybrid rerank (RRF or cross-encoder)
                                │
                                ▼
                          Top-K chunks + metadata
                                │
                                ▼
                          Construct prompt:
                          system + context chunks + user query
                                │
                                ▼
                          vLLM inference
                                │
                                ▼
                          Response with citations
                          (source doc, page, chunk ID)
                                │
                                ▼
                          Audit log ──▶ User
```

### 4.4 Database Schema (PostgreSQL — Core Tables)

```sql
-- Users and access control
users (id, email, name, role, created_at, last_login)
roles (id, name, permissions JSONB)
user_roles (user_id, role_id)

-- Conversations
conversations (id, user_id, title, model_id, created_at, updated_at, classification_level)
messages (id, conversation_id, role, content, tool_calls JSONB, token_count, created_at)

-- RAG / Knowledge Base
collections (id, name, description, owner_id, classification_level, created_at)
collection_permissions (collection_id, role_id, access_level)
documents (id, collection_id, filename, file_type, file_size, chunk_count, status, created_at)
chunks (id, document_id, content, chunk_index, page_number, embedding_id, metadata JSONB)

-- Agent Runtime
agent_definitions (id, name, description, system_prompt, tools JSONB, model_id, created_at)
agent_executions (id, agent_id, user_id, status, started_at, completed_at)
agent_steps (id, execution_id, step_number, action, input JSONB, output JSONB, tool_name, duration_ms, requires_approval BOOLEAN, approved_by, approved_at)

-- Model Registry
models (id, name, version, backend, file_path, quantization, parameters JSONB, status, created_at)
model_evaluations (id, model_id, benchmark, score, evaluated_at)

-- Audit (append-only)
audit_log (id, timestamp, user_id, action, resource_type, resource_id, request JSONB, response_summary, model_id, token_count, ip_address, classification_level)

-- Workflows (LangGraph state)
workflow_definitions (id, name, graph JSONB, created_by, created_at)
workflow_runs (id, workflow_id, user_id, state JSONB, status, started_at, completed_at)
workflow_checkpoints (id, run_id, step, state JSONB, created_at)
```

---

## 5. Phase 0 — Foundation & Infrastructure (Weeks 1-3)

### 5.1 Goals
- Bootable development environment with one command
- LLM serving operational (both vLLM and llama.cpp)
- PostgreSQL schema deployed with migrations
- Qdrant running with test collection
- Basic Next.js shell with auth
- FastAPI gateway with health checks and OpenAI-compatible endpoints
- Docker Compose orchestration for all services

### 5.2 Deliverables

#### Project Structure
```
sovereign-ai-hub/
├── docker-compose.yml              # Full stack orchestration
├── docker-compose.dev.yml          # Dev overrides
├── docker-compose.airgap.yml       # Air-gapped deployment overrides
├── .env.example                    # Environment template (no secrets)
│
├── gateway/                        # FastAPI API Gateway
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/                    # DB migrations
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py               # Settings from env vars
│   │   ├── dependencies.py         # DI: db sessions, auth, etc.
│   │   ├── middleware/
│   │   │   ├── auth.py             # JWT validation
│   │   │   ├── audit.py            # Request/response logging
│   │   │   └── rate_limit.py
│   │   ├── routers/
│   │   │   ├── chat.py             # /v1/chat/completions (OpenAI-compatible)
│   │   │   ├── models.py           # /v1/models
│   │   │   ├── embeddings.py       # /v1/embeddings
│   │   │   ├── collections.py      # RAG collection management
│   │   │   ├── documents.py        # Document upload/processing
│   │   │   ├── agents.py           # Agent CRUD and execution
│   │   │   ├── workflows.py        # LangGraph workflow management
│   │   │   ├── admin.py            # User/role management
│   │   │   └── audit.py            # Audit log queries
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── llm.py              # vLLM/llama.cpp client abstraction
│   │   │   ├── rag.py              # Retrieval pipeline
│   │   │   ├── embedding.py        # Embedding model client
│   │   │   └── agent_runtime.py    # Agent execution engine
│   │   └── utils/
│   │       ├── audit.py            # Audit log writer
│   │       └── crypto.py           # Encryption helpers
│   └── tests/
│
├── frontend/                       # Next.js 15 Application
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx            # Dashboard / landing
│   │   │   ├── chat/
│   │   │   │   ├── page.tsx        # Chat interface
│   │   │   │   └── [id]/page.tsx   # Specific conversation
│   │   │   ├── collections/
│   │   │   │   ├── page.tsx        # RAG collections list
│   │   │   │   └── [id]/page.tsx   # Collection detail + upload
│   │   │   ├── agents/
│   │   │   │   ├── page.tsx        # Agent library
│   │   │   │   ├── builder/page.tsx # Visual agent builder
│   │   │   │   └── [id]/page.tsx   # Agent detail + run
│   │   │   ├── workflows/
│   │   │   │   ├── page.tsx        # Workflow list
│   │   │   │   └── builder/page.tsx # Visual DAG editor
│   │   │   ├── models/
│   │   │   │   └── page.tsx        # Model registry & management
│   │   │   ├── admin/
│   │   │   │   ├── users/page.tsx
│   │   │   │   ├── roles/page.tsx
│   │   │   │   └── audit/page.tsx  # Audit log viewer
│   │   │   └── settings/page.tsx
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── ChatInput.tsx
│   │   │   │   ├── ToolCallDisplay.tsx
│   │   │   │   ├── ThinkingIndicator.tsx
│   │   │   │   └── CitationCard.tsx
│   │   │   ├── agents/
│   │   │   │   ├── AgentCard.tsx
│   │   │   │   ├── ToolSelector.tsx
│   │   │   │   ├── ApprovalDialog.tsx
│   │   │   │   └── ExecutionTimeline.tsx
│   │   │   ├── rag/
│   │   │   │   ├── FileUploader.tsx
│   │   │   │   ├── DocumentList.tsx
│   │   │   │   └── ChunkViewer.tsx
│   │   │   ├── workflows/
│   │   │   │   ├── GraphCanvas.tsx  # DAG editor
│   │   │   │   ├── NodePalette.tsx
│   │   │   │   └── RunViewer.tsx
│   │   │   └── shared/
│   │   │       ├── ModelSelector.tsx
│   │   │       ├── ClassificationBadge.tsx
│   │   │       └── StreamingText.tsx
│   │   ├── lib/
│   │   │   ├── api.ts              # API client (fetch wrapper)
│   │   │   ├── streaming.ts        # SSE/streaming response handler
│   │   │   └── auth.ts             # Token management
│   │   └── stores/                 # Zustand state management
│   │       ├── chatStore.ts
│   │       ├── agentStore.ts
│   │       └── authStore.ts
│   └── tests/
│
├── agent-runtime/                  # Rust Agent Execution Core
│   ├── Dockerfile
│   ├── Cargo.toml
│   ├── src/
│   │   ├── main.rs
│   │   ├── server.rs               # gRPC server for gateway communication
│   │   ├── sandbox/
│   │   │   ├── mod.rs
│   │   │   ├── container.rs        # Docker/Podman container management
│   │   │   └── permissions.rs      # Capability-based access control
│   │   ├── tools/
│   │   │   ├── mod.rs
│   │   │   ├── registry.rs         # Tool discovery and registration
│   │   │   ├── bash.rs             # Sandboxed shell execution
│   │   │   ├── file_ops.rs         # Read/write/list (scoped to workspace)
│   │   │   ├── http_client.rs      # Internal API calls (no external by default)
│   │   │   ├── database.rs         # Read-only SQL against permitted DBs
│   │   │   ├── code_exec.rs        # Sandboxed Python/JS execution
│   │   │   └── mcp.rs              # MCP protocol client for external tools
│   │   ├── execution/
│   │   │   ├── mod.rs
│   │   │   ├── engine.rs           # Step-by-step agent execution loop
│   │   │   ├── planner.rs          # ReAct / plan-and-execute patterns
│   │   │   └── approval.rs         # Human-in-the-loop gate
│   │   ├── state/
│   │   │   ├── mod.rs
│   │   │   └── postgres.rs         # Agent state persistence
│   │   └── audit/
│   │       ├── mod.rs
│   │       └── logger.rs           # Structured audit events
│   └── tests/
│
├── workers/                        # Background Processing (Python)
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── src/
│   │   ├── document_processor.py   # PDF/DOCX/etc ingestion pipeline
│   │   ├── chunker.py              # Semantic/recursive chunking
│   │   ├── embedder.py             # Batch embedding with local model
│   │   ├── ocr.py                  # Tesseract integration
│   │   └── evaluator.py            # Model benchmark runner
│   └── tests/
│
├── orchestration/                  # LangGraph Workflow Definitions
│   ├── pyproject.toml
│   ├── src/
│   │   ├── graphs/
│   │   │   ├── rag_agent.py        # RAG with iterative retrieval
│   │   │   ├── research_agent.py   # Multi-step research workflow
│   │   │   ├── code_agent.py       # Code generation + test + fix loop
│   │   │   └── approval_chain.py   # Multi-approver workflow
│   │   ├── nodes/
│   │   │   ├── llm_node.py
│   │   │   ├── tool_node.py
│   │   │   ├── human_node.py       # Human-in-the-loop
│   │   │   ├── conditional_node.py
│   │   │   └── parallel_node.py
│   │   └── state/
│   │       └── schemas.py          # TypedDict state definitions
│   └── tests/
│
├── models/                         # Model storage (gitignored, volume-mounted)
│   ├── llm/
│   ├── embedding/
│   ├── vision/
│   ├── whisper/
│   ├── tts/
│   └── diffusion/
│
├── scripts/
│   ├── setup.sh                    # One-command dev setup
│   ├── download-models.sh          # Pre-download models for air-gap
│   ├── build-airgap-bundle.sh      # Package everything for offline deploy
│   ├── run-benchmarks.sh           # Model evaluation suite
│   └── generate-sbom.sh            # Software Bill of Materials
│
├── deploy/
│   ├── kubernetes/
│   │   ├── helm-chart/
│   │   └── kustomize/
│   ├── ansible/                    # Bare-metal provisioning
│   └── airgap/
│       ├── container-images/       # Pre-built images for offline
│       └── install.sh              # Offline installer
│
└── docs/
    ├── architecture.md
    ├── api-reference.md
    ├── deployment-guide.md
    ├── security-controls.md        # NIST 800-53 mapping
    ├── user-guide.md
    └── model-compatibility.md
```

#### Docker Compose (Core Services)
```yaml
# docker-compose.yml defines:
services:
  postgres:        # PostgreSQL 16 with pgvector extension
  qdrant:          # Qdrant vector store
  redis:           # Message queue / cache
  vllm:            # vLLM model server (GPU)
  llama-cpp:       # llama.cpp server (CPU fallback)
  gateway:         # FastAPI API gateway
  agent-runtime:   # Rust agent execution engine
  workers:         # Background document processing
  frontend:        # Next.js application
  keycloak:        # Auth server (optional, can use built-in JWT)
```

### 5.3 Task Breakdown

| # | Task | Details | Est. |
|---|---|---|---|
| 0.1 | Project scaffolding | Repo init, monorepo structure, CI config | 2d |
| 0.2 | Docker Compose setup | All services defined, networking, volumes | 2d |
| 0.3 | PostgreSQL schema + migrations | Alembic setup, all core tables, seed data | 3d |
| 0.4 | vLLM server configuration | Dockerfile, model loading, GPU passthrough, health check | 2d |
| 0.5 | llama.cpp server configuration | Dockerfile, GGUF model loading, CPU/Metal config | 1d |
| 0.6 | FastAPI gateway skeleton | Auth middleware, audit middleware, router stubs, OpenAI-compatible /v1/chat/completions | 3d |
| 0.7 | Qdrant setup | Container config, collection creation, embedding pipeline stub | 1d |
| 0.8 | Next.js shell | App router setup, Tailwind, auth flow, layout, model selector | 3d |
| 0.9 | LLM abstraction layer | Unified client that routes to vLLM or llama.cpp based on config | 2d |
| 0.10 | Integration smoke test | End-to-end: frontend → gateway → LLM → response displayed | 1d |

**Phase 0 Total: ~3 weeks**

---

## 6. Phase 1 — Chat & Reasoning Engine (Weeks 3-6)

### 6.1 Goals
Match the conversational UX of ChatGPT/Claude — multi-turn, streaming, model switching, conversation management — entirely local.

### 6.2 Features

#### Chat Core
- Multi-turn conversation with full history management
- Streaming responses via Server-Sent Events (SSE)
- System prompt management (create, save, share personas)
- Model switching mid-conversation (dropdown selector)
- Conversation branching: edit a message and regenerate from that point
- Token counting and context window management
- Stop generation button

#### Reasoning / Thinking Mode
- "Show thinking" toggle: display chain-of-thought reasoning steps
- Implementation: use models that support structured thinking (e.g., Qwen3 with /think tags) or wrap prompts to elicit step-by-step reasoning
- Collapsible thinking blocks in the UI (similar to Claude's extended thinking)

#### Conversation Management
- Conversation list with search and filter
- Auto-generated titles (first message summarization via LLM)
- Manual rename, pin, archive, delete
- Export: JSON (full fidelity), Markdown, PDF
- Classification level tagging per conversation (Unclassified, CUI, etc.)

#### Rendering
- Full Markdown rendering (CommonMark + GFM tables)
- Syntax-highlighted code blocks with copy button
- LaTeX math rendering (KaTeX)
- Mermaid diagram rendering
- Image display (for multimodal responses, Phase 4)

### 6.3 Technical Implementation

#### Streaming Architecture
```
Next.js (client) ←── SSE ←── FastAPI ←── vLLM (streaming)

Frontend: EventSource or fetch + ReadableStream
Gateway:  StreamingResponse with async generator
vLLM:     OpenAI-compatible streaming (/v1/chat/completions, stream=true)
```

#### Context Window Management
```python
# Gateway handles context windowing:
# 1. Load full conversation history from PostgreSQL
# 2. Count tokens (tiktoken or model-specific tokenizer)
# 3. If over limit: sliding window (keep system + last N messages)
#    OR: summarize older messages via LLM call
# 4. Forward trimmed context to vLLM
```

### 6.4 Task Breakdown

| # | Task | Est. |
|---|---|---|
| 1.1 | Chat API endpoint with streaming (FastAPI SSE) | 3d |
| 1.2 | Conversation CRUD (create, list, get, update, delete) | 2d |
| 1.3 | Message persistence and retrieval | 1d |
| 1.4 | Context window management (token counting, trimming) | 2d |
| 1.5 | Chat UI — message list, input, streaming display | 3d |
| 1.6 | Chat UI — markdown/code/LaTeX/Mermaid rendering | 2d |
| 1.7 | Model selector component + backend routing | 1d |
| 1.8 | Thinking/reasoning mode (UI toggle + prompt wrapping) | 2d |
| 1.9 | Conversation management UI (list, search, export) | 2d |
| 1.10 | System prompt library (CRUD + assignment to conversations) | 2d |

**Phase 1 Total: ~3 weeks**

---

## 7. Phase 2 — RAG & Knowledge Base (Weeks 6-10)

### 7.1 Goals
"Talk to your documents" — the #1 government use case. Upload documents, ask questions, get cited answers.

### 7.2 Features

#### Document Ingestion
- Supported formats: PDF, DOCX, XLSX, PPTX, TXT, HTML, Markdown, CSV, JSON, email (.eml, .msg)
- OCR for scanned PDFs and images (Tesseract 5)
- Table extraction (preserve structured data from PDFs/XLSX)
- Metadata extraction (author, date, title, classification markings)
- Batch upload with progress tracking
- Background processing queue (Redis Streams)

#### Chunking Pipeline
```
Document → Parse → Clean → Chunk → Embed → Store

Chunking strategies (configurable per collection):
1. Recursive character splitting (default, configurable size/overlap)
2. Semantic chunking (split on topic boundaries via embedding similarity)
3. Document-structure-aware (respect headings, paragraphs, tables)
4. Sliding window with overlap
```

#### Retrieval
- **Hybrid search**: vector similarity (Qdrant) + keyword BM25 (PostgreSQL full-text search)
- **Reciprocal Rank Fusion (RRF)** to merge results from both search methods
- **Optional cross-encoder reranking** (local reranker model, e.g., bge-reranker)
- Configurable top-K retrieval (default 5, adjustable)
- **Metadata filtering**: filter by collection, date range, document type, classification level
- **Multi-collection search**: query across multiple collections in one request

#### Citations
- Every RAG response includes source citations
- Citation format: document name, page number, chunk excerpt
- Click-through from citation to source document viewer
- Highlight the relevant passage in the original document

#### Collection Management
- Create named collections (e.g., "Policy Documents", "Technical Manuals")
- Per-collection access control (role-based)
- Classification level per collection
- Collection statistics: document count, chunk count, storage size
- Re-index collection (re-chunk, re-embed after settings change)

### 7.3 Technical Implementation

#### Embedding Model
```
Default: nomic-embed-text (768 dim, runs on CPU, strong performance)
Alternative: bge-large-en-v1.5 (1024 dim, slightly better accuracy)
Served via: vLLM embedding endpoint OR sentence-transformers locally
```

#### Qdrant Collection Schema
```json
{
  "collection_name": "collection_{uuid}",
  "vectors": {
    "size": 768,
    "distance": "Cosine"
  },
  "payload_schema": {
    "document_id": "keyword",
    "chunk_index": "integer",
    "page_number": "integer",
    "content": "text",
    "classification_level": "keyword",
    "created_at": "datetime"
  }
}
```

#### PostgreSQL Full-Text Search (BM25 equivalent)
```sql
-- Add tsvector column to chunks table
ALTER TABLE chunks ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX idx_chunks_search ON chunks USING GIN (search_vector);

-- Query
SELECT id, content, ts_rank(search_vector, query) AS rank
FROM chunks, plainto_tsquery('english', :user_query) query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT :top_k;
```

### 7.4 Task Breakdown

| # | Task | Est. |
|---|---|---|
| 2.1 | Document upload API + file storage | 2d |
| 2.2 | PDF parser (text + OCR fallback) | 3d |
| 2.3 | DOCX/XLSX/PPTX/HTML parsers | 2d |
| 2.4 | Chunking pipeline (recursive, semantic, structure-aware) | 3d |
| 2.5 | Embedding service (local model, batch processing) | 2d |
| 2.6 | Qdrant integration (collection CRUD, upsert, search) | 2d |
| 2.7 | PostgreSQL full-text search setup | 1d |
| 2.8 | Hybrid retrieval + RRF merging | 2d |
| 2.9 | RAG prompt construction (system + context + query) | 1d |
| 2.10 | Citation extraction and formatting | 2d |
| 2.11 | Collection management API + RBAC | 2d |
| 2.12 | Frontend — file upload UI with progress | 2d |
| 2.13 | Frontend — collection management | 2d |
| 2.14 | Frontend — citation display + document viewer | 2d |
| 2.15 | Background worker queue (Redis Streams) | 1d |

**Phase 2 Total: ~4 weeks**

---

## 8. Phase 3 — Agentic Runtime (Weeks 10-16)

### 8.1 Goals
This is the core differentiator. Build an agent that can actually do things — call tools, execute code, read files, query databases, chain multi-step plans — all within a security sandbox.

### 8.2 Architecture: Custom Agent Runtime (IronClaw-Inspired)

#### Design Principles (Taken from IronClaw)
1. **Rust core** for security-critical paths (sandbox, permissions, tool execution)
2. **Container isolation** — every tool execution runs in a sandboxed container
3. **MCP Protocol support** — extensible tool ecosystem via Model Context Protocol
4. **Capability-based permissions** — agents get explicit capability grants, not ambient authority
5. **PostgreSQL state** — all agent state persisted, recoverable, auditable
6. **Human-in-the-loop gates** — configurable approval requirements before sensitive actions

#### Agent Execution Loop
```
┌─────────────────────────────────────────────────┐
│                 AGENT EXECUTION ENGINE           │
│                                                  │
│  1. Receive task (user prompt + agent config)    │
│  2. Load agent definition (system prompt, tools) │
│  3. Send to LLM with tool definitions            │
│  4. LLM responds:                                │
│     ├── text only → return to user               │
│     └── tool_call → proceed to step 5            │
│  5. Check permissions:                           │
│     ├── auto-approved → execute in sandbox       │
│     └── requires approval → pause, notify user   │
│  6. Execute tool in container sandbox            │
│  7. Capture output (stdout, stderr, artifacts)   │
│  8. Feed tool result back to LLM                 │
│  9. Log step to audit trail                      │
│  10. Loop to step 4 (max iterations configurable)│
│  11. Return final response + execution trace     │
└─────────────────────────────────────────────────┘
```

### 8.3 Built-In Tools

#### Tier 1 — Core Tools (Ship in Phase 3)
| Tool | Description | Sandbox | Approval |
|---|---|---|---|
| `bash` | Execute shell commands | Container | Configurable |
| `file_read` | Read file contents (scoped to workspace) | Container | Auto |
| `file_write` | Write/create files (scoped to workspace) | Container | Configurable |
| `file_list` | List directory contents | Container | Auto |
| `python_exec` | Execute Python code, return output | Container | Configurable |
| `javascript_exec` | Execute JavaScript/Node.js | Container | Configurable |
| `http_request` | Make HTTP requests (internal network only by default) | Container | Configurable |
| `sql_query` | Read-only SQL against permitted databases | Direct (read-only) | Auto |
| `rag_search` | Search RAG collections | Direct | Auto |
| `web_search` | Search the web (disabled in air-gap mode) | Container | Yes |

#### Tier 2 — Extended Tools (Phase 3.5)
| Tool | Description |
|---|---|
| `git_ops` | Clone, diff, commit, branch (scoped repos) |
| `image_analyze` | Send image to vision model for analysis |
| `generate_image` | Create image via local Stable Diffusion |
| `send_notification` | Internal notification (webhook, email) |
| `calendar` | Read/create events (when integrated) |
| `spreadsheet` | Read/analyze spreadsheet data |

#### Tier 3 — MCP External Tools (Phase 3.5+)
- Any tool exposed via MCP protocol
- Third-party MCP servers can be registered by admin
- Each MCP tool inherits the permission/sandbox model

### 8.4 Tool Sandbox Architecture

```
┌─ Host Machine ─────────────────────────────────┐
│                                                 │
│  Agent Runtime (Rust)                           │
│    │                                            │
│    ├── Tool Request                             │
│    │     │                                      │
│    │     ▼                                      │
│    ├── Permission Check                         │
│    │     │                                      │
│    │     ▼                                      │
│    ├── Container Manager                        │
│    │     │                                      │
│    │     ▼                                      │
│    │  ┌─ Sandbox Container ──────────────────┐  │
│    │  │                                      │  │
│    │  │  - Ephemeral (destroyed after exec)   │  │
│    │  │  - Read-only root filesystem          │  │
│    │  │  - Workspace dir mounted (r/w)        │  │
│    │  │  - No network (unless explicit grant) │  │
│    │  │  - Resource limits (CPU, RAM, time)   │  │
│    │  │  - No host device access              │  │
│    │  │  - seccomp + AppArmor profiles        │  │
│    │  │                                      │  │
│    │  │  Executes: bash, python, node, etc.  │  │
│    │  │  Returns: stdout, stderr, exit code  │  │
│    │  │                                      │  │
│    │  └──────────────────────────────────────┘  │
│    │                                            │
│    ├── Capture output                           │
│    ├── Log to audit trail                       │
│    └── Return result to LLM                     │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 8.5 LangGraph Integration

LangGraph handles the higher-level orchestration — multi-agent workflows, conditional branching, parallel execution, long-running tasks with checkpoints.

#### Example: Research Agent Graph
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated

class ResearchState(TypedDict):
    query: str
    search_results: list[str]
    analysis: str
    draft: str
    review: str
    final_output: str
    needs_revision: bool

graph = StateGraph(ResearchState)

# Nodes
graph.add_node("search", search_rag_collections)
graph.add_node("analyze", analyze_results_with_llm)
graph.add_node("draft", draft_response)
graph.add_node("review", review_and_critique)
graph.add_node("revise", revise_draft)

# Edges
graph.add_edge("search", "analyze")
graph.add_edge("analyze", "draft")
graph.add_edge("draft", "review")
graph.add_conditional_edges(
    "review",
    lambda state: "revise" if state["needs_revision"] else END
)
graph.add_edge("revise", "review")  # Loop back

graph.set_entry_point("search")
research_agent = graph.compile(checkpointer=postgres_checkpointer)
```

#### Example: Approval Workflow Graph
```python
# Multi-step workflow with human-in-the-loop
graph.add_node("plan", create_execution_plan)
graph.add_node("human_review", interrupt_for_approval)  # Pauses execution
graph.add_node("execute", execute_approved_plan)
graph.add_node("report", generate_report)

graph.add_edge("plan", "human_review")
graph.add_conditional_edges(
    "human_review",
    lambda state: "execute" if state["approved"] else END
)
graph.add_edge("execute", "report")
```

### 8.6 Agent Definition Schema (User-Facing)

```json
{
  "name": "Data Analyst",
  "description": "Analyzes datasets, generates visualizations, and produces reports",
  "system_prompt": "You are a data analyst. Use the provided tools to analyze data, create visualizations, and write reports. Always show your work.",
  "model": "llama-3.1-70b-instruct",
  "tools": ["python_exec", "file_read", "file_write", "sql_query", "rag_search"],
  "permissions": {
    "network": false,
    "max_iterations": 20,
    "max_execution_time_seconds": 300,
    "require_approval_for": ["file_write", "sql_query"],
    "workspace_path": "/workspaces/{execution_id}"
  },
  "output_format": "markdown"
}
```

### 8.7 Frontend — Agent Experience

- **Agent Library**: browse/search pre-built agents (Data Analyst, Researcher, Code Generator, etc.)
- **Agent Builder**: form-based agent creation (name, prompt, model, tools, permissions)
- **Execution View**: real-time step-by-step execution display
  - Each step shows: tool called, input, output, duration
  - Thinking/reasoning steps shown in collapsible blocks
  - Artifacts (files, images, charts) displayed inline
  - Approval dialogs for gated actions
- **Execution History**: browse past agent runs, replay steps, view audit trail

### 8.8 Task Breakdown

| # | Task | Est. |
|---|---|---|
| 3.1 | Rust agent runtime — project setup, gRPC server | 3d |
| 3.2 | Container sandbox manager (Docker SDK) | 4d |
| 3.3 | Permission system (capability grants, approval gates) | 3d |
| 3.4 | Tool framework — registry, schema, execution interface | 3d |
| 3.5 | Implement Tier 1 tools (bash, file ops, python exec, http, sql, rag) | 5d |
| 3.6 | Agent execution engine (loop, tool dispatch, state tracking) | 4d |
| 3.7 | LLM tool-calling integration (OpenAI function calling format) | 2d |
| 3.8 | LangGraph setup — core nodes, state schemas, PostgreSQL checkpointer | 3d |
| 3.9 | Pre-built workflow graphs (research, code, approval chain) | 3d |
| 3.10 | Human-in-the-loop — pause/resume, WebSocket notification | 3d |
| 3.11 | Agent definition CRUD API | 2d |
| 3.12 | Agent execution API (start, status, approve, cancel) | 2d |
| 3.13 | MCP protocol client (connect to external MCP tool servers) | 3d |
| 3.14 | Frontend — agent library + builder | 3d |
| 3.15 | Frontend — execution view with real-time steps | 4d |
| 3.16 | Frontend — approval dialog + execution history | 2d |
| 3.17 | Audit logging for all agent actions | 2d |

**Phase 3 Total: ~6 weeks**

---

## 9. Phase 4 — Multimodal Capabilities (Weeks 16-20)

### 9.1 Goals
Vision, voice, and image generation — all local.

### 9.2 Features

#### Vision (Image Understanding)
- Upload images in chat → model describes, extracts text, answers questions
- Models: LLaVA 1.6, Llama 3.2 Vision (11B/90B), Qwen2-VL
- Served via vLLM (supports multimodal models)
- Use cases: analyze charts, read handwritten notes, describe photos, extract data from screenshots

#### Speech-to-Text
- Whisper.cpp for local transcription
- Real-time (streaming) and batch modes
- Language detection and translation
- Integration: microphone button in chat UI, or upload audio files
- Supported formats: WAV, MP3, M4A, FLAC, OGG

#### Text-to-Speech
- Piper TTS for local voice synthesis
- Multiple voice options (configurable per user)
- Read-aloud button on any AI response
- Streaming audio output for long responses

#### Image Generation
- Stable Diffusion XL or SD 3 via ComfyUI backend
- Text-to-image in chat ("generate an image of...")
- Agent tool: `generate_image` for agentic workflows
- Prompt enhancement (LLM rewrites user prompt for better SD results)
- Image gallery with history

#### Document Vision (Direct)
- Skip OCR pipeline: feed PDF page images directly to vision model
- Better for complex layouts, forms, handwritten content
- Fallback/complement to the text-based RAG pipeline

### 9.3 Task Breakdown

| # | Task | Est. |
|---|---|---|
| 4.1 | vLLM multimodal model serving (LLaVA/Llama Vision) | 3d |
| 4.2 | Image upload + vision query API | 2d |
| 4.3 | Whisper.cpp integration (server mode) | 2d |
| 4.4 | Speech-to-text API endpoint + streaming | 2d |
| 4.5 | Piper TTS integration | 2d |
| 4.6 | Text-to-speech API endpoint + audio streaming | 2d |
| 4.7 | ComfyUI backend setup for image generation | 3d |
| 4.8 | Image generation API + prompt enhancement | 2d |
| 4.9 | Frontend — image upload, voice button, audio player, image gallery | 4d |
| 4.10 | Document vision pipeline (PDF pages → vision model) | 2d |

**Phase 4 Total: ~4 weeks**

---

## 10. Phase 5 — Code Assistant (Weeks 20-24)

### 10.1 Goals
Local Copilot — code generation, analysis, execution, and git integration.

### 10.2 Features

- Code generation from natural language
- Code explanation and documentation
- Bug detection and fix suggestions
- Multi-file context awareness (upload project files or connect workspace)
- Sandboxed code execution with output capture (Python, JavaScript, Bash, SQL)
- Git integration: diff review, commit message generation, PR summary
- Jupyter-style notebook interface for iterative code + output
- Language-specific: Python, JavaScript/TypeScript, SQL, Bash, Go, Rust, Java, C/C++
- Integration with Agent Runtime — code agent can iteratively write, run, debug

### 10.3 Models
- Primary: Qwen2.5-Coder (7B/32B) or DeepSeek Coder V2
- Alternative: CodeLlama 34B, StarCoder2

### 10.4 Task Breakdown

| # | Task | Est. |
|---|---|---|
| 5.1 | Code-focused agent definition (system prompts, tool config) | 2d |
| 5.2 | Multi-file context assembly (workspace upload + indexing) | 3d |
| 5.3 | Code execution sandbox (Python, JS, Bash with output capture) | 3d |
| 5.4 | Git integration tools (diff, log, commit msg generation) | 2d |
| 5.5 | Notebook-style UI (code cells + output cells) | 4d |
| 5.6 | Code-specific UI components (syntax highlight, diff viewer) | 3d |
| 5.7 | Iterative code agent workflow (write → run → fix loop) | 3d |

**Phase 5 Total: ~4 weeks**

---

## 11. Phase 6 — Security, Compliance & Governance (Weeks 24-28)

### 11.1 Goals
Harden everything. Map controls. Generate compliance documentation. Make it government-sellable.

### 11.2 Security Features

#### Authentication & Authorization
- Keycloak integration: SAML 2.0, OIDC, LDAP/AD
- CAC/PIV smart card authentication (via Keycloak SPI)
- RBAC: Admin, Manager, Analyst, Viewer (customizable roles)
- Per-resource permissions: collections, agents, workflows, models
- Session management: configurable timeout, concurrent session limits
- MFA support (TOTP, WebAuthn/FIDO2)

#### Encryption
- At rest: AES-256-GCM for sensitive fields in PostgreSQL (using pgcrypto)
- At rest: LUKS (Linux) or FileVault (macOS) for disk encryption
- In transit: TLS 1.3 between all services, mTLS option for service mesh
- Model files: optional encryption at rest with key management

#### Audit System
```
Every interaction generates an immutable audit record:

{
  "timestamp": "2026-03-15T14:30:00Z",
  "user_id": "u-abc123",
  "action": "agent_tool_execution",
  "resource_type": "agent_execution",
  "resource_id": "exec-xyz789",
  "details": {
    "agent": "Data Analyst",
    "tool": "python_exec",
    "input_summary": "pandas read_csv and groupby...",
    "output_summary": "DataFrame with 5 columns, 100 rows",
    "duration_ms": 1230,
    "approval": "auto",
    "model": "llama-3.1-70b-instruct",
    "tokens_in": 1500,
    "tokens_out": 800
  },
  "classification_level": "CUI",
  "ip_address": "10.0.1.50"
}
```
- Audit log stored in append-only PostgreSQL table (no UPDATE/DELETE permissions)
- Export to SIEM (Splunk, Elastic) via syslog or webhook
- Retention policy configuration (30d, 90d, 1y, indefinite)
- Audit dashboard with filtering, search, and export

#### Data Classification
- Classification level tagging: Unclassified, CUI, FOUO, SECRET (configurable)
- Per-conversation, per-collection, per-document classification
- Visual banners showing classification level (color-coded header/footer)
- Prevent cross-classification data mixing (CUI collection can't be used in Unclassified chat)
- Classification downgrade requires admin approval

#### Network Security
- Air-gap mode: all external network calls blocked at container level
- Internal-only mode: only calls to whitelisted internal endpoints
- Network policy enforcement via Docker network isolation or Kubernetes NetworkPolicy
- No telemetry, no analytics, no phone-home in any component
- DNS resolution: local only (no external DNS queries)

### 11.3 Compliance Mapping

#### NIST 800-53 Rev 5 (Selected Controls)

| Control Family | Control | Implementation |
|---|---|---|
| AC (Access Control) | AC-2 Account Management | Keycloak user lifecycle, RBAC |
| AC | AC-3 Access Enforcement | Per-resource RBAC, collection permissions |
| AC | AC-6 Least Privilege | Capability-based agent permissions |
| AU (Audit) | AU-2 Event Logging | Full prompt/response/tool audit |
| AU | AU-3 Content of Audit Records | Structured JSON with all required fields |
| AU | AU-6 Audit Review | Dashboard, SIEM export, alerting |
| AU | AU-9 Protection of Audit Info | Append-only table, separate DB role |
| CM (Config Mgmt) | CM-2 Baseline Configuration | Docker images, IaC, pinned versions |
| CM | CM-6 Configuration Settings | All config via env vars, no hardcoded secrets |
| CM | CM-8 System Component Inventory | SBOM generation, container image manifest |
| IA (Identification) | IA-2 Identification and Auth | Keycloak + MFA + CAC/PIV |
| SC (System/Comms) | SC-8 Transmission Confidentiality | TLS 1.3, mTLS between services |
| SC | SC-13 Cryptographic Protection | AES-256-GCM, FIPS 140-2 validated libs |
| SC | SC-28 Protection of Info at Rest | Disk encryption, DB field encryption |
| SI (System Integrity) | SI-4 System Monitoring | Audit log, container health, resource limits |

#### SBOM (Software Bill of Materials)
- Generated via `syft` for container images
- Generated via `pip-audit` / `npm audit` for application dependencies
- Includes: package name, version, license, known CVEs
- Delivered as SPDX or CycloneDX format
- Regenerated on every release

### 11.4 Task Breakdown

| # | Task | Est. |
|---|---|---|
| 6.1 | Keycloak integration (SAML/OIDC, user sync) | 4d |
| 6.2 | RBAC enforcement across all API endpoints | 3d |
| 6.3 | Per-resource permissions (collections, agents, models) | 3d |
| 6.4 | Audit log hardening (append-only, SIEM export) | 3d |
| 6.5 | Data classification system (tagging, banners, enforcement) | 3d |
| 6.6 | Encryption at rest (pgcrypto, field-level encryption) | 2d |
| 6.7 | mTLS between services | 2d |
| 6.8 | Air-gap network enforcement (container network policies) | 2d |
| 6.9 | SBOM generation pipeline | 1d |
| 6.10 | Security controls documentation (NIST mapping) | 3d |
| 6.11 | Penetration test (self-assessment or contracted) | 5d |
| 6.12 | Frontend — audit viewer, classification banners, admin panels | 4d |

**Phase 6 Total: ~5 weeks**

---

## 12. Phase 7 — Fine-Tuning & Model Management (Weeks 28-32)

### 12.1 Goals
Let operators customize models for their domain. Manage model lifecycle.

### 12.2 Features

#### Fine-Tuning
- LoRA/QLoRA fine-tuning on local GPU (8B-70B models)
- Dataset preparation UI: upload JSONL, CSV, or create from conversation history
- Training configuration: learning rate, epochs, LoRA rank, target modules
- Training progress monitoring (loss curves, eval metrics)
- Adapter management: save, version, apply, stack multiple LoRA adapters

#### Model Registry
- List all available models (base models, fine-tuned adapters, quantizations)
- Model metadata: parameter count, quantization level, context window, supported features
- Model status: downloading, available, loaded, active
- Version tagging and rollback
- Import/export for air-gapped transfer (USB, secure file transfer)

#### Evaluation
- Automated benchmark suite on model load:
  - General: MMLU subset, HellaSwag
  - Code: HumanEval, MBPP
  - RAG: custom retrieval accuracy benchmark
  - Tool calling: custom tool-use accuracy benchmark
- Side-by-side model comparison UI
- A/B testing: route % of traffic to different models, compare metrics

### 12.3 Task Breakdown

| # | Task | Est. |
|---|---|---|
| 7.1 | Model registry API (CRUD, status, metadata) | 3d |
| 7.2 | Model download/import pipeline | 2d |
| 7.3 | LoRA fine-tuning service (unsloth or PEFT) | 5d |
| 7.4 | Dataset preparation tools (format conversion, validation) | 3d |
| 7.5 | Training monitoring (progress, metrics, early stopping) | 2d |
| 7.6 | Evaluation benchmark runner | 3d |
| 7.7 | A/B testing infrastructure (traffic routing, metrics collection) | 3d |
| 7.8 | Frontend — model manager, training UI, eval dashboard | 4d |

**Phase 7 Total: ~4 weeks**

---

## 13. Phase 8 — Edge Deployment (Weeks 32-36)

### 13.1 Goals
Extend the platform to disconnected, tactical, and resource-constrained environments using PicoClaw-inspired edge agents.

### 13.2 Features

#### Edge Agent (Go Binary)
- Single binary, cross-compiled for ARM64, x86_64, RISC-V
- Sub-10MB footprint, boots in <1 second
- Runs quantized small models (Phi-3 Mini, TinyLlama, Qwen2 0.5B)
- Connects to hub when network available, operates independently when disconnected
- Syncs conversation history and knowledge base deltas when reconnected

#### Hub-Edge Sync
```
┌──────────────┐          ┌──────────────┐
│  Sovereign   │  ◄─sync─►│  Edge Agent  │
│  AI Hub      │          │  (PicoClaw)  │
│  (datacenter)│          │  (field)     │
│              │          │              │
│  Full models │          │  Tiny models │
│  Full RAG    │          │  Local cache │
│  All tools   │          │  Basic tools │
└──────────────┘          └──────────────┘

Sync protocol:
- Knowledge base: delta sync (new chunks only)
- Conversations: full sync on reconnect
- Models: admin-pushed updates
- Config: policy sync (permissions, classifications)
```

#### Use Cases
- Field analysts with laptop + no connectivity
- SCIF workstations with air-gapped networks
- Deployed units with limited bandwidth
- IoT/sensor data analysis at the edge

### 13.3 Task Breakdown

| # | Task | Est. |
|---|---|---|
| 8.1 | Edge agent binary (Go, cross-compilation) | 5d |
| 8.2 | Small model serving (llama.cpp embedded) | 3d |
| 8.3 | Local knowledge cache (embedded SQLite + vector) | 3d |
| 8.4 | Hub-edge sync protocol (delta sync, conflict resolution) | 5d |
| 8.5 | Edge management dashboard (hub-side) | 3d |
| 8.6 | Testing on constrained hardware (RPi, NUC) | 2d |

**Phase 8 Total: ~4 weeks**

---

## 14. Deployment Strategy

### 14.1 Deployment Targets

| Target | Stack | Use Case |
|---|---|---|
| **Developer Laptop** | `docker compose up` | Development, demos |
| **Single Server** | Docker Compose + TLS + Postgres | Small team, pilot |
| **Air-Gapped Enclave** | Pre-built images on USB/ISO, offline install script | Classified environments |
| **Kubernetes Cluster** | Helm chart, GPU operator, horizontal scaling | Enterprise / multi-team |
| **Edge Device** | Single Go binary + small model | Field / disconnected ops |

### 14.2 One-Command Dev Setup

```bash
# Clone and start everything
git clone <repo>
cd sovereign-ai-hub
cp .env.example .env

# Download a starter model
./scripts/download-models.sh --model llama-3.1-8b-instruct-q4

# Start all services
docker compose up -d

# Access at https://localhost:3000
```

### 14.3 Air-Gap Bundle

```bash
# Build the complete offline bundle
./scripts/build-airgap-bundle.sh \
  --models llama-3.1-70b-instruct-q4,nomic-embed-text,whisper-large-v3 \
  --output sovereign-ai-hub-airgap-v1.0.tar.gz

# Bundle contains:
# - All Docker images (pre-built, saved as tar)
# - All model weights
# - Install script
# - Configuration templates
# - SBOM
# - Documentation

# On target machine (no internet required):
tar xzf sovereign-ai-hub-airgap-v1.0.tar.gz
cd sovereign-ai-hub-airgap
sudo ./install.sh
```

### 14.4 Kubernetes Production

```bash
# Add Helm repo (or use local chart in air-gap)
helm install sovereign-ai ./deploy/kubernetes/helm-chart \
  --namespace sovereign-ai \
  --set gpu.enabled=true \
  --set gpu.count=4 \
  --set vllm.model=llama-3.1-70b-instruct \
  --set postgres.storageClass=fast-ssd \
  --set ingress.tls.enabled=true \
  --set keycloak.enabled=true
```

---

## 15. Model Selection Guide

### 15.1 Recommended Models by Use Case

| Use Case | Model | Parameters | Quantization | VRAM Required | Notes |
|---|---|---|---|---|---|
| **General Chat (Laptop)** | Llama 3.1 8B Instruct | 8B | Q4_K_M | ~6 GB | Best quality/size ratio for laptop |
| **General Chat (Server)** | Llama 3.1 70B Instruct | 70B | Q4_K_M | ~40 GB | Production quality |
| **General Chat (Best)** | Llama 3.1 405B Instruct | 405B | Q4_K_M | ~240 GB | Multi-GPU required |
| **Tool Calling** | Llama 3.1 70B Instruct | 70B | Q4_K_M | ~40 GB | Native tool calling support |
| **Tool Calling (Alt)** | Qwen2.5 72B Instruct | 72B | Q4_K_M | ~42 GB | Excellent tool calling |
| **Tool Calling (Small)** | Mistral Nemo 12B | 12B | Q4_K_M | ~8 GB | Best small model for tools |
| **Code** | Qwen2.5-Coder 32B | 32B | Q4_K_M | ~20 GB | Top code performance |
| **Code (Small)** | DeepSeek Coder V2 Lite | 16B | Q4_K_M | ~10 GB | Good code on limited hardware |
| **Embedding** | nomic-embed-text | 137M | FP16 | ~0.5 GB | 768-dim, runs on CPU |
| **Embedding (Alt)** | bge-large-en-v1.5 | 335M | FP16 | ~1 GB | 1024-dim, slightly better |
| **Reranker** | bge-reranker-v2-m3 | 568M | FP16 | ~1.5 GB | Cross-encoder reranking |
| **Vision** | Llama 3.2 Vision 11B | 11B | Q4_K_M | ~8 GB | Image understanding |
| **Vision (Best)** | Llama 3.2 Vision 90B | 90B | Q4_K_M | ~55 GB | Best local vision |
| **Speech-to-Text** | Whisper Large V3 | 1.5B | FP16 | ~3 GB | Via whisper.cpp |
| **Text-to-Speech** | Piper TTS | Varies | Native | ~0.2 GB | Multiple voice models |
| **Image Gen** | SDXL Turbo | 6.6B | FP16 | ~8 GB | Fast image generation |
| **Edge** | Phi-3 Mini 3.8B | 3.8B | Q4_K_M | ~2.5 GB | Best for constrained devices |

### 15.2 Tool Calling Model Requirements

For the agentic runtime to work, the LLM MUST support function/tool calling. Specifically:

- Model must output structured `tool_calls` in OpenAI function calling format
- vLLM serves this via `--enable-auto-tool-choice` flag
- Verified models with tool calling:
  - Llama 3.1 (all sizes) — native tool calling
  - Qwen2.5 (all sizes) — native tool calling
  - Mistral Nemo / Mistral Large — native tool calling
  - Hermes 2 Pro — function calling fine-tuned
  - Functionary — specifically trained for function calling

### 15.3 Hardware Sizing Guide

| Deployment | Users | Hardware | Models |
|---|---|---|---|
| **Laptop Demo** | 1 | MacBook M2/M3 16GB+ | 8B Q4 + embedding |
| **Small Team** | 5-10 | 1x server, 1x A100 80GB | 70B Q4 + embedding + vision |
| **Department** | 50-100 | 2-4x A100 80GB, 128GB RAM | 70B FP16 + code + vision + STT/TTS |
| **Enterprise** | 500+ | 8+ A100/H100, Kubernetes | Multiple models, redundancy |
| **Edge** | 1 | Raspberry Pi 5 / NUC | 3.8B Q4 |

---

## 16. Risk Register

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| Local model quality insufficient for complex tasks | High | Medium | Support multiple models, A/B testing, fine-tuning pipeline |
| Agent sandbox escape | Critical | Low | Defense in depth: containers + seccomp + AppArmor + no network + resource limits |
| Prompt injection in RAG documents | High | Medium | Input sanitization, output filtering, user awareness training |
| GPU availability/cost for government buyers | Medium | Medium | Support CPU inference (llama.cpp), Apple Silicon, quantized models |
| Rapid open-source ecosystem changes | Medium | High | Abstraction layers at every integration point, swappable components |
| Single model vendor risk (Meta/Llama dominance) | Medium | Low | Support Qwen, Mistral, Phi, DeepSeek — no single vendor dependency |
| Keycloak upgrade breaks auth | Medium | Low | Version pinning, integration tests, rollback plan |
| Data loss in PostgreSQL | Critical | Low | Automated backups, WAL archiving, point-in-time recovery |

---

## 17. Government Sales Positioning

### 17.1 Elevator Pitch (30 seconds)

> "We built ChatGPT for your classified network. It runs entirely on your hardware — no data leaves your building, ever. Your analysts get AI chat, document Q&A, autonomous agents, code generation, and voice — all local, all auditable, all under your control. Swap models without vendor lock-in. Scale from a laptop demo to a datacenter deployment with the same codebase."

### 17.2 Competitive Positioning

| Capability | ChatGPT Enterprise | AWS Bedrock | Azure OpenAI | **Sovereign AI Hub** |
|---|---|---|---|---|
| Air-gap capable | No | No | No | **Yes** |
| Data stays on-prem | No (cloud) | No (AWS) | No (Azure) | **Yes** |
| Model vendor lock-in | Yes (OpenAI) | Partial | Yes (OpenAI) | **No — open weight** |
| Audit trail | Limited | Partial | Partial | **Full — every action** |
| Agentic tool use | Yes | Limited | Yes | **Yes — sandboxed** |
| Cost model | Per-token SaaS | Per-token SaaS | Per-token SaaS | **One-time + hardware** |
| Classification support | No | Partial (GovCloud) | Partial | **Built-in** |
| SBOM available | No | No | No | **Yes** |

### 17.3 Target Buyers

| Buyer | Pain Point | Our Message |
|---|---|---|
| **CISO** | "AI tools are shadow IT leaking our data" | "Deploy sanctioned AI that your team controls. Full audit. Zero exfiltration." |
| **CTO** | "We need AI but can't use cloud in our environment" | "Same capabilities, runs on your network, scales with your infrastructure." |
| **Program Manager** | "My analysts waste hours on document review" | "RAG pipeline answers questions from your documents in seconds, with citations." |
| **Contracting Officer** | "I need NIST 800-53 controls documentation" | "Here's our controls mapping. Here's our SBOM. Here's the audit log." |

### 17.4 Pricing Model (Suggested)

| Tier | Target | Includes |
|---|---|---|
| **Starter** | Small team pilot | Software license, 1 model, email support |
| **Professional** | Department | Software + all models, RAG + agents, 8x5 support |
| **Enterprise** | Organization-wide | Everything + fine-tuning + custom agents + 24x7 support + compliance docs |
| **Edge Add-On** | Field deployments | Edge agent license per device |

---

## Timeline Summary

| Phase | Weeks | Cumulative |
|---|---|---|
| Phase 0: Foundation | 1–3 | 3 weeks |
| Phase 1: Chat & Reasoning | 3–6 | 6 weeks |
| Phase 2: RAG & Knowledge Base | 6–10 | 10 weeks |
| Phase 3: Agentic Runtime | 10–16 | 16 weeks |
| Phase 4: Multimodal | 16–20 | 20 weeks |
| Phase 5: Code Assistant | 20–24 | 24 weeks |
| Phase 6: Security & Compliance | 24–28 | 28 weeks |
| Phase 7: Fine-Tuning & Models | 28–32 | 32 weeks |
| Phase 8: Edge Deployment | 32–36 | 36 weeks |

**Total: ~36 weeks (9 months) to full feature set.**

MVP (Phases 0-3): **16 weeks (4 months)** — chat, RAG, agents. Demoable to government buyers.

---

## Next Steps

1. **Validate model selection** — download and test top 3 LLMs for tool calling accuracy
2. **Scaffold Phase 0** — repo init, Docker Compose, database schema
3. **Build the chat loop first** — fastest path to a working demo
4. **Parallel-track the Rust agent runtime** — longest lead time component
