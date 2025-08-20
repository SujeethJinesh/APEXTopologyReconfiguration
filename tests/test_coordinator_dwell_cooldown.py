import pytest

from apex.runtime.coordinator import Coordinator
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


@pytest.mark.asyncio
async def test_coordinator_dwell_and_cooldown_enforcement():
    r = Router(recipients=["a", "b"])
    se = SwitchEngine(r)
    coord = Coordinator(se)

    # Initially, dwell not satisfied
    res1 = await coord.request_switch("chain")
    assert res1["accepted"] is False and res1["reason"] == "dwell"

    # Advance steps until dwell satisfied
    coord.step()
    res2 = await coord.request_switch("chain")
    assert res2["accepted"] is False and res2["reason"] == "dwell"
    coord.step()  # dwell now satisfied (>=2)

    res3 = await coord.request_switch("chain")
    assert res3["accepted"] is True and res3["switch_result"]["ok"] is True

    # Immediately try another switch – should be denied by cooldown
    res4 = await coord.request_switch("flat")
    assert res4["accepted"] is False and res4["reason"] == "cooldown"

    # Step through cooldown
    coord.step()
    res5 = await coord.request_switch("flat")
    assert res5["accepted"] is False and res5["reason"] == "cooldown"
    coord.step()
    res6 = await coord.request_switch("flat")
    assert res6["accepted"] is True and res6["switch_result"]["ok"] is True
