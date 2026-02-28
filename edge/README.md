# Sovereign Edge Agent

A lightweight, self-contained AI agent for disconnected, tactical, and resource-constrained environments. Part of the Sovereign AI Hub platform (Phase 8).

## Quick Start

### 1. Install

```bash
# From pre-built binaries
./install.sh

# Or build from source
make build
sudo install bin/sovereign-edge /usr/local/bin/
```

### 2. Add a Model

Place a GGUF model file in the models directory:

```bash
cp my-model-Q4_K_M.gguf ~/.sovereign-edge/models/
sovereign-edge config default_model_file my-model-Q4_K_M.gguf
```

### 3. Run

```bash
# Start the API server
sovereign-edge serve

# Or use interactive chat
sovereign-edge chat
```

### 4. Connect to Hub (optional)

Register the device on the hub (Admin > Edge Devices), then configure:

```bash
sovereign-edge config hub_url https://hub.example.com:8888
sovereign-edge config agent_id edge-alpha-01
sovereign-edge config api_key sov-edge-xxxx
sovereign-edge sync
```

## CLI Commands

| Command  | Description |
|----------|-------------|
| `serve`  | Start local HTTP API server (default port 8899) |
| `sync`   | Manually trigger sync with the hub |
| `chat`   | Interactive terminal chat |
| `status` | Show agent status, models, sync state |
| `config` | Show/set configuration (`config key value`) |

## Configuration Reference

Configuration is loaded from `~/.sovereign-edge/config.yaml` and can be overridden with environment variables prefixed `SOVEREIGN_EDGE_`.

| Key | Default | Description |
|-----|---------|-------------|
| `hub_url` | _(empty)_ | URL of the Sovereign AI Hub |
| `agent_id` | _(empty)_ | Unique agent identifier (assigned by hub) |
| `agent_name` | `edge-agent` | Human-readable name |
| `api_key` | _(empty)_ | API key for hub authentication |
| `model_path` | `~/.sovereign-edge/models` | Directory containing GGUF model files |
| `data_dir` | `~/.sovereign-edge/data` | Directory for SQLite database |
| `listen_addr` | `0.0.0.0:8899` | HTTP server listen address |
| `sync_interval` | `5m` | Automatic sync interval (Go duration) |
| `llm_backend` | `embedded` | `embedded` (llama-cli subprocess) or `remote` (HTTP) |
| `llm_remote_url` | `http://127.0.0.1:8080` | URL of local llama.cpp server |
| `llm_context_size` | `4096` | Context window size |
| `llm_threads` | `4` | CPU threads for inference |
| `llm_gpu_layers` | `0` | GPU layers (0 = CPU only) |
| `default_model_file` | _(empty)_ | Default GGUF file to load |

## API Endpoints

The edge agent exposes an OpenAI-compatible API:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/chat/completions` | API key | Chat completion (streaming supported) |
| GET | `/v1/models` | API key | List local models |
| POST | `/api/search` | API key | Search local knowledge cache |
| GET | `/api/status` | API key | Agent status |
| POST | `/api/sync` | API key | Trigger hub sync |
| GET | `/health` | None | Health check |

## Sync Protocol

The edge agent synchronises with the hub using a simple delta-based protocol:

1. **Conversations (push)**: Local conversations not yet uploaded are sent to the hub via `POST /api/edge/sync/conversations`.
2. **Knowledge (pull)**: New knowledge chunks since the last sync timestamp are downloaded via `GET /api/edge/sync/knowledge`.
3. **Config (pull)**: Current policy and configuration are pulled via `GET /api/edge/sync/config`.
4. **Models (pull)**: Available model metadata is checked via `GET /api/edge/sync/models`.

Key properties:
- **Idempotent**: Every sync operation is safe to retry.
- **Server-authoritative**: On conflict, the hub wins.
- **Offline-tolerant**: The agent operates fully offline; sync resumes when connectivity returns.
- **Delta-based**: Only changes since the last sync are transferred, tracked per-resource via `last_sync_timestamp`.

## Supported Platforms

| OS | Architecture | Binary |
|----|-------------|--------|
| Linux | x86_64 | `sovereign-edge-linux-amd64` |
| Linux | ARM64 | `sovereign-edge-linux-arm64` |
| macOS | x86_64 | `sovereign-edge-darwin-amd64` |
| macOS | ARM64 (Apple Silicon) | `sovereign-edge-darwin-arm64` |

## Docker

```bash
docker build -t sovereign-edge .
docker run -p 8899:8899 -v ~/.sovereign-edge:/home/edge/.sovereign-edge sovereign-edge
```

## Troubleshooting

**"no model files found"**
Place a `.gguf` file in `~/.sovereign-edge/models/` and set `default_model_file` in config.

**"llama-cli: executable file not found"**
The embedded backend requires `llama-cli` on the PATH. Install llama.cpp or switch to `llm_backend: remote`.

**Sync fails with "hub_url not configured"**
Set the hub URL: `sovereign-edge config hub_url https://hub:8888`

**Sync fails with "unauthorized"**
Register the device on the hub and configure the API key: `sovereign-edge config api_key <key>`

**Database locked errors**
The SQLite database uses WAL mode for concurrent access. If you see lock errors, ensure only one `sovereign-edge serve` process is running.

**Port 8899 already in use**
Change the listen address: `sovereign-edge config listen_addr 0.0.0.0:9899`
