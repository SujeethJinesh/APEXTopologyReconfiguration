"""Test LLM generation with PID tracking."""
import asyncio
import json
from apex.llm.client import PortableLLMClient

async def test_llm():
    print("Creating LLM client...")
    client = PortableLLMClient()
    
    print("Warming up all workers...")
    await client.warmup_all("Hello", 1)
    
    print("\nTesting generation from 3 different agents...")
    agents = ["agent_star", "agent_chain", "agent_flat"]
    
    for agent in agents:
        print(f"\n--- Testing {agent} ---")
        response = await client.complete(
            prompt="What is 2+2?",
            max_tokens=50,
            agent_id=agent
        )
        print(f"Response: {response.content[:100]}...")
        print(f"Tokens used: {response.tokens_used}")
        print(f"Error: {response.error}")
        print(f"Status: {response.status}")
    
    print("\nClient stats:")
    print(json.dumps(client.get_stats(), indent=2))
    
    client.shutdown()

if __name__ == "__main__":
    import os
    os.environ["APEX_ALLOW_NETWORK"] = "1"
    os.environ["APEX_LLM_BACKEND"] = "llama_cpp_metal"
    os.environ["APEX_LLM_N_INSTANCES"] = "3"
    asyncio.run(test_llm())
