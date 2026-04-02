# -------------------------------------------------
# mesh_listener.py
# Async listener that re-assembles chunked packets (FLRC or classic LoRa)
# -------------------------------------------------
import json, time, asyncio, base64, hashlib
from collections import defaultdict
from typing import Dict, Tuple, List

from meshtastic.serial_interface import SerialInterface
from meshtastic import portnums_pb2


class MeshListener:
    """
    Listens for PRIVATE_APP packets that follow the chunk format:
    {
        "mid": "<msg-id>",
        "seq": <int>,
        "total": <int>,
        "payload": "<base64-bytes>"
    }
    Emits the *re-assembled* JSON object via an asyncio.Queue.
    """

    def __init__(self, iface: SerialInterface, timeout: float = 30.0):
        self.iface = iface
        self.timeout = timeout
        self._buffers: Dict[str, Dict] = defaultdict(dict)
        self.queue: asyncio.Queue[Tuple[str, dict]] = asyncio.Queue()

    async def start(self):
        asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        while True:
            packet = await self.iface.receive()
            if packet is None:
                await asyncio.sleep(0.05)
                continue
            if packet.portnum != portnums_pb2.PortNum.PRIVATE_APP:
                continue
            try:
                data = packet.decoded
                chunk = json.loads(data.decode())
                await self._process_chunk(chunk)
            except Exception as exc:
                print(f"[Listener] malformed packet: {exc}")

    async def _process_chunk(self, chunk: dict):
        mid = chunk["mid"]
        seq = int(chunk["seq"])
        total = int(chunk["total"])
        payload = base64.b64decode(chunk["payload"])

        buf = self._buffers[mid]
        if not buf:
            buf["total"] = total
            buf["chunks"] = {}
            buf["first_seen"] = time.time()

        buf["chunks"][seq] = payload

        if len(buf["chunks"]) == buf["total"]:
            ordered = b"".join(buf["chunks"][i] for i in range(buf["total"]))
            try:
                full_msg = json.loads(ordered.decode())
                await self.queue.put((mid, full_msg))
            except Exception as exc:
                print(f"[Listener] re-assembly decode error: {exc}")
            del self._buffers[mid]

        now = time.time()
        for k in list(self._buffers):
            if now - self._buffers[k]["first_seen"] > self.timeout:
                del self._buffers[k]

    async def next_message(self) -> Tuple[str, dict]:
        return await self.queue.get()
