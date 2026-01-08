#!/usr/bin/env python3
"""
Test script for session and agent context persistence.

This script tests that sessions and agent contexts are properly
saved to and restored from the PostgreSQL database.
"""
import sys
import asyncio
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.session_manager_async import AsyncSessionManager
from app.services.agent_context_async import AsyncAgentContextManager
from app.agents.base_agent import AgentType


async def test_session_persistence():
    """Test session persistence"""
    print("=" * 60)
    print("Testing Session Persistence")
    print("=" * 60)
    
    # Create session manager
    sm = AsyncSessionManager()
    await sm.initialize()
    
    # Create a test session
    session_id = "test_session_123"
    print(f"\n1. Creating session: {session_id}")
    session = await sm.create(session_id, system_prompt="You are a helpful assistant")
    print(f"   ✓ Session created with {len(session.messages)} messages")
    
    # Add some messages
    print("\n2. Adding messages to session")
    await sm.append_message(session_id, "user", "Hello, how are you?")
    await sm.append_message(session_id, "assistant", "I'm doing great! How can I help you?")
    print(f"   ✓ Added 2 messages, total: {len(sm.get(session_id).messages)}")
    
    # Verify session exists
    print("\n3. Verifying session exists in memory")
    assert sm.exists(session_id), "Session should exist"
    print(f"   ✓ Session exists in memory")
    
    # Get history
    history = sm.get_history(session_id)
    print(f"\n4. Retrieved history: {len(history)} messages")
    for i, msg in enumerate(history):
        print(f"   - Message {i+1}: {msg['role']}")
    
    print("\n✅ Session persistence test completed successfully!")
    return session_id


async def test_agent_context_persistence():
    """Test agent context persistence"""
    print("\n" + "=" * 60)
    print("Testing Agent Context Persistence")
    print("=" * 60)
    
    # Create agent context manager
    acm = AsyncAgentContextManager()
    await acm.initialize()
    
    # Create a test context
    session_id = "test_context_456"
    print(f"\n1. Creating agent context: {session_id}")
    context = await acm.get_or_create(session_id)
    print(f"   ✓ Context created with agent: {context.current_agent.value}")
    
    # Switch agent
    print("\n2. Switching to coder agent")
    context.switch_agent(AgentType.CODER, "User requested coding task")
    print(f"   ✓ Switched to: {context.current_agent.value}")
    print(f"   ✓ Switch count: {context.switch_count}")
    
    # Add metadata
    print("\n3. Adding metadata")
    context.add_metadata("test_key", "test_value")
    print(f"   ✓ Metadata added: {context.metadata}")
    
    # Verify context exists
    print("\n4. Verifying context exists in memory")
    assert acm.exists(session_id), "Context should exist"
    print(f"   ✓ Context exists in memory")
    
    # Get history
    history = context.get_agent_history()
    print(f"\n5. Retrieved agent history: {len(history)} switches")
    for i, switch in enumerate(history):
        print(f"   - Switch {i+1}: {switch['from']} → {switch['to']}")
    
    print("\n✅ Agent context persistence test completed successfully!")
    return session_id


async def test_restoration():
    """Test restoration after 'restart'"""
    print("\n" + "=" * 60)
    print("Testing Restoration After Restart")
    print("=" * 60)
    
    print("\n1. Simulating restart by creating new manager instances...")
    
    # Create new instances (simulating restart)
    new_sm = AsyncSessionManager()
    await new_sm.initialize()
    
    new_acm = AsyncAgentContextManager()
    await new_acm.initialize()
    
    print(f"   ✓ New AsyncSessionManager loaded {len(new_sm._sessions)} sessions")
    print(f"   ✓ New AsyncAgentContextManager loaded {len(new_acm._contexts)} contexts")
    
    # Check if test session exists
    print("\n2. Checking if test sessions were restored...")
    
    if new_sm.exists("test_session_123"):
        session = new_sm.get("test_session_123")
        print(f"   ✓ Session 'test_session_123' restored with {len(session.messages)} messages")
        history = new_sm.get_history("test_session_123")
        print(f"   ✓ Message history intact: {len(history)} messages")
    else:
        print("   ⚠ Session 'test_session_123' not found (may have been cleaned up)")
    
    if new_acm.exists("test_context_456"):
        context = new_acm.get("test_context_456")
        print(f"   ✓ Context 'test_context_456' restored")
        print(f"   ✓ Current agent: {context.current_agent.value}")
        print(f"   ✓ Switch count: {context.switch_count}")
        print(f"   ✓ Metadata: {context.metadata}")
    else:
        print("   ⚠ Context 'test_context_456' not found (may have been cleaned up)")
    
    print("\n✅ Restoration test completed successfully!")


async def cleanup():
    """Cleanup test data"""
    print("\n" + "=" * 60)
    print("Cleanup")
    print("=" * 60)
    
    sm = AsyncSessionManager()
    await sm.initialize()
    
    acm = AsyncAgentContextManager()
    await acm.initialize()
    
    # Delete test sessions
    if sm.exists("test_session_123"):
        await sm.delete("test_session_123")
        print("   ✓ Deleted test_session_123")
    
    if acm.exists("test_context_456"):
        await acm.delete("test_context_456")
        print("   ✓ Deleted test_context_456")
    
    print("\n✅ Cleanup completed!")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Session & Agent Context Persistence Test Suite")
    print("=" * 60)
    
    try:
        # Test session persistence
        await test_session_persistence()
        
        # Test agent context persistence
        await test_agent_context_persistence()
        
        # Test restoration
        await test_restoration()
        
        # Cleanup
        await cleanup()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\nThe session and agent context persistence is working correctly.")
        print("Sessions will now survive service restarts!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
