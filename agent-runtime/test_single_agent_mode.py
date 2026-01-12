"""
Test script for Single-Agent mode (UniversalAgent).

This script verifies that:
1. UniversalAgent can be instantiated correctly
2. Multi-agent mode can be toggled via config
3. Both modes are accessible
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.universal_agent import UniversalAgent
from app.agents.base_agent import AgentType
from app.core.config import AppConfig


def test_universal_agent_creation():
    """Test that UniversalAgent can be created"""
    print("Testing UniversalAgent creation...")
    
    agent = UniversalAgent()
    
    assert agent.agent_type == AgentType.UNIVERSAL, "Agent type should be UNIVERSAL"
    assert agent.allowed_tools is not None, "Agent should have allowed tools"
    assert len(agent.allowed_tools) > 0, "Agent should have at least one tool"
    assert agent.file_restrictions is None or len(agent.file_restrictions) == 0, \
        "Universal agent should have no file restrictions"
    
    print(f"✓ UniversalAgent created successfully")
    print(f"  - Type: {agent.agent_type.value}")
    print(f"  - Tools: {len(agent.allowed_tools)}")
    print(f"  - File restrictions: {agent.file_restrictions}")
    print()


def test_agent_type_enum():
    """Test that AgentType.UNIVERSAL exists"""
    print("Testing AgentType.UNIVERSAL enum...")
    
    assert hasattr(AgentType, 'UNIVERSAL'), "AgentType should have UNIVERSAL"
    assert AgentType.UNIVERSAL.value == "universal", "UNIVERSAL value should be 'universal'"
    
    print(f"✓ AgentType.UNIVERSAL exists: {AgentType.UNIVERSAL.value}")
    print()


def test_config_multi_agent_mode():
    """Test that MULTI_AGENT_MODE config exists"""
    print("Testing MULTI_AGENT_MODE configuration...")
    
    assert hasattr(AppConfig, 'MULTI_AGENT_MODE'), "AppConfig should have MULTI_AGENT_MODE"
    
    mode = AppConfig.MULTI_AGENT_MODE
    print(f"✓ MULTI_AGENT_MODE configuration exists: {mode}")
    print(f"  - Current mode: {'Multi-Agent' if mode else 'Single-Agent (Universal)'}")
    print()


def test_tool_access():
    """Test that UniversalAgent has access to all expected tools"""
    print("Testing UniversalAgent tool access...")
    
    agent = UniversalAgent()
    
    expected_tools = [
        "read_file",
        "write_file",
        "list_files",
        "search_in_code",
        "create_directory",
        "execute_command",
        "attempt_completion",
        "ask_followup_question"
    ]
    
    for tool in expected_tools:
        assert agent.can_use_tool(tool), f"Agent should be able to use {tool}"
        print(f"  ✓ Can use: {tool}")
    
    print(f"✓ All {len(expected_tools)} tools are accessible")
    print()


def test_file_restrictions():
    """Test that UniversalAgent has no file restrictions"""
    print("Testing UniversalAgent file restrictions...")
    
    agent = UniversalAgent()
    
    test_files = [
        "src/main.py",
        "docs/README.md",
        "tests/test_agent.py",
        "config/settings.json",
        ".env"
    ]
    
    for file_path in test_files:
        assert agent.can_edit_file(file_path), f"Agent should be able to edit {file_path}"
        print(f"  ✓ Can edit: {file_path}")
    
    print(f"✓ No file restrictions (can edit all files)")
    print()


def main():
    """Run all tests"""
    print("=" * 60)
    print("Single-Agent Mode Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_agent_type_enum()
        test_universal_agent_creation()
        test_config_multi_agent_mode()
        test_tool_access()
        test_file_restrictions()
        
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        print()
        print("Usage:")
        print("  - To enable Single-Agent mode: set AGENT_RUNTIME__MULTI_AGENT_MODE=false")
        print("  - To enable Multi-Agent mode: set AGENT_RUNTIME__MULTI_AGENT_MODE=true (default)")
        print()
        
        return 0
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"✗ Test failed: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ Unexpected error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
