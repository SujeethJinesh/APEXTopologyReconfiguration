import dataclasses

from apex.runtime.message import AgentID, Epoch, Message


def test_message_mutability_and_defaults():
    msg = Message(
        episode_id="e1",
        msg_id="m1",
        sender=AgentID("planner"),
        recipient=AgentID("coder"),
        topo_epoch=Epoch(0),
        payload={"k": "v"},
    )
    assert dataclasses.is_dataclass(msg)
    # Ensure dataclass is not frozen (mutable)
    assert not getattr(Message.__dataclass_params__, "frozen")
    # Defaults
    assert msg.attempt == 0
    assert msg.redelivered is False
    assert msg.drop_reason is None
    assert isinstance(msg.created_ts, float)
    assert msg.expires_ts == 0.0
    # Mutations should work
    msg.attempt += 1
    msg.redelivered = True
    msg.drop_reason = "timeout"
    assert msg.attempt == 1
    assert msg.redelivered is True
    assert msg.drop_reason == "timeout"
    # NewType checks (runtime backs by base types)
    assert isinstance(msg.sender, str)
    assert isinstance(msg.recipient, str)
    assert isinstance(msg.topo_epoch, int)
