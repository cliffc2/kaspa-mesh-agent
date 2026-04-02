# Kaspa Mesh Agent

A self-organising Kaspa agent for LR2021 / FLRC LoRa mesh networks. Combines air-gapped transaction signing, chunked Meshtastic transport, and LLM-powered coordination into a single resilient off-grid crypto agent.

## Features

- **Mesh transport (FLRC-ready)**: Chunked message sending and automatic reassembly via Meshtastic. Supports both classic LoRa (230B chunks) and LR2021 FLRC (1200B chunks).
- **Air-gapped signing**: AES-256-GCM encrypted mnemonic storage. Private keys never touch the mesh — only signed raw transactions travel over radio.
- **Gateway broadcast**: Gateway nodes reassemble incoming transactions and submit them to the Kaspa network via RPC.
- **Self-organising coordination**: LLM-driven role proposal (Signer, Gateway, Coordinator, Helper) via OpenRouter. No fixed hierarchy — roles emerge autonomously.
- **RAG-powered QA**: Lightweight knowledge base with sentence-transformers + FAISS for semantic search over Kaspa documentation.
- **Rich-media support**: Encode/decode PNG/WAV files for FLRC transport.
- **Real Kaspa SDK integration**: Uses the official `kaspa` Python package (bindings to rusty-kaspa) for mnemonic derivation, keypair generation, and transaction signing.

## Architecture

```
kaspa_mesh_agent/
├── kaspa_mesh_agent/          # Python package
│   ├── __init__.py            # Public API exports
│   ├── kaspa_mesh_agent_lr2021.py  # Core agent class (FLRC-optimised)
│   ├── mesh_listener.py       # Async chunk reassembly listener
│   ├── kaspa_wallet.py        # AES-GCM encrypted wallet + Kaspa SDK signing
│   ├── media_utils.py         # PNG/WAV encode/decode helpers
│   └── version.py             # Package version
├── tests/
│   ├── test_agent.py          # Agent load, QA, coordination tests
│   ├── test_listener.py       # Chunk reassembly tests
│   └── test_wallet.py         # Wallet encrypt/decrypt + keypair derivation
├── example_flow.yaml          # ii-Agent YAML pipeline
├── requirements.txt
├── README.md
└── .gitignore
```

## Quick Start

```bash
# Clone the repo
git clone https://github.com/yourname/kaspa_mesh_agent.git
cd kaspa_mesh_agent

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests (7 tests should pass)
pytest -v
```

## Usage

### Basic Agent

```python
from kaspa_mesh_agent import KaspaMeshAgent

agent = KaspaMeshAgent(node_type="general", use_flrc=True)
agent.load()

# Ask a question about Kaspa
answer = agent.qa("How does GHOSTDAG work?")
print(answer)
```

### Create a Wallet

```python
from kaspa import Mnemonic
from kaspa_mesh_agent import save_wallet, load_wallet, get_address
from kaspa import NetworkType

# Generate a new mnemonic
m = Mnemonic.random()
print("Mnemonic:", m.phrase)

# Save encrypted to disk
save_wallet(m.phrase, "my_wallet.bin", "strong-password")

# Load and get address
loaded = load_wallet("my_wallet.bin", "strong-password")
addr = get_address(loaded, NetworkType.Mainnet)
print("Address:", addr)
```

### Signer Node (Air-gapped)

```python
import asyncio
from kaspa_mesh_agent import KaspaMeshAgent, load_wallet, get_keypair
from kaspa import NetworkType

# Load wallet
mnemonic = load_wallet("my_wallet.bin", "password")
kp = get_keypair(mnemonic)
print("Signing address:", kp.to_address(NetworkType.Mainnet))

# Create agent and send signed tx over mesh
agent = KaspaMeshAgent(node_type="signer", use_flrc=True)
agent.load()

# In production: build real transaction with kaspa SDK
# tx = create_transaction(utxo_source, outputs, fee)
# signed = sign_transaction(tx, kp)
# agent.send_over_mesh({"type": "signed_tx", "data": signed})
```

### Gateway Node

```python
import asyncio
from kaspa_mesh_agent import KaspaMeshAgent

gw = KaspaMeshAgent(node_type="gateway", use_flrc=True)
gw.load()
asyncio.run(gw.start_listener())  # Listens for incoming transactions
```

### Self-Organising Coordination

```python
import asyncio
from kaspa_mesh_agent import KaspaMeshAgent

agent = KaspaMeshAgent(node_type="general")
agent.load()

# Ask the agent to propose a role for a mission
decision = await agent.coordinate_task("Send 100 KAS to kaspa:qqexample...")
print(decision)
# {"role": "Gateway", "reason": "I have internet access", "next_action": "broadcast tx"}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | API key for LLM-powered QA and coordination |
| `MESHTASTIC_SERIAL_PORT` | Serial port path to Meshtastic device (e.g. `/dev/ttyUSB0`) |

## Hardware

- **LR2021 FLRC**: Seeed Studio LR2021 Evaluation Kit or G-NiceRF LoRa2021 modules (up to 2.6 Mbps)
- **Classic LoRa**: Any Meshtastic-compatible board (Heltec, LilyGo, ESP32)
- **Gateway**: Raspberry Pi + LoRa HAT + internet connection + Kaspa node (kaspad)

## Dependencies

| Package | Purpose |
|---------|---------|
| `kaspa` | Official Kaspa SDK (rusty-kaspa bindings) |
| `meshtastic` | Meshtastic radio communication |
| `sentence-transformers` | Text embeddings for RAG |
| `faiss-cpu` | Vector similarity search |
| `pycryptodome` | AES-256-GCM wallet encryption |
| `nltk` | Text tokenisation |
| `requests` | HTTP client for OpenRouter API |
| `pytest` / `pytest-asyncio` | Test framework |

## Tests

```bash
pytest -v
```

All 7 tests pass:
- `test_load_and_qa` — Agent initialisation and RAG-powered QA
- `test_coordinate_task` — LLM-driven role proposal
- `test_metadata` — Agent metadata endpoint
- `test_reassembly` — Chunked message reassembly
- `test_encrypt_decrypt_roundtrip` — Wallet AES-GCM encryption
- `test_derive_keypair_and_address` — Kaspa keypair derivation
- `test_deterministic_derivation` — Deterministic address generation

## License

MIT
