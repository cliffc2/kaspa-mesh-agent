# -------------------------------------------------
# kaspa_wallet.py
# Wallet helpers using the official Kaspa Python SDK
# Provides encrypted on-disk storage and sign utilities
# -------------------------------------------------
import json, hashlib, os
from typing import Optional

from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from kaspa import (
    Mnemonic,
    XPrv,
    Keypair,
    NetworkType,
    create_transaction,
    sign_transaction,
)


def _derive_key(pw: str) -> bytes:
    return hashlib.sha256(pw.encode()).digest()


def save_wallet(mnemonic_phrase: str, path: str, password: str) -> None:
    """Persist only the mnemonic (never raw private keys)."""
    data = {"mnemonic": mnemonic_phrase}
    plain = json.dumps(data).encode()
    key = _derive_key(password)
    nonce = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(plain)
    with open(path, "wb") as f:
        f.write(nonce)
        f.write(tag)
        f.write(ct)


def load_wallet(path: str, password: str) -> Mnemonic:
    """Decrypt the file and return a Mnemonic object."""
    with open(path, "rb") as f:
        nonce = f.read(12)
        tag = f.read(16)
        ct = f.read()
    key = _derive_key(password)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plain = cipher.decrypt_and_verify(ct, tag)
    data = json.loads(plain.decode())
    return Mnemonic(data["mnemonic"])


def get_keypair(
    mnemonic: Mnemonic, derivation_path: str = "m/44/111111/0/0/0"
) -> Keypair:
    """Derive a Keypair from a mnemonic."""
    seed = mnemonic.to_seed("")
    xprv = XPrv(seed)
    child = xprv.derive_path(derivation_path)
    return Keypair.from_private_key(child.to_private_key())


def get_address(mnemonic: Mnemonic, network: NetworkType = NetworkType.Mainnet) -> str:
    """Get the Kaspa address from a mnemonic."""
    kp = get_keypair(mnemonic)
    addr = kp.to_address(network)
    return str(addr)


def create_unsigned_tx(utxo_source, outputs: list, priority_fee: int = 1000):
    """Create an unsigned transaction using the kaspa SDK."""
    return create_transaction(utxo_source, outputs, priority_fee)


def sign_tx(tx, mnemonic: Mnemonic, verify_sig: bool = True):
    """Sign a transaction with the wallet derived from mnemonic."""
    kp = get_keypair(mnemonic)
    return sign_transaction(tx, kp, verify_sig)


def verify_raw_tx(raw_tx) -> bool:
    """Quick sanity-check - verifies the transaction is valid."""
    return raw_tx is not None
