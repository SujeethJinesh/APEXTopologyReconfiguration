from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from apex.agents.base import BaseAgent
from apex.agents.roles import (
    CoderAgent,
    CriticAgent,
    PlannerAgent,
    RunnerAgent,
    SummarizerAgent,
)
from apex.runtime.message import AgentID, Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine

from stubs import StubFS, StubLLM, StubTest


@pytest.fixture
def toy_repo(tmp_path):
    """Create a toy repository with a bug for testing."""
    # Create src/app.py with a bug
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    app_file = src_dir / "app.py"
    app_file.write_text("""def add(a, b):
    return a - b  # bug; coder should patch to a + b
""")
    
    # Create tests/test_app.py
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_app.py"
    test_file.write_text("""from src.app import add

def test_add():
    assert add(2, 3) == 5
""")
    
    return tmp_path


@pytest.fixture
def stub_fs(toy_repo):
    """Create a stub filesystem for the toy repo."""
    return StubFS(toy_repo)


@pytest.fixture
def stub_test(toy_repo):
    """Create a stub test runner for the toy repo."""
    return StubTest(toy_repo)


@pytest.fixture
def stub_llm():
    """Create a stub LLM."""
    return StubLLM()


def create_agents(
    router: Router,
    switch: SwitchEngine,
    fs: StubFS,
    test: StubTest,
    llm: StubLLM,
    episode_id: str,  # Add episode_id parameter
) -> Dict[AgentID, BaseAgent]:
    """Create all role agents with unified episode_id."""
    agents = {}
    
    # Create Planner
    agents[AgentID("planner")] = PlannerAgent(
        agent_id=AgentID("planner"),
        router=router,
        switch=switch,
        fs=fs,
        test=test,
        episode_id=episode_id,  # Pass shared episode_id
        llm=llm,
    )
    
    # Create Coder
    agents[AgentID("coder")] = CoderAgent(
        agent_id=AgentID("coder"),
        router=router,
        switch=switch,
        fs=fs,
        test=test,
        episode_id=episode_id,  # Pass shared episode_id
        llm=llm,
    )
    
    # Create Runner
    agents[AgentID("runner")] = RunnerAgent(
        agent_id=AgentID("runner"),
        router=router,
        switch=switch,
        fs=fs,
        test=test,
        episode_id=episode_id,  # Pass shared episode_id
        llm=llm,
    )
    
    # Create Critic
    agents[AgentID("critic")] = CriticAgent(
        agent_id=AgentID("critic"),
        router=router,
        switch=switch,
        fs=fs,
        test=test,
        episode_id=episode_id,  # Pass shared episode_id
        llm=llm,
    )
    
    # Create Summarizer
    agents[AgentID("summarizer")] = SummarizerAgent(
        agent_id=AgentID("summarizer"),
        router=router,
        switch=switch,
        fs=fs,
        test=test,
        episode_id=episode_id,  # Pass shared episode_id
        llm=llm,
    )
    
    return agents


class TraceCollector:
    """Collects trace events for JSONL artifact generation."""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.step = 0
    
    def add_event(self, event_type: str, **kwargs):
        """Add an event to the trace."""
        self.step += 1
        event = {
            "step": self.step,
            "event": event_type,
            **kwargs,
        }
        self.events.append(event)
    
    def save_jsonl(self, path: Path):
        """Save events as JSONL to the given path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for event in self.events:
                f.write(json.dumps(event) + "\n")


class TracingRouter(Router):
    """Router wrapper that traces all events with clear success/rejection status."""
    
    def __init__(self, *args, trace_collector: TraceCollector, **kwargs):
        super().__init__(*args, **kwargs)
        self.trace = trace_collector
    
    async def route(self, msg: Message) -> bool:
        """Route and trace the message with success/rejection status."""
        topology, epoch = self._switch_engine.active() if self._switch_engine else ("unknown", 0)
        
        # Log attempt
        self.trace.add_event(
            "enqueue_attempt",
            epoch=epoch,
            topology=topology,
            from_agent=str(msg.sender),
            to_agent=str(msg.recipient),
            msg_id=msg.msg_id,
        )
        
        # Try to route
        try:
            result = await super().route(msg)
            # Log success
            self.trace.add_event(
                "enqueue_success",
                epoch=epoch,
                topology=topology,
                from_agent=str(msg.sender),
                to_agent=str(msg.recipient),
                msg_id=msg.msg_id,
            )
            return result
        except Exception as e:
            # Log rejection
            self.trace.add_event(
                "enqueue_rejected",
                epoch=epoch,
                topology=topology,
                from_agent=str(msg.sender),
                to_agent=str(msg.recipient),
                msg_id=msg.msg_id,
                reason=str(e),
            )
            raise
    
    async def dequeue(self, agent_id: AgentID) -> Optional[Message]:
        """Dequeue and trace if a message is returned."""
        msg = await super().dequeue(agent_id)
        if msg:
            topology, epoch = (
                self._switch_engine.active() if self._switch_engine else ("unknown", 0)
            )
            self.trace.add_event(
                "dequeue",
                epoch=epoch,
                topology=topology,
                agent=str(agent_id),
                msg_id=msg.msg_id,
                from_agent=str(msg.sender),
                to_agent=str(msg.recipient),
            )
        return msg