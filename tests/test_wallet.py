import os, json, pytest
from unittest.mock import patch, MagicMock
from kaspa_mesh_agent.kaspa_wallet import (
    get_balance,
    get_addresses,
    new_address,
    create_unsigned_tx,
    sign_tx,
    broadcast_tx,
    send,
    get_daemon_version,
    KaswalletError,
)


def test_get_balance():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps({"balance": 1000000000})
        result = get_balance()
        assert result["balance"] == 1000000000
        mock_cli.assert_called_once_with(["balance", "--json"], "testnet")


def test_get_addresses():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps(["kaspa:qqq123", "kaspa:qqq456"])
        result = get_addresses()
        assert len(result) == 2
        assert result[0].startswith("kaspa:")


def test_new_address():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps({"address": "kaspa:qqqnew"})
        result = new_address()
        assert result == "kaspa:qqqnew"


def test_create_unsigned_tx():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps({"tx_id": "unsigned123"})
        result = create_unsigned_tx("kaspa:qqq...", 1000000, 1000)
        assert "tx_id" in result
        mock_cli.assert_called_once()


def test_sign_tx():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps({"tx_id": "signed123"})
        result = sign_tx("unsigned123")
        assert "tx_id" in result


def test_broadcast_tx():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps({"tx_id": "broadcasted123"})
        result = broadcast_tx("signed123")
        assert "tx_id" in result


def test_send():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps({"tx_id": "sent123"})
        result = send("kaspa:qqq...", 1000000)
        assert "tx_id" in result


def test_get_daemon_version():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = "0.1.0"
        result = get_daemon_version()
        assert result == "0.1.0"


def test_kaswallet_error():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.side_effect = KaswalletError("CLI not found")
        with pytest.raises(KaswalletError):
            mock_cli()


def test_network_parameter():
    with patch("kaspa_mesh_agent.kaspa_wallet._run_cli") as mock_cli:
        mock_cli.return_value = json.dumps({"balance": 0})
        get_balance(network="mainnet")
        mock_cli.assert_called_once_with(["balance", "--json"], "mainnet")
