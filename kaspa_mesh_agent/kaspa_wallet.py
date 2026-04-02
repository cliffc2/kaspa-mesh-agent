# -------------------------------------------------
# kaspa_wallet.py
# Wrapper around kaswallet-cli (IgraLabs)
# Uses subprocess to interact with the gRPC wallet daemon
# -------------------------------------------------
import subprocess
import json
from typing import Optional, Dict, Any, Union
from pathlib import Path

DEFAULT_NETWORK = "testnet"


class KaswalletError(Exception):
    """Raised when kaswallet-cli fails."""

    pass


def _run_cli(args: list, network: str = DEFAULT_NETWORK, timeout: int = 30) -> str:
    """Run kaswallet-cli command and return stdout."""
    cmd = ["kaswallet-cli", f"--{network}"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise KaswalletError(f"kaswallet-cli failed: {e.stderr}") from e
    except FileNotFoundError:
        raise KaswalletError(
            "kaswallet-cli not found. Install from https://github.com/IgraLabs/kaswallet"
        ) from None


def get_balance(network: str = DEFAULT_NETWORK) -> Dict[str, Any]:
    """Get wallet balance."""
    output = _run_cli(["balance", "--json"], network)
    return json.loads(output)


def get_addresses(network: str = DEFAULT_NETWORK) -> list:
    """Show all wallet addresses."""
    output = _run_cli(["show-addresses", "--json"], network)
    return json.loads(output)


def new_address(network: str = DEFAULT_NETWORK) -> str:
    """Generate a new address."""
    output = _run_cli(["new-address", "--json"], network)
    return json.loads(output).get("address", "")


def create_unsigned_tx(
    to_address: str,
    amount_sompi: int,
    fee_sompi: int = 1000,
    network: str = DEFAULT_NETWORK,
) -> Dict[str, Any]:
    """Create an unsigned transaction."""
    output = _run_cli(
        [
            "create-unsigned-transaction",
            "--to",
            to_address,
            "--amount",
            str(amount_sompi),
            "--fee",
            str(fee_sompi),
            "--json",
        ],
        network,
    )
    return json.loads(output)


def sign_tx(tx_input: str, network: str = DEFAULT_NETWORK) -> Dict[str, Any]:
    """Sign an unsigned transaction. tx_input can be a file path or transaction ID."""
    output = _run_cli(["sign", "--input", tx_input, "--json"], network)
    return json.loads(output)


def broadcast_tx(tx_input: str, network: str = DEFAULT_NETWORK) -> Dict[str, Any]:
    """Broadcast a signed transaction."""
    output = _run_cli(["broadcast", "--input", tx_input, "--json"], network)
    return json.loads(output)


def send(
    to_address: str,
    amount_sompi: int,
    fee_sompi: int = 1000,
    network: str = DEFAULT_NETWORK,
) -> Dict[str, Any]:
    """Send transaction directly (create + sign + broadcast in one step)."""
    output = _run_cli(
        [
            "send",
            "--to",
            to_address,
            "--amount",
            str(amount_sompi),
            "--fee",
            str(fee_sompi),
            "--json",
        ],
        network,
    )
    return json.loads(output)


def get_daemon_version(network: str = DEFAULT_NETWORK) -> str:
    """Get the wallet daemon version."""
    output = _run_cli(["get-daemon-version"], network)
    return output
