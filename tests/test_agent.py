import os, json, asyncio, pytest
from unittest.mock import MagicMock, patch
from kaspa_mesh_agent import KaspaMeshAgent


@pytest.fixture(autouse=True)
def mock_openrouter(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {"message": {"content": "GHOSTDAG is Kaspa's consensus protocol"}}
                ]
            }

    monkeypatch.setattr("requests.post", lambda *_, **__: FakeResp())


@pytest.fixture(autouse=True)
def mock_meshtastic(monkeypatch):
    monkeypatch.setenv("MESHTASTIC_SERIAL_PORT", "")


@pytest.mark.asyncio
async def test_load_and_qa():
    agent = KaspaMeshAgent(node_type="general", use_flrc=False)
    status = agent.load()
    assert status["status"] == "ok"
    answer = agent.qa("What is Kaspa's consensus?")
    assert "GHOSTDAG" in answer or "Kaspa" in answer


@pytest.mark.asyncio
async def test_coordinate_task():
    agent = KaspaMeshAgent(node_type="signer", use_flrc=False)
    agent.load()
    decision = await agent.coordinate_task("Send 100 KAS to kaspa:qqq...")
    assert "role" in decision


@pytest.mark.asyncio
async def test_metadata():
    agent = KaspaMeshAgent(node_type="general", use_flrc=False)
    meta = agent.metadata()
    assert "title" in meta
    assert "Kaspa" in meta["title"]
