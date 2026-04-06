# SKILL.md – Kaspa Mesh Agent (v0.3.0)

> **Goal:** Autonomous AI swarm for KAS-ETH atomic swaps with THORChain-style fees, LP management, and mesh-resilient transport.

---

## Skill Overview

| Field | Value |
|-------|-------|
| **Name** | `kaspa_mesh_agent` |
| **Category** | Crypto / Mesh Networking / Atomic Swaps / Agent Coordination |
| **Version** | `0.3.0` |
| **License** | MIT |
| **Source** | <https://github.com/cliffc2/kaspa-mesh-agent> |
| **Dependencies** | `kaswallet-cli`, `kaspa-atomic-swap-cli`, `eth-swap-cli`, `kaspa`, `meshtastic`, `sentence-transformers`, `faiss-cpu`, `nltk`, `requests`, `web3.py` |
| **Runtime** | Python 3.11+ |
| **Persistence** | JSON state file + LP ledger (`lp-ledger.json`) |

---

## Architecture

```
Coordinator Agent (LLM + coordinate_task)
   ├── Kaspa Specialist → kaswallet-cli + kaspa-atomic-swap-cli
   ├── ETH Specialist → eth-swap-cli (THORChain fees + HTLC)
   ├── Monitor Agent → polls pool depth + prices + rebalance
   └── Gateway Agent → mesh/WebSocket relay + tx broadcast

Transport: Meshtastic LoRa FLRC (primary) + WebSocket (fallback)
Fee Model: THORChain CLP slip-based liquidity fee
LP Sharing: Proportional fee distribution to all liquidity providers
```

---

## Public API

### Core Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| **`load()`** | `load(force: bool = False) → dict` | Init mesh, RPC, RAG, pool manager |
| **`qa()`** | `qa(question: str, max_tokens: int = 256) → str` | RAG QA with Kaspa knowledge |
| **`coordinate_task()`** | `coordinate_task(mission: str, system_prompt: Optional[str] = None) → dict` | Self-organising role proposal |
| **`execute_atomic_swap()`** | `execute_atomic_swap(input_asset, output_asset, amount, counterparty, affiliate) → dict` | Full swap with secret generation + fee quote |
| **`send_over_mesh()`** | `send_over_mesh(payload: dict, destination: int) → bool` | Chunked LoRa transport |
| **`start_listener()`** | `start_listener() → None` | Async mesh listener |
| **`metadata()`** | `metadata() → dict` | Agent metadata |

### Wallet Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| **`create_unsigned_tx()`** | `create_unsigned_tx(to: str, amount: int, fee: int) → dict` | Build unsigned tx |
| **`sign_tx()`** | `sign_tx(tx_input: str) → dict` | Sign tx (air-gapped) |
| **`broadcast_tx()`** | `broadcast_tx(tx_input: str) → dict` | Broadcast tx |

### Atomic Swap Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| **`initiate_htlc()`** | `initiate_htlc(amount_sompi, claim_addr, secret_hash, timelock_blocks, from_addr) → dict` | Create HTLC on Kaspa |
| **`claim_htlc()`** | `claim_htlc(utxo, preimage) → dict` | Claim with preimage |
| **`refund_htlc()`** | `refund_htlc(utxo) → dict` | Refund after timelock |
| **`swap_status()`** | `swap_status(txid) → dict` | Check swap UTXO status |
| **`generate_secret()`** | `generate_secret() → dict` | Generate preimage + hash |

### Liquidity Pool Methods (via `self.pool_manager`)

| Method | Signature | Description |
|--------|-----------|-------------|
| **`add_liquidity()`** | `pool_manager.add_liquidity(lp_key, kas_added, eth_added) → dict` | Add liquidity, receive LP units |
| **`remove_liquidity()`** | `pool_manager.remove_liquidity(lp_key, percentage) → dict` | Withdraw proportional assets |
| **`get_proportional_share()`** | `pool_manager.get_proportional_share(lp_key) → dict` | Get LP share % |
| **`get_pool_depth()`** | `pool_manager.get_pool_depth() → dict` | Current KAS/ETH depth |
| **`update_pool_depth()`** | `pool_manager.update_pool_depth(kas, eth) → None` | Update from real balances |
| **`update_config()`** | `pool_manager.update_config(key, value) → dict` | Mimir-style param update |
| **`get_config()`** | `pool_manager.get_config() → dict` | Current fee config |
| **`distribute_liquidity_fee()`** | `pool_manager.distribute_liquidity_fee(fee, asset) → float` | Credit fee to pool |

---

## CLI Tools Registry

All CLIs output consistent JSON: `{"success": bool, "message": str, "data": {...}}`

### Kaspa CLI (`kaspa-atomic-swap-cli`)

| Command | Description |
|---------|-------------|
| `initiate --amount --to --secret-hash --timelock-blocks` | Create HTLC covenant |
| `claim --utxo --secret` | Claim with preimage |
| `refund --utxo` | Refund after timelock |
| `status --txid` | Check UTXO status |
| `monitor --wallet --interval` | Watch for incoming swaps |
| `show-script --secret-hash --timelock-blocks --refund-addr --claim-addr` | Debug covenant script |

### ETH CLI (`eth-swap-cli`)

| Command | Description |
|---------|-------------|
| `quote --in-asset --out-asset --amount [--affiliate]` | THORChain-style quote with slip fees |
| `swap --from-asset --to-asset --amount --secret-hash --counterparty --timelock` | Execute swap |
| `add-liquidity --kas-amount --eth-amount --lp-address [--asym]` | Add liquidity |
| `remove-liquidity --lp-address [--percentage]` | Remove liquidity |
| `pool-depth` | Show pool stats |
| `my-share --lp-address` | Show LP position |
| `claim --secret-hash --secret` | Claim HTLC |
| `refund --secret-hash` | Refund HTLC |
| `update-mimir --key --value` | Update config params |
| `list-tools` | Auto-discovery for agents |

### Kaspa Wallet (`kaswallet-cli`)

| Command | Description |
|---------|-------------|
| `balance --json` | Wallet balance |
| `new-address --json` | Generate address |
| `send --to --amount --json` | One-shot transfer |
| `create-unsigned-transaction --to --amount --json` | Build unsigned tx |
| `sign --input --json` | Sign tx |
| `broadcast --input --json` | Broadcast tx |

---

## THORChain Fee Model

### Slip-Based Liquidity Fee

```
fee = (x² × Y) / (x + X)²
```

- `x` = input swap amount
- `X` = input-side pool depth
- `Y` = output-side pool depth

### Fee Distribution

| Component | Default | Description |
|-----------|---------|-------------|
| **Liquidity Fee (slip)** | Variable | Scales with swap size vs pool depth |
| **Operator Cut** | 1.50% (150 bps) | Swarm operator revenue |
| **Affiliate Cut** | 0% (configurable) | Frontend/integrator share |
| **LP Share** | Remainder | Distributed proportionally to LP units |

### LP Earnings

Anyone providing liquidity earns proportional % of swap fees. Deeper pools → tighter spreads → more volume → higher total fees.

---

## Coordination System Prompt (Atomic Swaps)

```
You are the Coordinator of a THORChain-style KAS-ETH autonomous liquidity swarm.

Core Rules:
1. ALWAYS run `quote` first to get expected_output, liquidity_fee, slip_bps
2. Apply operator_cut + affiliate cut BEFORE locking
3. Lock fee-adjusted output amount on first chain
4. Wait for counterparty lock on second chain
5. Claim with secret (never send preimage over mesh until claim step)
6. Liquidity fee stays in pool (distributed to LPs proportionally)
7. For swaps >5% of pool depth, use streaming (split into 4-8 HTLCs)
8. Rebalance if one side >30% imbalance

Available tools:
- quote, swap, add-liquidity, remove-liquidity, pool-depth
- kaspa.initiate_htlc, kaspa.claim_htlc, kaspa.refund_htlc
- eth.lock, eth.claim, eth.refund
- generate_secret, monitor_swaps, fetch_price_oracle

Output ONLY valid JSON with: role, next_action, tool_calls[], reasoning
```

---

## Installation

```bash
# Clone repos
git clone https://github.com/cliffc2/kaspa-mesh-agent.git
cd kaspa-mesh-agent

# Build CLIs
cd ../kaspa-atomic-swap-cli && cargo build --release
cd ../IgraLabs/kaswallet && ./install.sh

# Python deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install web3.py click

# Environment
export OPENROUTER_API_KEY="sk-or-..."
export ETH_RPC_URL="https://sepolia.infura.io/v3/YOUR_KEY"
export HTLC_CONTRACT="0xYOUR_DEPLOYED_HTLC"
```

---

## Quick Start

```python
from kaspa_mesh_agent import KaspaMeshAgent

agent = KaspaMeshAgent(node_type="coordinator", network="testnet")
agent.load()

# Add liquidity
agent.pool_manager.add_liquidity(
    lp_key="kaspa:your_address",
    kas_added=Decimal('50000'),
    eth_added=Decimal('10')
)

# Execute swap
import asyncio
result = asyncio.run(agent.execute_atomic_swap(
    input_asset="KAS",
    output_asset="ETH",
    amount="1000",
    counterparty="0xCounterpartyAddr"
))
print(result)
```

---

## File Layout

```
kaspa_mesh_agent/
├── kaspa_mesh_agent/
│   ├── kaspa_mesh_agent_lr2021.py   # Core agent (extended)
│   ├── kaspa_wallet.py              # kaswallet-cli wrapper
│   ├── atomic_swap.py               # kaspa-atomic-swap-cli wrapper
│   ├── liquidity_pool_manager.py    # THORChain LP manager
│   ├── mesh_listener.py             # Async mesh transport
│   ├── media_utils.py               # Media encode/decode
│   └── version.py
├── cli-tools/
│   ├── eth-swap-cli/                # ETH HTLC + fee CLI
│   │   └── eth_swap_cli.py
│   └── shared/
│       ├── fee_engine.py            # THORChain CLP formula
│       └── atomic_swap.py           # Kaspa swap wrapper
├── contracts/
│   └── ETHAtomicSwap.sol            # HTLC contract
├── lp-ledger.json                   # Pool state
├── docker-compose.yml               # Multi-node deployment
└── SKILL.md                         # This file
```

---

## Testing

```bash
pytest -v
```

Expected: All tests pass including swap CLI, LP manager, fee engine, and coordination.

---

## Summary

The `kaspa_mesh_agent` skill is now a **full autonomous KAS-ETH atomic swap swarm** with:

- **THORChain-style slip-based fees** — liquidity-sensitive pricing
- **LP fee sharing** — anyone providing liquidity earns proportional %
- **CLI-first design** — all tools callable via subprocess + JSON
- **Mesh-resilient transport** — LoRa FLRC + WebSocket fallback
- **Air-gapped signing** — kaswallet-cli on secure nodes
- **Self-organising coordination** — LLM decides roles and actions
- **Streaming swaps** — large orders split to reduce slip
- **Mimir-style config** — dynamic parameter updates
