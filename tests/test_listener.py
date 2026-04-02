import asyncio, json, base64
import pytest
from kaspa_mesh_agent.mesh_listener import MeshListener
from meshtastic import portnums_pb2


@pytest.mark.asyncio
async def test_reassembly():
    payload = json.dumps({"type": "test", "data": "hello"}).encode()
    chunk_sz = 10
    chunks = [payload[i : i + chunk_sz] for i in range(0, len(payload), chunk_sz)]
    mid = "abc123def456"

    packet_data = []
    for i, ch in enumerate(chunks):
        msg = {
            "mid": mid,
            "seq": i,
            "total": len(chunks),
            "payload": base64.b64encode(ch).decode(),
        }
        packet_data.append(json.dumps(msg).encode())

    class DummyInterface:
        def __init__(self):
            self.idx = 0

        async def receive(self):
            if self.idx < len(packet_data):
                pkt = type(
                    "Packet",
                    (),
                    {
                        "decoded": packet_data[self.idx],
                        "portnum": portnums_pb2.PortNum.PRIVATE_APP,
                    },
                )()
                self.idx += 1
                return pkt
            await asyncio.sleep(0.1)
            return None

    iface = DummyInterface()
    listener = MeshListener(iface, timeout=2.0)
    await listener.start()

    mid_ret, full_msg = await asyncio.wait_for(listener.next_message(), timeout=5.0)
    assert mid_ret == mid
    assert full_msg["type"] == "test"
    assert full_msg["data"] == "hello"
