# Kaspa Mesh Agent

A self-organising Kaspa agent for LR2021 / FLRC LoRa mesh networks. Combines air-gapped transaction signing via `kaswallet-cli`, chunked Meshtastic transport, and LLM-powered coordination into a single resilient off-grid crypto agent.

## Features

- **Mesh transport (FLRC-ready)**: Chunked message sending and automatic reassembly via Meshtastic. Supports both classic LoRa (230B chunks) and LR2021 FLRC (1200B chunks).
- **Air-gapped signing**: Uses [IgraLabs kaswallet](https://github.com/IgraLabs/kaswallet) — a Rust-based gRPC wallet daemon. Private keys never touch the mesh; only signed transactions travel over radio.
- **Gateway broadcast**: Gateway nodes reassemble incoming transactions and submit them to the Kaspa network via RPC or `kaswallet-cli`.
- **Self-organising coordination**: LLM-driven role proposal (Signer, Gateway, Coordinator, Helper) via OpenRouter. No fixed hierarchy — roles emerge autonomously.
- **RAG-powered QA**: Lightweight knowledge base with sentence-transformers + FAISS for semantic search over Kaspa documentation.
- **Rich-media support**: Encode/decode PNG/WAV files for FLRC transport.
- **Testnet ready**: Configurable network parameter (`testnet`, `mainnet`, `devnet`, `simnet`).

## Architecture

```
kaspa_mesh_agent/
├── kaspa_mesh_agent/          # Python package
│   ├── __init__.py            # Public API exports
│   ├── kaspa_mesh_agent_lr2021.py  # Core agent class (FLRC-optimised)
│   ├── mesh_listener.py       # Async chunk reassembly listener
│   ├── kaspa_wallet.py        # kaswallet-cli subprocess wrapper
│   ├── media_utils.py         # PNG/WAV encode/decode helpers
│   └── version.py             # Package version
├── tests/
│   ├── test_agent.py          # Agent load, QA, coordination, tx tests
│   ├── test_listener.py       # Chunk reassembly tests
│   └── test_wallet.py         # kaswallet-cli wrapper tests
├── example_flow.yaml          # ii-Agent YAML pipeline
├── requirements.txt
├── README.md
├── SKILL.md
└── .gitignore
```

## Prerequisites

### 1. Install kaswallet (IgraLabs)

```bash
git clone https://github.com/IgraLabs/kaswallet.git
cd kaswallet
./install.sh
```

This installs `kaswallet-create`, `kaswallet-daemon`, and `kaswallet-cli` to `~/.cargo/bin`.

### 2. Create a Testnet Wallet

```bash
# Create new wallet
kaswallet-create --testnet

# Or import existing mnemonic
kaswallet-create --testnet --import
```

### 3. Start the Wallet Daemon

```bash
# Point to a testnet Kaspa node
kaswallet-daemon --testnet --server='grpc://<testnet-node>:<port>'
```

Keep this running in the background. The agent communicates with it via `kaswallet-cli`.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/cliffc2/kaspa-mesh-agent.git
cd kaspa-mesh-agent

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests (17 tests should pass)
pytest -v
```

## Usage

### Basic Agent

```python
from kaspa_mesh_agent import KaspaMeshAgent

agent = KaspaMeshAgent(node_type="general", use_flrc=True, network="testnet")
agent.load()

# Ask a question about Kaspa
answer = agent.qa("How does GHOSTDAG work?")
print(answer)
```

### Wallet Operations

```python
from kaspa_mesh_agent import (
    get_balance, get_addresses, new_address,
    create_unsigned_tx, sign_tx, broadcast_tx, send
)

# Check balance
balance = get_balance(network="testnet")
print(balance)

# Generate new address
addr = new_address(network="testnet")
print(addr)

# Send transaction (all-in-one)
result = send("kaspa:qqexample...", 10000000, network="testnet")
print(result)
```

### Air-Gapped Signing Flow

```python
import asyncio
from kaspa_mesh_agent import KaspaMeshAgent, create_unsigned_tx, sign_tx, broadcast_tx

async def air_gapped_flow():
    # 1. Create unsigned transaction (on any device)
    unsigned = await create_unsigned_tx("kaspa:qqexample...", 10000000, network="testnet")
    print("Unsigned:", unsigned)

    # 2. Sign on air-gapped device (kaswallet-cli handles keys securely)
    signed = await sign_tx(unsigned["tx_id"], network="testnet")
    print("Signed:", signed)

    # 3. Broadcast via gateway
    result = await broadcast_tx(signed["tx_id"], network="testnet")
    print("Broadcast:", result)

asyncio.run(air_gapped_flow())
```

### Signer Node (Air-gapped)

```python
import asyncio
from kaspa_mesh_agent import KaspaMeshAgent

agent = KaspaMeshAgent(node_type="signer", use_flrc=True, network="testnet")
agent.load()

# Create and sign transaction
unsigned = await agent.create_unsigned_tx("kaspa:qqexample...", 10000000)
signed = await agent.sign_tx(unsigned["tx_id"])

# Send signed tx over mesh to gateway
agent.send_over_mesh({"type": "signed_tx", "data": signed["tx_id"]})
```

### Gateway Node

```python
import asyncio
from kaspa_mesh_agent import KaspaMeshAgent

gw = KaspaMeshAgent(node_type="gateway", use_flrc=True, network="testnet")
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

### Signer Node (Air-gapped)
- **RAM**: 2 GB minimum, 4 GB recommended
- **Storage**: 8 GB minimum
- **CPU**: Raspberry Pi Zero 2W+ or any ARM/x86
- **LoRa Radio**: Any Meshtastic board (Heltec V3, LilyGo T-Beam)

### Gateway Node
- **RAM**: 4 GB minimum, 8 GB recommended
- **Storage**: 32 GB minimum (128 GB if running local Kaspa node)
- **CPU**: Raspberry Pi 4/5 or x86 mini-PC
- **Network**: Ethernet (stable connection)
- **LoRa Radio**: Seeed LR2021 Eval Kit (FLRC 2.6 Mbps) or any Meshtastic board

### LoRa Radio Hardware

| Board | Price | Notes |
|-------|-------|-------|
| **Heltec V3** (ESP32 + LoRa) | ~$25 | Classic LoRa, Meshtastic-ready |
| **LilyGo T-Beam** (ESP32 + GPS) | ~$35 | Built-in GPS, good for mobile |
| **Seeed LR2021 Eval Kit** | ~$45 | **FLRC 2.6 Mbps** — what the agent is optimised for |
| **G-NiceRF LoRa2021 module** | ~$30 | Module only, needs carrier board |

## Dependencies

| Package | Purpose |
|---------|---------|
| `kaswallet-cli` | Rust-based Kaspa wallet CLI (external, install separately) |
| `kaspa` | Official Kaspa SDK (rusty-kaspa bindings) for RPC |
| `meshtastic` | Meshtastic radio communication |
| `sentence-transformers` | Text embeddings for RAG |
| `faiss-cpu` | Vector similarity search |
| `nltk` | Text tokenisation |
| `requests` | HTTP client for OpenRouter API |
| `pytest` / `pytest-asyncio` | Test framework |

## Tests

```bash
pytest -v
```

All 17 tests pass:
- **Agent** (6): load, QA, coordination, metadata, create tx, sign tx, broadcast tx
- **Listener** (1): chunk reassembly
- **Wallet** (10): balance, addresses, new address, create/sign/broadcast/send tx, daemon version, error handling, network parameter

## License

MIT
