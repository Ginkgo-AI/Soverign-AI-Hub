# Sovereign AI Hub — Architecture

## Overview

Sovereign AI Hub is a Docker-based, air-gapped AI platform for government/enterprise. It provides a self-hosted alternative to cloud AI services with full data sovereignty, running entirely on local infrastructure.

### Tech Stack
- **Frontend**: Next.js 15 (App Router), TypeScript, Tailwind CSS, Zustand
- **Gateway**: FastAPI (Python 3.11+), async, SSE streaming
- **Database**: PostgreSQL (via SQLAlchemy async), Qdrant (vector search)
- **LLM Backend**: vLLM (OpenAI-compatible API)
- **Queue**: Redis Streams (document processing, async jobs)
- **Container**: Docker Compose orchestration

---

## Core Architecture

### Request Flow
```
Browser → Next.js (3000) → Gateway API (8888) → vLLM (8001/8002)
                                    ↕
                              PostgreSQL + Qdrant + Redis
```

### Key Patterns
- **SSE Streaming**: Chat uses Server-Sent Events for real-time token streaming and tool execution events
- **Agentic Tool Loop**: Gateway runs a multi-turn agent loop — LLM calls tools, gateway executes them, feeds results back until the LLM produces a final response
- **Feature Flags**: All major features have enable/disable flags in `gateway/app/config.py`
- **Model Mixins**: All models use `UUIDMixin` + `TimestampMixin` from `models/base.py`
- **Async Sessions**: Database access via `async_session` from `database.py`

---

## Feature Phases (Osaurus-Inspired)

All 7 phases have been implemented. Each is feature-flagged and error-isolated.

### Phase A: Tool Plugin System
Extensible tool registry. Plugins are stored in PostgreSQL, compiled at startup, and registered into the `ToolRegistry` singleton.

**Key files**: `models/plugin.py`, `services/plugin_manager.py`, `routers/plugins.py`

### Phase B: Four-Layer Memory System
1. **User Memory** — preferences/facts (PostgreSQL)
2. **Working Memory** — active conversation context (message history)
3. **Conversation Summaries** — LLM-compressed history (PostgreSQL + Qdrant)
4. **Knowledge Graph** — subject-predicate-object triples with contradiction detection

**Key files**: `models/memory.py`, `services/memory_service.py`, `routers/memory.py`

### Phase C: Skills/Capability Registry
Packaged system prompts + tool configs + examples. Two-phase loading: lightweight catalog for browsing, full definition loaded on activation. Default skills seeded at startup.

**Key files**: `models/skill.py`, `services/skill_service.py`, `routers/skills.py`

### Phase D: Work Mode (Multi-Step Task Execution)
LLM decomposes complex objectives into dependency-tracked subtasks. Topological execution with progress tracking.

**Key files**: `models/work_task.py`, `services/work_mode.py`, `routers/work_mode.py`

### Phase E: Cryptographic Agent Identity
Ed25519 signing of agent actions. Every tool call and response is hashed and signed for audit/compliance.

**Key files**: `models/agent_identity.py`, `services/agent_identity.py`

### Phase F: Automation (Schedules & Watchers)
APScheduler cron jobs + watchfiles filesystem monitors. Triggers agent execution or document ingestion.

**Key files**: `models/automation.py`, `services/scheduler_service.py`, `services/watcher_service.py`, `routers/automation.py`

### Phase G: MCP Server Compatibility
JSON-RPC 2.0 over SSE transport. Exposes tools, RAG collections (as resources), and skills (as prompts) to MCP clients like Cursor and Claude Desktop.

**Key files**: `routers/mcp.py`, `services/mcp_server.py`, `schemas/mcp.py`

---

## Chart Rendering (Recharts)

Charts are rendered client-side using Recharts, inspired by the Metis project's approach.

### How It Works
1. **LLM outputs JSON data** — guided by tool descriptions to use `print(json.dumps(data))` instead of matplotlib
2. **Detection** — `chartUtils.ts` detects chart-compatible JSON in tool results and markdown code blocks
3. **Rendering** — `AutoChart.tsx` (dynamically imported with `ssr: false`) renders interactive bar/line/pie/area charts

### Supported Data Formats
- **Row format**: `[{date: "2024-01", AAPL: 150}, ...]`
- **Columnar format**: `{dates: [...], AAPL: [...], GOOG: [...]}` (auto-converted to rows)
- **Key-value**: `{A: 10, B: 20}` (rendered as pie chart)
- **Explicit config**: `{type: "bar", data: [...], xKey: "date", yKeys: ["value"]}`

### Key Files
- `frontend/src/components/chat/chartUtils.ts` — SSR-safe detection/analysis (no recharts dependency)
- `frontend/src/components/chat/AutoChart.tsx` — Client-only Recharts rendering
- `frontend/src/components/chat/MarkdownRenderer.tsx` — Chart detection in code blocks
- `frontend/src/components/chat/MessageBubble.tsx` — Chart detection in tool results

---

## Tool Execution

### Built-in Tools
| Tool | Category | Approval |
|------|----------|----------|
| `rag_search` | search | No |
| `python_exec` | code_execution | Yes |
| `bash_exec` | code_execution | Yes |
| `file_read` / `file_write` | file_ops | No / Yes |
| `http_request` | http | No |
| `sql_query` | data_analysis | Yes |
| `calculator` | data_analysis | No |
| `vision_analyze` | multimodal | No |
| `transcribe_audio` | multimodal | No |
| `text_to_speech` | multimodal | No |
| `generate_image` | multimodal | No |
| `code_analyze` / `code_explain` / `code_generate` | code_execution | No |
| `git_diff` / `git_commit_message` | code_execution | No |

### Python Exec Enhancements
- **Auto-print**: AST-based detection of dangling expressions — automatically wraps with `print()` (like IPython/Jupyter)
- **Image collection**: Detects new image files in workspace after execution, returns as base64 data URIs
- **Sandboxed**: Runs in subprocess with timeout, workspace directory as CWD

---

## Database Schema

Tables are created via `Base.metadata.create_all()` at startup. For column additions to existing tables, manual `ALTER TABLE` is required (no Alembic migrations yet).

### Core Tables
- `users`, `conversations`, `messages` — chat foundation
- `models` — LLM model registry
- `rag_collections`, `rag_documents`, `rag_chunks` — document ingestion
- `agent_definitions`, `agent_executions` — agent configuration and runs
- `audit_log` — action audit trail

### Feature Tables
- `plugin_tools` — Phase A
- `user_memories`, `conversation_summaries`, `knowledge_entries` — Phase B
- `skills` — Phase C
- `work_tasks` — Phase D
- `agent_actions` — Phase E
- `schedules`, `watchers`, `automation_logs` — Phase F

---

## Docker Networking

The gateway runs on the `local_ai_default` network. When vLLM runs on a separate Docker network (e.g., `metis_2_metis-network`), use the host gateway IP (`172.25.0.1` or equivalent) with `VLLM_HOST` / `VLLM_PORT` environment variables.

---

## Cross-Cutting Concerns

- **Air-gap safe**: All features work offline. Memory extraction uses local LLM. Plugins load from local files.
- **Error isolation**: Each service catches its own exceptions. Feature failures must not break core chat.
- **Feature flags**: Disabled features skip router registration entirely.
- **Auth**: Optional auth via `get_optional_user` for public read endpoints, `get_current_user` for write endpoints.

---

## Future Considerations

- **Alembic migrations**: Currently using `create_all()` + manual ALTER. Should adopt Alembic for production.
- **Memory extraction tuning**: Currently LLM-based — quality depends on model capability.
- **Plugin sandboxing**: Current restriction is import-based. Could add process-level isolation.
- **MCP Streamable HTTP**: Current implementation uses SSE transport. MCP spec is moving toward streamable HTTP.
