import os, json, pytest
from unittest.mock import patch, MagicMock
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


@pytest.mark.asyncio
async def test_create_unsigned_tx():
    from kaspa_mesh_agent.kaspa_wallet import create_unsigned_tx

    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps({"tx_id": "test123", "unsigned": True})
        result = await KaspaMeshAgent().create_unsigned_tx("kaspa:qqq...", 1000000)
        assert mock_cli.called


@pytest.mark.asyncio
async def test_sign_tx():
    from kaspa_mesh_agent.kaspa_wallet import sign_tx

    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps({"tx_id": "test123", "signed": True})
        result = await KaspaMeshAgent().sign_tx("test123")
        assert mock_cli.called


@pytest.mark.asyncio
async def test_broadcast_tx():
    from kaspa_mesh_agent.kaspa_wallet import broadcast_tx

    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps(
            {"tx_id": "test123", "status": "broadcasted"}
        )
        agent = KaspaMeshAgent(node_type="gateway")
        result = await agent.broadcast_tx("signed_tx_123")
        assert mock_cli.called
