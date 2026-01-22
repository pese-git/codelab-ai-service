"""
Test script for /api/v1/agents endpoint.

Verifies that the correct number of agents is registered based on MULTI_AGENT_MODE.
"""
import sys
import os
import asyncio
import httpx

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import AppConfig


async def test_agents_endpoint():
    """Test /api/v1/agents endpoint"""
    
    # Determine expected agent count based on mode
    if AppConfig.MULTI_AGENT_MODE:
        expected_count = 5
        expected_agents = ['orchestrator', 'coder', 'architect', 'debug', 'ask']
        mode_name = "Multi-Agent"
    else:
        expected_count = 2
        expected_agents = ['orchestrator', 'universal']
        mode_name = "Single-Agent"
    
    print("=" * 60)
    print(f"Testing /api/v1/agents endpoint ({mode_name} mode)")
    print("=" * 60)
    print()
    
    # Start the application
    print("Starting application...")
    from app.main import app
    
    # Import after app is created to ensure initialization
    from app.domain.services.agent_registry import agent_router
    
    # Check registered agents in router
    registered_agents = agent_router.list_agents()
    print(f"Registered agents in router: {[a.value for a in registered_agents]}")
    print(f"Count: {len(registered_agents)}")
    print()
    
    # Verify router state
    assert len(registered_agents) == expected_count, \
        f"Expected {expected_count} agents in router, got {len(registered_agents)}"
    
    for agent_type in registered_agents:
        assert agent_type.value in expected_agents, \
            f"Unexpected agent type: {agent_type.value}"
    
    print(f"✓ Router has correct number of agents: {expected_count}")
    print(f"✓ All expected agents are registered: {expected_agents}")
    print()
    
    # Test HTTP endpoint
    print("Testing HTTP endpoint...")
    
    # Use TestClient for synchronous testing
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    
    client = TestClient(app)
    
    # Add internal auth header (used by middleware)
    headers = {
        "X-Internal-Auth": "test-key"
    }
    
    # Patch the config to match our test key
    with patch("app.middleware.internal_auth.AppConfig.INTERNAL_API_KEY", "test-key"):
        try:
            response = client.get("/api/v1/agents", headers=headers)
            
            print(f"Response status: {response.status_code}")
            
            assert response.status_code == 200, \
                f"Expected status 200, got {response.status_code}"
            
            agents_data = response.json()
            
            print(f"Response data: {agents_data}")
            print()
            
            # Verify response structure
            assert isinstance(agents_data, list), "Response should be a list"
            assert len(agents_data) == expected_count, \
                f"Expected {expected_count} agents in response, got {len(agents_data)}"
            
            # Verify each agent has required fields
            for agent in agents_data:
                assert "type" in agent, "Agent should have 'type' field"
                assert "name" in agent, "Agent should have 'name' field"
                assert "description" in agent, "Agent should have 'description' field"
                assert "allowed_tools" in agent, "Agent should have 'allowed_tools' field"
                assert "has_file_restrictions" in agent, "Agent should have 'has_file_restrictions' field"
                
                assert agent["type"] in expected_agents, \
                    f"Unexpected agent type in response: {agent['type']}"
                
                print(f"  ✓ {agent['type']}: {len(agent['allowed_tools'])} tools")
            
            print()
            print("=" * 60)
            print(f"✓ All tests passed for {mode_name} mode!")
            print("=" * 60)
            print()
            
            # Print summary
            print("Summary:")
            print(f"  - Mode: {mode_name}")
            print(f"  - Expected agents: {expected_count}")
            print(f"  - Actual agents: {len(agents_data)}")
            print(f"  - Agent types: {[a['type'] for a in agents_data]}")
            print()
            
            return True
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"✗ Test failed: {e}")
        print("=" * 60)
        return False
    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ Unexpected error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run tests"""
    print()
    print("Agent Endpoint Test")
    print()
    print(f"Configuration:")
    print(f"  MULTI_AGENT_MODE: {AppConfig.MULTI_AGENT_MODE}")
    print()
    
    # Run async test
    success = asyncio.run(test_agents_endpoint())
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
