"""Tests for THORChain-style fee engine."""

import sys
import os
from decimal import Decimal
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "kaspa_mesh_agent"))

from fee_engine import (
    calculate_slip_fee,
    calculate_output_with_fee,
    calculate_lp_units,
    should_stream_swap,
)


def test_calculate_slip_fee_basic():
    """Test basic slip fee calculation."""
    fee = calculate_slip_fee(Decimal("1000"), Decimal("50000"), Decimal("10"))
    assert fee > 0
    assert fee < Decimal("1000")


def test_calculate_slip_fee_zero_pool():
    """Test slip fee with zero pool depth."""
    fee = calculate_slip_fee(Decimal("1000"), Decimal("0"), Decimal("10"))
    assert fee == Decimal("0")


def test_calculate_slip_fee_small_swap():
    """Test slip fee for small swap relative to pool."""
    fee = calculate_slip_fee(Decimal("100"), Decimal("100000"), Decimal("100"))
    assert fee > 0
    assert fee < Decimal("1")


def test_calculate_slip_fee_large_swap():
    """Test slip fee for large swap relative to pool."""
    fee = calculate_slip_fee(Decimal("50000"), Decimal("50000"), Decimal("50"))
    assert fee > Decimal("10")


def test_calculate_output_with_fee_basic():
    """Test full output calculation with fees."""
    result = calculate_output_with_fee(Decimal("1000"), Decimal("50000"), Decimal("10"))
    assert "expected_output" in result
    assert "liquidity_fee" in result
    assert "slip_bps" in result
    assert "total_fee_bps" in result
    assert Decimal(result["expected_output"]) > 0
    assert Decimal(result["liquidity_fee"]) > 0


def test_calculate_output_with_fee_zero_pool():
    """Test output calculation with empty pool."""
    result = calculate_output_with_fee(Decimal("1000"), Decimal("0"), Decimal("10"))
    assert result["expected_output"] == "0"
    assert result["liquidity_fee"] == "0"


def test_calculate_output_with_fee_operator_cut():
    """Test output calculation with operator cut."""
    result = calculate_output_with_fee(
        Decimal("1000"), Decimal("50000"), Decimal("10"), operator_cut_bps=200
    )
    assert Decimal(result["operator_cut"]) > 0
    assert Decimal(result["lp_fee"]) >= 0


def test_calculate_output_with_fee_affiliate():
    """Test output calculation with affiliate cut."""
    result = calculate_output_with_fee(
        Decimal("1000"), Decimal("50000"), Decimal("10"), affiliate_cut_bps=50
    )
    assert Decimal(result["affiliate_cut"]) > 0


def test_calculate_lp_units_first_liquidity():
    """Test LP units calculation for first liquidity."""
    units = calculate_lp_units(
        Decimal("10000"), Decimal("10"), Decimal("0"), Decimal("0"), Decimal("0")
    )
    assert units > 0


def test_calculate_lp_units_subsequent():
    """Test LP units calculation for subsequent liquidity."""
    units = calculate_lp_units(
        Decimal("5000"),
        Decimal("5"),
        Decimal("50000"),
        Decimal("50"),
        Decimal("1000000"),
    )
    assert units > 0


def test_should_stream_swap_small():
    """Test small swap should not stream."""
    should_stream, chunks = should_stream_swap(
        Decimal("1000"), Decimal("50000"), max_swap_percent=5
    )
    assert not should_stream
    assert chunks == 1


def test_should_stream_swap_large():
    """Test large swap should stream."""
    should_stream, chunks = should_stream_swap(
        Decimal("10000"), Decimal("50000"), max_swap_percent=5
    )
    assert should_stream
    assert chunks >= 4
    assert chunks <= 8


def test_should_stream_swap_edge_case():
    """Test edge case at exactly max_swap_percent."""
    should_stream, chunks = should_stream_swap(
        Decimal("2500"), Decimal("50000"), max_swap_percent=5
    )
    assert not should_stream
