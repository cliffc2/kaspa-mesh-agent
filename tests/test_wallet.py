import os, tempfile, pytest
from kaspa_mesh_agent.kaspa_wallet import (
    save_wallet,
    load_wallet,
    get_keypair,
    get_address,
)
from kaspa import Mnemonic, NetworkType


def test_encrypt_decrypt_roundtrip():
    m = Mnemonic.random()
    fd, path = tempfile.mkstemp()
    os.close(fd)

    pw = "strong-password-123"
    save_wallet(m.phrase, path, pw)
    m2 = load_wallet(path, pw)
    assert m2.phrase == m.phrase


def test_derive_keypair_and_address():
    m = Mnemonic.random()
    kp = get_keypair(m)
    addr = get_address(m, NetworkType.Mainnet)
    assert addr.startswith("kaspa:")
    assert len(addr) > 40


def test_deterministic_derivation():
    m = Mnemonic.random()
    addr1 = get_address(m, NetworkType.Mainnet)
    addr2 = get_address(m, NetworkType.Mainnet)
    assert addr1 == addr2
