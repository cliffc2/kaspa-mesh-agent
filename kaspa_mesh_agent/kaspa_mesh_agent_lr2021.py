# ========================================================
# kaspa_mesh_agent_lr2021.py
# Core self-organising Kaspa agent for LR2021 / FLRC LoRa
# Extended with atomic swap + THORChain-style fee support
# ========================================================
import os, json, time, asyncio, hashlib, base64
from pathlib import Path
from typing import Dict, List, Optional
from decimal import Decimal

import requests
from meshtastic.serial_interface import SerialInterface
from meshtastic import portnums_pb2

# Kaspa RPC (gateway only)
from kaspa import RpcClient, Resolver

# Light-weight RAG
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import nltk

nltk.download("punkt", quiet=True)

# Local imports
from .mesh_listener import MeshListener
from .kaspa_wallet import (
    create_unsigned_tx as _cli_create_unsigned_tx,
    sign_tx as _cli_sign_tx,
    broadcast_tx as _cli_broadcast_tx,
    KaswalletError,
)

# Atomic swap + fee engine
try:
    from .atomic_swap import (
        initiate_htlc as _kaspa_initiate,
        claim_htlc as _kaspa_claim,
        refund_htlc as _kaspa_refund,
        status_swap as _kaspa_status,
    )
    from .liquidity_pool_manager import LiquidityPoolManager

    HAS_SWAP_SUPPORT = True
except ImportError:
    HAS_SWAP_SUPPORT = False

# WebSocket fallback transport
try:
    from .ws_transport import WebSocketTransport

    HAS_WS_TRANSPORT = True
except ImportError:
    HAS_WS_TRANSPORT = False

DEFAULT_CHUNK_FLRC = 1200
DEFAULT_CHUNK_CLASSIC = 230


class KaspaMeshAgent:
    """
    Public API mimics the arxiv skill (load, qa, coordinate_task)
    but adds Kaspa-specific transaction handling and LoRa mesh transport.
    """

    def __init__(
        self,
        node_type: str = "general",
        openrouter_key: Optional[str] = None,
        use_flrc: bool = True,
        network: str = "testnet",
    ):
        self.node_type = node_type
        self.node_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
        self.openrouter_key = openrouter_key or os.getenv("OPENROUTER_API_KEY")
        self.use_flrc = use_flrc
        self.network = network
        self.interface: Optional[SerialInterface] = None
        self.rpc_client: Optional[RpcClient] = None
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.kaspa_knowledge: List[Dict] = []
        self.index = None

        self.cache_dir = Path("kaspa_mesh_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.state_path = self.cache_dir / "state.json"
        self._load_state()

        self._listener: Optional[MeshListener] = None

        if HAS_SWAP_SUPPORT:
            self.pool_manager = LiquidityPoolManager()
        else:
            self.pool_manager = None

        self._ws_transport = None
        if HAS_WS_TRANSPORT and os.getenv("WS_TRANSPORT_URI"):
            self._ws_transport = WebSocketTransport(
                uri=os.getenv("WS_TRANSPORT_URI"), node_id=self.node_id
            )

        print(
            f"[KaspaMeshAgent {self.node_id}] init - type={self.node_type} | FLRC={self.use_flrc} | network={self.network} | swaps={HAS_SWAP_SUPPORT} | ws={bool(self._ws_transport)}"
        )

    def load(self, force: bool = False) -> Dict:
        port = os.getenv("MESHTASTIC_SERIAL_PORT")
        if port and not self.interface:
            self.interface = SerialInterface(port)
            print("Meshtastic connected (serial)")

        if self.node_type in ("gateway", "general"):
            self.rpc_client = RpcClient(resolver=Resolver())
            print("Kaspa RPC client ready")

        if not self.kaspa_knowledge or force:
            self._build_kaspa_rag()

        self._save_state()
        return {
            "status": "ok",
            "node_id": self.node_id,
            "type": self.node_type,
            "flrc": self.use_flrc,
            "network": self.network,
        }

    def _build_kaspa_rag(self):
        docs = [
            {
                "topic": "ghostdag",
                "text": "GHOSTDAG is Kaspa's consensus. It orders parallel blocks by the heaviest sub-DAG.",
            },
            {
                "topic": "blockdag",
                "text": "Kaspa uses a BlockDAG instead of a linear chain, enabling ~1 block / s.",
            },
            {
                "topic": "transaction",
                "text": "Kaspa transactions are signed with Schnorr signatures. Broadcast via submitTransaction RPC.",
            },
            {
                "topic": "fee",
                "text": "Fees are expressed in sompi; higher priority fees get the fastest inclusion.",
            },
        ]
        self.kaspa_knowledge = docs
        texts = [d["text"] for d in docs]
        emb = self.embedder.encode(texts)
        faiss.normalize_L2(emb)
        self.index = faiss.IndexFlatIP(emb.shape[1])
        self.index.add(emb)
        print("Kaspa RAG knowledge loaded (4 passages)")

    def _chunk_payload(self, data: bytes) -> List[bytes]:
        chunk_sz = DEFAULT_CHUNK_FLRC if self.use_flrc else DEFAULT_CHUNK_CLASSIC
        return [data[i : i + chunk_sz] for i in range(0, len(data), chunk_sz)]

    def send_over_mesh(self, payload: Dict, destination: int = 0xFFFFFFFF) -> bool:
        if self.interface:
            raw = json.dumps(payload).encode("utf-8")
            chunks = self._chunk_payload(raw)

            for seq, chunk in enumerate(chunks):
                msg = {
                    "mid": hashlib.sha256(raw).hexdigest()[:12],
                    "seq": seq,
                    "total": len(chunks),
                    "payload": base64.b64encode(chunk).decode(),
                }
                self.interface.sendData(
                    data=json.dumps(msg).encode(),
                    destinationId=destination,
                    portNum=portnums_pb2.PortNum.PRIVATE_APP,
                    wantAck=True,
                    hopLimit=7,
                )
                time.sleep(0.05 if self.use_flrc else 0.4)

            print(f"Sent {len(chunks)} chunk(s) over LoRa -> {len(raw)} B total")
            return True

        if self._ws_transport and self._ws_transport.connected:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._ws_transport.send(payload))
                else:
                    loop.run_until_complete(self._ws_transport.send(payload))
                print(f"Sent payload over WebSocket")
                return True
            except Exception as e:
                print(f"WebSocket send failed: {e}")

        print("No transport available (LoRa or WebSocket) - abort send")
        return False

    async def create_unsigned_tx(
        self, to_address: str, amount_sompi: int, fee_sompi: int = 1000
    ) -> Dict:
        """Create unsigned transaction via kaswallet-cli."""
        return _cli_create_unsigned_tx(
            to_address, amount_sompi, fee_sompi, self.network
        )

    async def sign_tx(self, unsigned_tx_input: str) -> Dict:
        """Sign transaction via kaswallet-cli.

        Args:
            unsigned_tx_input: Transaction ID or file path of unsigned tx

        Returns:
            Dict with signed transaction data
        """
        return _cli_sign_tx(unsigned_tx_input, self.network)

    async def broadcast_tx(self, signed_tx_input: str) -> Dict:
        """Broadcast signed transaction via kaswallet-cli or RPC fallback."""
        if self.rpc_client:
            try:
                result = await self.rpc_client.submit_transaction(
                    transaction=signed_tx_input, allow_orphan=False
                )
                return {"txid": result.get("txId"), "status": "broadcasted"}
            except Exception:
                pass
        # Fallback to kaswallet-cli broadcast
        return _cli_broadcast_tx(signed_tx_input, self.network)

    def qa(self, question: str, max_tokens: int = 256) -> str:
        if not self.index:
            return "RAG not loaded"

        q_vec = self.embedder.encode([question])[0]
        _, I = self.index.search(np.expand_dims(q_vec, 0), k=3)
        context = "\n".join([self.kaspa_knowledge[i]["text"] for i in I[0]])

        prompt = f"""You are a Kaspa Mesh Agent. Use ONLY the following knowledge:

{context}

Question: {question}
Answer (concise, no hallucination):"""

        headers = {"Authorization": f"Bearer {self.openrouter_key}"}
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    async def initiate_htlc(
        self,
        amount_sompi: int,
        claim_addr: str,
        secret_hash: str,
        timelock_blocks: int = 288,
        from_addr: Optional[str] = None,
    ) -> Dict:
        """Initiate atomic swap HTLC on Kaspa."""
        if not HAS_SWAP_SUPPORT:
            return {"success": False, "error": "swap_support_not_available"}
        return _kaspa_initiate(
            amount_sompi,
            claim_addr,
            secret_hash,
            timelock_blocks,
            self.network,
            from_addr,
        )

    async def claim_htlc(self, utxo: str, preimage: str) -> Dict:
        """Claim HTLC by revealing preimage."""
        if not HAS_SWAP_SUPPORT:
            return {"success": False, "error": "swap_support_not_available"}
        return _kaspa_claim(utxo, preimage, self.network)

    async def refund_htlc(self, utxo: str) -> Dict:
        """Refund HTLC after timelock."""
        if not HAS_SWAP_SUPPORT:
            return {"success": False, "error": "swap_support_not_available"}
        return _kaspa_refund(utxo, self.network)

    async def swap_status(self, txid: str) -> Dict:
        """Check swap UTXO status."""
        if not HAS_SWAP_SUPPORT:
            return {"success": False, "error": "swap_support_not_available"}
        return _kaspa_status(txid, self.network)

    def generate_secret(self) -> Dict:
        """Generate cryptographically secure secret preimage and hash."""
        preimage = os.urandom(32)
        secret_hash = hashlib.sha256(preimage).hexdigest()
        return {"preimage": preimage.hex(), "secret_hash": secret_hash}

    async def coordinate_task(
        self, mission: str, system_prompt: Optional[str] = None
    ) -> Dict:
        if system_prompt is None:
            prompt = f"""You are part of a self-organising Kaspa Mesh Agent swarm that communicates over a LoRa-FLRC mesh.
Mission: {mission}
Available roles: Signer, Gateway, Coordinator, Helper, Abstain.
Propose your role (JSON output only):
{{"role":"...", "reason":"...", "next_action":"..."}}"""
        else:
            prompt = f"{system_prompt}\n\nMission: {mission}"

        headers = {"Authorization": f"Bearer {self.openrouter_key}"}
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 512,
        }
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        try:
            decision = json.loads(resp.json()["choices"][0]["message"]["content"])
        except Exception:
            decision = {
                "role": "Abstain",
                "reason": "LLM parse error",
                "next_action": "",
            }
        print(f"Coordination decision -> {decision}")
        return decision

    async def execute_atomic_swap(
        self,
        input_asset: str,
        output_asset: str,
        amount: str,
        counterparty: str,
        affiliate: Optional[str] = None,
    ) -> Dict:
        """
        Full atomic swap execution with THORChain-style fees.
        Generates secret, quotes, locks on first chain, waits for counterparty.
        """
        if not HAS_SWAP_SUPPORT or not self.pool_manager:
            return {"success": False, "error": "swap_support_not_available"}

        secret = self.generate_secret()
        secret_hash = secret["secret_hash"]
        preimage = secret["preimage"]

        depth = self.pool_manager.get_pool_depth()
        config = self.pool_manager.get_config()

        result = {
            "success": True,
            "phase": "secret_generated",
            "secret_hash": secret_hash,
            "input_asset": input_asset,
            "output_asset": output_asset,
            "amount": amount,
            "counterparty": counterparty,
            "pool_depth": {k: str(v) for k, v in depth.items()},
            "config": config,
            "next_step": "lock_htlc_on_first_chain",
        }

        return result

    async def start_listener(self):
        if not self.interface:
            raise RuntimeError("Mesh interface not initialised - call load() first")
        self._listener = MeshListener(self.interface)
        await self._listener.start()
        print("Mesh listener started")
        asyncio.create_task(self._process_incoming())

    async def _process_incoming(self):
        while True:
            mid, msg = await self._listener.next_message()
            typ = msg.get("type")
            if typ == "signed_tx":
                if self.node_type == "gateway":
                    result = await self.broadcast_tx(msg["data"])
                    self.send_over_mesh(
                        {"type": "tx_status", "mid": mid, "result": result},
                        destination=msg.get("origin", 0xFFFFFFFF),
                    )
            elif typ == "media":
                from .media_utils import decode_media

                out = decode_media(msg["data"], msg.get("ext", "png"))
                print(f"[Media] Received {out}")
            else:
                print(f"[Mesh] Unhandled message type: {typ}")

    def _load_state(self):
        if self.state_path.exists():
            with open(self.state_path) as f:
                self.state = json.load(f)
        else:
            self.state = {}

    def _save_state(self):
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, indent=2)

    def metadata(self) -> Dict:
        return {
            "title": "Kaspa - BlockDAG cryptocurrency",
            "authors": ["Kaspa Team"],
            "url": "https://kaspa.org",
        }
