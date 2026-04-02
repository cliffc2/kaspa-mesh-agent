# SKILL.md – Kaspa Mesh Agent

> **Goal:** Give an autonomous agent (or human user) the ability to sign Kaspa transactions off-grid, coordinate with a mesh swarm, and query Kaspa knowledge — all over LR2021/FLRC LoRa radio.

---

## Skill Overview

| Field | Value |
|-------|-------|
| **Name** | `kaspa_mesh_agent` |
| **Category** | Crypto / Mesh Networking / Agent Coordination |
| **Version** | `0.2.0` |
| **License** | MIT |
| **Source** | <https://github.com/cliffc2/kaspa-mesh-agent> |
| **Dependencies** | `kaswallet-cli` (Rust), `kaspa`, `meshtastic`, `sentence-transformers`, `faiss-cpu`, `nltk`, `requests` |
| **Runtime** | Python 3.9+ (CPU only; GPU optional for embeddings) |
| **Persistence** | JSON state file + kaswallet daemon keys |

---

## Prerequisites

### 1. Install kaswallet (IgraLabs)

```bash
git clone https://github.com/IgraLabs/kaswallet.git
cd kaswallet
./install.sh
```

### 2. Create Wallet & Start Daemon

```bash
kaswallet-create --testnet
kaswallet-daemon --testnet --server='grpc://<testnet-node>:<port>'
```

---

## Public API

| Method | Signature | Description |
|--------|-----------|-------------|
| **`load()`** | `load(force: bool = False) → dict` | Initialise Meshtastic interface, Kaspa RPC (if gateway), and RAG knowledge base. |
| **`qa()`** | `qa(question: str, max_tokens: int = 256) → str` | Retrieval-augmented QA using Kaspa knowledge + OpenRouter LLM. |
| **`coordinate_task()`** | `coordinate_task(mission: str) → dict` | Self-organising role proposal (Signer, Gateway, Coordinator, Helper, Abstain). |
| **`send_over_mesh()`** | `send_over_mesh(payload: dict, destination: int) → bool` | Chunk and send any payload over LoRa mesh (FLRC or classic). |
| **`create_unsigned_tx()`** | `create_unsigned_tx(to: str, amount: int, fee: int) → dict` | Build unsigned tx via kaswallet-cli. |
| **`sign_tx()`** | `sign_tx(tx_input: str) → dict` | Sign tx via kaswallet-cli (air-gapped). |
| **`broadcast_tx()`** | `broadcast_tx(tx_input: str) → dict` | Broadcast via kaswallet-cli or RPC fallback. |
| **`start_listener()`** | `start_listener() → None` | Start async mesh listener for incoming chunked messages. |
| **`metadata()`** | `metadata() → dict` | Return agent metadata (title, version, URL). |

### Standalone Wallet Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| **`get_balance()`** | `get_balance(network: str) → dict` | Get wallet balance |
| **`get_addresses()`** | `get_addresses(network: str) → list` | List all wallet addresses |
| **`new_address()`** | `new_address(network: str) → str` | Generate new address |
| **`send()`** | `send(to: str, amount: int, fee: int) → dict` | All-in-one send (create + sign + broadcast) |
| **`get_daemon_version()`** | `get_daemon_version(network: str) → str` | Get kaswallet daemon version |

---

## Internal Workflow

```mermaid
flowchart TD
    A[Agent initialised] --> B{load()}
    B --> C[Connect Meshtastic]
    B --> D[Connect Kaspa RPC if gateway]
    B --> E[Build RAG index]
    E --> F[Ready for operations]

    F --> G[qa question]
    G --> H[FAISS retrieve top-k]
    H --> I[Build prompt + OpenRouter]
    I --> J[Return answer]

    F --> K[coordinate_task mission]
    K --> L[LLM proposes role]
    L --> M[Return JSON decision]

    F --> N[create_unsigned_tx via kaswallet-cli]
    N --> O[sign_tx via kaswallet-cli]
    O --> P[send_over_mesh → LoRa → Gateway]
    P --> Q[broadcast_tx → Kaspa network]
```

---

## Installation

```bash
git clone https://github.com/cliffc2/kaspa-mesh-agent.git
cd kaspa-mesh-agent

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Set environment variables:
```bash
export OPENROUTER_API_KEY="sk-or-..."
export MESHTASTIC_SERIAL_PORT="/dev/ttyUSB0"   # optional
```

---

## Quick-Start Demo

```python
from kaspa_mesh_agent import KaspaMeshAgent

agent = KaspaMeshAgent(node_type="general", use_flrc=True, network="testnet")
print(agent.load())

# QA
print(agent.qa("What is GHOSTDAG?"))

# Coordination
import asyncio
decision = asyncio.run(agent.coordinate_task("Send 100 KAS to kaspa:qqexample"))
print(decision)
```

---

## Configuration

| What to tweak | How |
|---------------|-----|
| **FLRC mode** | `use_flrc=True` (default) for LR2021, `False` for classic LoRa |
| **Network** | `network="testnet"` or `"mainnet"`, `"devnet"`, `"simnet"` |
| **Embedding model** | Edit `SentenceTransformer("all-MiniLM-L6-v2")` in the agent |
| **LLM model** | Change `"model": "openai/gpt-4o-mini"` in `qa()` / `coordinate_task()` |
| **Chunk size** | Edit `DEFAULT_CHUNK_FLRC = 1200` or `DEFAULT_CHUNK_CLASSIC = 230` |
| **RAG depth** | Change `k=3` in `qa()` to retrieve more context |

---

## Using from an Agent Prompt

```
🧠 System: You have access to the skill `kaspa_mesh_agent`.
🧠 User: Send 50 KAS to kaspa:qqexample...
🧠 Assistant (tool call):
{
  "name": "kaspa_mesh_agent.create_unsigned_tx",
  "arguments": {"to_address": "kaspa:qqexample...", "amount_sompi": 5000000000}
}
🧠 Assistant (tool call):
{
  "name": "kaspa_mesh_agent.sign_tx",
  "arguments": {"unsigned_tx_input": "tx_id_from_previous_step"}
}
🧠 Assistant (tool call):
{
  "name": "kaspa_mesh_agent.KaspaMeshAgent.send_over_mesh",
  "arguments": {"payload": {"type": "signed_tx", "data": "..."}}
}
```

---

## File Layout

```
kaspa_mesh_agent/
├── kaspa_mesh_agent/
│   ├── __init__.py
│   ├── kaspa_mesh_agent_lr2021.py   # Core agent
│   ├── mesh_listener.py             # Async reassembly
│   ├── kaspa_wallet.py              # kaswallet-cli wrapper
│   ├── media_utils.py               # Media encode/decode
│   └── version.py
├── tests/
│   ├── test_agent.py
│   ├── test_listener.py
│   └── test_wallet.py
├── example_flow.yaml
├── requirements.txt
├── README.md
├── SKILL.md
└── .gitignore
```

---

## Testing

```bash
pytest -v
```

Expected: **17 passed** — agent load/QA/coordination/metadata/tx operations, listener reassembly, wallet CLI wrapper (balance, addresses, send, broadcast, version, error handling, network parameter).

---

## Summary

The `kaspa_mesh_agent` skill turns any Python environment with a LoRa radio into a **resilient, self-organising Kaspa transaction agent**. It uses [IgraLabs kaswallet](https://github.com/IgraLabs/kaswallet) — a lightweight Rust gRPC wallet daemon — for secure transaction signing, and leverages LLM reasoning for autonomous swarm coordination. Works completely off-grid.
