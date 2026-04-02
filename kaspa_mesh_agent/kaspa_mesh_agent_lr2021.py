# ========================================================
# kaspa_mesh_agent_lr2021.py
# Core self-organising Kaspa agent for LR2021 / FLRC LoRa
# ========================================================
import os, json, time, asyncio, hashlib, base64
from pathlib import Path
from typing import Dict, List, Optional

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
    load_wallet,
    create_unsigned_tx,
    sign_tx,
    verify_raw_tx,
)

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
    ):
        self.node_type = node_type
        self.node_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
        self.openrouter_key = openrouter_key or os.getenv("OPENROUTER_API_KEY")
        self.use_flrc = use_flrc
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

        print(
            f"[KaspaMeshAgent {self.node_id}] init - type={self.node_type} | FLRC={self.use_flrc}"
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
        if not self.interface:
            print("No Meshtastic interface - abort send")
            return False

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

        print(f"Sent {len(chunks)} chunk(s) -> {len(raw)} B total")
        return True

    async def create_unsigned_tx(
        self, to_address: str, amount_sompi: int, fee_sompi: int = 1000
    ) -> Dict:
        tx = create_unsigned_tx(to_address, amount_sompi, fee_sompi)
        unsigned_hex = tx.serialized().hex()
        return {"unsigned_tx_hex": unsigned_hex}

    async def sign_tx(
        self, unsigned_hex: str, wallet_path: str, password: str, account_idx: int = 0
    ) -> str:
        wallet = load_wallet(wallet_path, password)
        from kaspa import Transaction

        tx_obj = Transaction.deserialize(bytes.fromhex(unsigned_hex))
        signed_hex = sign_tx(tx_obj, wallet, account_idx)
        assert verify_raw_tx(signed_hex), "Signed payload broken!"
        return signed_hex

    async def broadcast_tx(self, signed_tx_hex: str) -> Dict:
        if not self.rpc_client:
            return {"error": "No RPC client (node not a gateway)"}
        try:
            result = await self.rpc_client.submit_transaction(
                transaction=signed_tx_hex, allow_orphan=False
            )
            return {"txid": result.get("txId"), "status": "broadcasted"}
        except Exception as e:
            return {"error": str(e)}

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

    async def coordinate_task(self, mission: str) -> Dict:
        prompt = f"""You are part of a self-organising Kaspa Mesh Agent swarm that communicates over a LoRa-FLRC mesh.
Mission: {mission}
Available roles: Signer, Gateway, Coordinator, Helper, Abstain.
Propose your role (JSON output only):
{{"role":"...", "reason":"...", "next_action":"..."}}"""

        headers = {"Authorization": f"Bearer {self.openrouter_key}"}
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 128,
        }
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=20,
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
