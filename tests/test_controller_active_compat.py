"""Test controller compatibility with both tuple and dict from switch.active()."""

import asyncio
from unittest.mock import Mock
from apex.controller.controller import APEXController
from apex.controller.bandit_v1 import BanditSwitchV1
from apex.controller.features import FeatureSource


def test_switch_active_tuple_format():
    """Test controller handles tuple format from switch.active() per ISwitchEngine spec."""
    # Mock switch returning tuple (topology, epoch) per vMVP-1 spec
    switch_mock = Mock()
    switch_mock.active.return_value = ("star", 42)
    switch_mock.switched_at = 10
    
    # Mock coordinator
    coordinator_mock = Mock()
    async def mock_request_switch(x):
        return {"committed": False}
    coordinator_mock.request_switch = mock_request_switch
    
    # Create controller
    controller = APEXController(
        bandit=BanditSwitchV1(seed=42),
        feature_src=FeatureSource(),
        coordinator=coordinator_mock,
        switch=switch_mock,
        budget=1000
    )
    
    # Execute tick
    decision = asyncio.run(controller.tick())
    
    # Verify it handled tuple format correctly
    assert decision["topology"] == "star"
    assert decision["switch"]["epoch"] == 42
    assert "bandit_ms" in decision
    assert "tick_ms" in decision
    assert decision["step"] == 1


def test_switch_active_dict_format():
    """Test controller handles dict format from switch.active() for backwards compat."""
    # Mock switch returning dict format
    switch_mock = Mock()
    switch_mock.active.return_value = {
        "topology": "chain",
        "epoch": 99,
        "switched_at": 50
    }
    
    # Mock coordinator
    coordinator_mock = Mock()
    async def mock_request_switch(x):
        return {"committed": False}
    coordinator_mock.request_switch = mock_request_switch
    
    # Create controller
    controller = APEXController(
        bandit=BanditSwitchV1(seed=42),
        feature_src=FeatureSource(),
        coordinator=coordinator_mock,
        switch=switch_mock,
        budget=1000
    )
    
    # Execute tick
    decision = asyncio.run(controller.tick())
    
    # Verify it handled dict format correctly
    assert decision["topology"] == "chain"
    assert decision["switch"]["epoch"] == 99
    assert "bandit_ms" in decision
    assert "tick_ms" in decision
    assert decision["step"] == 1


def test_switch_active_both_formats():
    """Test controller handles switching between tuple and dict formats."""
    switch_mock = Mock()
    coordinator_mock = Mock()
    async def mock_request_switch(x):
        return {"committed": False}
    coordinator_mock.request_switch = mock_request_switch
    
    controller = APEXController(
        bandit=BanditSwitchV1(seed=42),
        feature_src=FeatureSource(),
        coordinator=coordinator_mock,
        switch=switch_mock,
        budget=1000
    )
    
    # First tick with tuple format
    switch_mock.active.return_value = ("flat", 1)
    switch_mock.switched_at = 0
    decision1 = asyncio.run(controller.tick())
    assert decision1["topology"] == "flat"
    assert decision1["switch"]["epoch"] == 1
    
    # Second tick with dict format
    switch_mock.active.return_value = {"topology": "star", "epoch": 2, "switched_at": 1}
    decision2 = asyncio.run(controller.tick())
    assert decision2["topology"] == "star"
    assert decision2["switch"]["epoch"] == 2
    
    # Both should have latency measurements
    assert "bandit_ms" in decision1 and "tick_ms" in decision1
    assert "bandit_ms" in decision2 and "tick_ms" in decision2