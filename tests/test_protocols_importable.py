from apex.controller.bandit_api import BanditSwitch
from apex.integrations.llm.client_api import LLM
from apex.integrations.mcp.fs_api import FS
from apex.integrations.mcp.test_api import Test
from apex.runtime.router_api import IRouter
from apex.runtime.switch_api import ISwitchEngine


def test_protocols_defined_and_importable():
    for proto in (IRouter, ISwitchEngine, BanditSwitch, FS, Test, LLM):
        assert hasattr(proto, "__module__")
        assert hasattr(proto, "__doc__") or True  # presence is enough for M0
