# SKILL.md – Kaspa Mesh Agent

> **Goal:** Give an autonomous agent (or human user) the ability to sign Kaspa transactions off-grid, coordinate with a mesh swarm, and query Kaspa knowledge — all over LR2021/FLRC LoRa radio.

---

## Skill Overview

| Field | Value |
|-------|-------|
| **Name** | `kaspa_mesh_agent` |
| **Category** | Crypto / Mesh Networking / Agent Coordination |
| **Version** | `0.1.0` |
| **License** | MIT |
| **Source** | <https://github.com/yourname/kaspa_mesh_agent> |
| **Dependencies** | `kaspa`, `meshtastic`, `sentence-transformers`, `faiss-cpu`, `nltk`, `requests`, `pycryptodome` |
| **Runtime** | Python 3.9+ (CPU only; GPU optional for embeddings) |
| **Persistence** | JSON state file + encrypted wallet files (`.bin`) |

---

## Public API

| Method | Signature | Description |
|--------|-----------|-------------|
| **`load()`** | `load(force: bool = False) → dict` | Initialise Meshtastic interface, Kaspa RPC (if gateway), and RAG knowledge base. |
| **`qa()`** | `qa(question: str, max_tokens: int = 256) → str` | Retrieval-augmented QA using Kaspa knowledge + OpenRouter LLM. |
| **`coordinate_task()`** | `coordinate_task(mission: str) → dict` | Self-organising role proposal (Signer, Gateway, Coordinator, Helper, Abstain). |
| **`send_over_mesh()`** | `send_over_mesh(payload: dict, destination: int) → bool` | Chunk and send any payload over LoRa mesh (FLRC or classic). |
| **`create_unsigned_tx()`** | `create_unsigned_tx(to: str, amount: int, fee: int) → dict` | Build an unsigned Kaspa transaction. |
| **`sign_tx()`** | `sign_tx(unsigned_hex: str, wallet_path: str, password: str) → str` | Air-gapped signing — returns raw signed tx hex. |
| **`broadcast_tx()`** | `broadcast_tx(signed_hex: str) → dict` | Gateway-only: submit signed tx to Kaspa network via RPC. |
| **`start_listener()`** | `start_listener() → None` | Start async mesh listener for incoming chunked messages. |
| **`metadata()`** | `metadata() → dict` | Return agent metadata (title, version, URL). |

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

    F --> N[sign_tx + send_over_mesh]
    N --> O[Chunk → LoRa → Gateway]
    O --> P[broadcast_tx → Kaspa RPC]
```

---

## Installation

```bash
git clone https://github.com/yourname/kaspa_mesh_agent.git
cd kaspa_mesh_agent

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

agent = KaspaMeshAgent(node_type="general", use_flrc=True)
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
| **Embedding model** | Edit `SentenceTransformer("all-MiniLM-L6-v2")` in the agent |
| **LLM model** | Change `"model": "openai/gpt-4o-mini"` in `qa()` / `coordinate_task()` |
| **Chunk size** | Edit `DEFAULT_CHUNK_FLRC = 1200` or `DEFAULT_CHUNK_CLASSIC = 230` |
| **RAG depth** | Change `k=3` in `qa()` to retrieve more context |
| **Derivation path** | Edit `"m/44/111111/0/0/0"` in `kaspa_wallet.py` |

---

## Using from an Agent Prompt

```
🧠 System: You have access to the skill `kaspa_mesh_agent`.
🧠 User: Send 50 KAS to kaspa:qqexample...
🧠 Assistant (tool call):
{
  "name": "kaspa_mesh_agent.KaspaMeshAgent.create_unsigned_tx",
  "arguments": {"to_address": "kaspa:qqexample...", "amount_sompi": 5000000000}
}
🧠 Assistant (tool call):
{
  "name": "kaspa_mesh_agent.sign_tx",
  "arguments": {"unsigned_hex": "...", "wallet_path": "wallet.bin", "password": "..."}
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
│   ├── kaspa_wallet.py              # Wallet + signing
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

Expected: **7 passed** — agent load/QA, coordination, listener reassembly, wallet encryption, keypair derivation.

---

## Summary

The `kaspa_mesh_agent` skill turns any Python environment with a LoRa radio into a **resilient, self-organising Kaspa transaction agent**. It works completely off-grid, uses the official Kaspa SDK for real signing, and leverages LLM reasoning for autonomous coordination.
