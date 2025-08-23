from __future__ import annotations

from apex.agents.base import BaseAgent
from apex.runtime.message import AgentID, Message


class CoderAgent(BaseAgent):
    """Coder agent that modifies code based on plans or feedback."""

    async def handle(self, msg: Message) -> list[Message]:
        """
        Handle incoming messages:
        - From Planner with plan: read file, apply patch
        - From Critic with feedback: apply fixes
        """
        payload = msg.payload
        
        target_file = payload.get("target_file", "src/app.py")
        
        try:
            # Read the target file
            content = await self.fs.read_file(target_file)
            content_str = content.decode("utf-8")
            
            # Check if we need to fix the bug (deterministic patch)
            if "return a - b" in content_str:
                # Apply the fix: change subtraction to addition
                # Using a simple diff format for patch_file
                diff = """--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b  # bug; coder should patch to a + b
+    return a + b  # fixed
"""
                await self.fs.patch_file(target_file, diff)
                action = "patched_bug"
            else:
                # Already fixed or different content
                action = "no_changes_needed"
            
        except Exception as e:
            # If file doesn't exist or other error, report it
            action = f"error: {str(e)}"
        
        # Check topology to determine recipient
        topology, _ = self.switch.active()
        
        if topology == "star":
            # In star, must go through planner
            recipient = AgentID("planner")
        elif topology == "chain":
            # In chain, coder -> runner is valid
            recipient = AgentID("runner")
        else:
            # In flat, direct peer-to-peer is allowed
            recipient = AgentID("runner")
        
        # Send to appropriate recipient based on topology
        return [
            self._new_msg(
                recipient=recipient,
                payload={
                    "action": "run_tests",
                    "coder_action": action,
                    "next_agent": "runner",  # Hint for planner in star topology
                },
            )
        ]