"""Tests for LiquidityPoolManager."""

import sys
import os
import json
import tempfile
from decimal import Decimal
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "kaspa_mesh_agent"))

from liquidity_pool_manager import LiquidityPoolManager


@pytest.fixture
def pool_manager():
    """Create a pool manager with a temporary ledger."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "total_units": "0",
                "lp_positions": {},
                "pool_depth": {"KAS": "0", "ETH": "0"},
                "config": {
                    "min_slip_bps": 5,
                    "operator_cut_bps": 150,
                    "affiliate_cut_bps": 0,
                    "max_swap_percent": 5,
                },
            },
            f,
        )
        ledger_path = f.name

    manager = LiquidityPoolManager(ledger_path=ledger_path)
    yield manager

    os.unlink(ledger_path)


def test_initial_state(pool_manager):
    """Test initial pool state."""
    assert pool_manager.ledger["total_units"] == "0"
    assert pool_manager.ledger["lp_positions"] == {}
    assert pool_manager.ledger["pool_depth"]["KAS"] == "0"


def test_update_pool_depth(pool_manager):
    """Test updating pool depth."""
    pool_manager.update_pool_depth(Decimal("50000"), Decimal("10"))
    assert pool_manager.ledger["pool_depth"]["KAS"] == "50000"
    assert pool_manager.ledger["pool_depth"]["ETH"] == "10"


def test_add_liquidity_first(pool_manager):
    """Test adding first liquidity."""
    result = pool_manager.add_liquidity(
        lp_key="kaspa:test123", kas_added=Decimal("50000"), eth_added=Decimal("10")
    )
    assert result["lp_key"] == "kaspa:test123"
    assert Decimal(result["share_percent"]) > 0
    assert pool_manager.ledger["total_units"] != "0"


def test_add_liquidity_second_lp(pool_manager):
    """Test adding liquidity from second LP."""
    pool_manager.add_liquidity("kaspa:first", Decimal("50000"), Decimal("10"))
    result = pool_manager.add_liquidity("kaspa:second", Decimal("25000"), Decimal("5"))

    assert result["lp_key"] == "kaspa:second"
    assert Decimal(result["share_percent"]) > 0
    assert Decimal(result["share_percent"]) < 100


def test_get_proportional_share(pool_manager):
    """Test getting LP share."""
    pool_manager.add_liquidity("kaspa:test", Decimal("50000"), Decimal("10"))
    share = pool_manager.get_proportional_share("kaspa:test")

    assert share["share_percent"] == 100.0
    assert Decimal(share["units"]) > 0


def test_get_proportional_share_not_found(pool_manager):
    """Test getting share for non-existent LP."""
    share = pool_manager.get_proportional_share("kaspa:unknown")
    assert share["share_percent"] == 0.0


def test_remove_liquidity(pool_manager):
    """Test removing liquidity."""
    pool_manager.add_liquidity("kaspa:test", Decimal("50000"), Decimal("10"))
    result = pool_manager.remove_liquidity("kaspa:test", percentage=50)

    assert result["lp_key"] == "kaspa:test"
    assert Decimal(result["kas_returned"]) > 0
    assert Decimal(result["eth_returned"]) > 0


def test_remove_liquidity_not_found(pool_manager):
    """Test removing liquidity for non-existent LP."""
    result = pool_manager.remove_liquidity("kaspa:unknown")
    assert "error" in result


def test_distribute_liquidity_fee(pool_manager):
    """Test distributing liquidity fee."""
    pool_manager.update_pool_depth(Decimal("50000"), Decimal("10"))
    fee = pool_manager.distribute_liquidity_fee(Decimal("100"), "KAS")

    assert fee == 100.0
    assert Decimal(pool_manager.ledger["pool_depth"]["KAS"]) == Decimal("50100")


def test_update_config(pool_manager):
    """Test updating config."""
    result = pool_manager.update_config("min_slip_bps", 10)
    assert result["success"] is True
    assert pool_manager.ledger["config"]["min_slip_bps"] == 10


def test_update_config_invalid_key(pool_manager):
    """Test updating invalid config key."""
    result = pool_manager.update_config("invalid_key", 10)
    assert result["success"] is False


def test_get_config(pool_manager):
    """Test getting config."""
    config = pool_manager.get_config()
    assert "min_slip_bps" in config
    assert "operator_cut_bps" in config


def test_get_pool_depth(pool_manager):
    """Test getting pool depth."""
    pool_manager.update_pool_depth(Decimal("100000"), Decimal("20"))
    depth = pool_manager.get_pool_depth()

    assert depth["KAS"] == Decimal("100000")
    assert depth["ETH"] == Decimal("20")
