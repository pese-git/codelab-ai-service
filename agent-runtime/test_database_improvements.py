"""
Test script for improved database structure.

Tests:
- Session creation and retrieval
- Message storage and pagination
- Agent context management
- Agent switch history
- Statistics and analytics
- Soft delete functionality
"""
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.database import Database
from app.agents.base_agent import AgentType


def test_session_operations(db: Database):
    """Test basic session operations"""
    print("\n=== Testing Session Operations ===")
    
    session_id = "test_session_001"
    
    # Create session with messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you!"}
    ]
    
    db.save_session(session_id, messages, datetime.utcnow())
    print(f"✓ Created session: {session_id}")
    
    # Load session
    loaded = db.load_session(session_id)
    assert loaded is not None, "Session should exist"
    assert len(loaded["messages"]) == 3, "Should have 3 messages"
    print(f"✓ Loaded session with {len(loaded['messages'])} messages")
    
    # List sessions
    sessions = db.list_all_sessions()
    assert session_id in sessions, "Session should be in list"
    print(f"✓ Listed {len(sessions)} sessions")
    
    return session_id


def test_message_pagination(db: Database, session_id: str):
    """Test message pagination"""
    print("\n=== Testing Message Pagination ===")
    
    # Add more messages
    messages = []
    for i in range(100):
        messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i}"
        })
    
    db.save_session(session_id, messages, datetime.utcnow())
    print(f"✓ Saved {len(messages)} messages")
    
    # Test pagination
    page1 = db.get_messages_paginated(session_id, page=1, page_size=20)
    assert len(page1) == 20, "First page should have 20 messages"
    print(f"✓ Page 1: {len(page1)} messages")
    
    page2 = db.get_messages_paginated(session_id, page=2, page_size=20)
    assert len(page2) == 20, "Second page should have 20 messages"
    print(f"✓ Page 2: {len(page2)} messages")
    
    # Verify different messages
    assert page1[0]["content"] != page2[0]["content"], "Pages should have different messages"
    print("✓ Pagination working correctly")


def test_session_stats(db: Database, session_id: str):
    """Test session statistics"""
    print("\n=== Testing Session Statistics ===")
    
    stats = db.get_session_stats(session_id)
    assert stats is not None, "Stats should exist"
    assert stats["message_count"] > 0, "Should have messages"
    
    print(f"✓ Session stats:")
    print(f"  - Messages: {stats['message_count']}")
    print(f"  - Total tokens: {stats['total_tokens']}")
    print(f"  - Created: {stats['created_at']}")
    print(f"  - Last activity: {stats['last_activity']}")


def test_agent_context(db: Database, session_id: str):
    """Test agent context operations"""
    print("\n=== Testing Agent Context ===")
    
    # Create agent context
    agent_history = [
        {
            "from": None,
            "to": "orchestrator",
            "reason": "Initial agent",
            "timestamp": datetime.utcnow().isoformat()
        },
        {
            "from": "orchestrator",
            "to": "coder",
            "reason": "User requested code changes",
            "timestamp": datetime.utcnow().isoformat()
        }
    ]
    
    db.save_agent_context(
        session_id=session_id,
        current_agent="coder",
        agent_history=agent_history,
        metadata={"project": "test_project"},
        created_at=datetime.utcnow(),
        last_switch_at=datetime.utcnow(),
        switch_count=1
    )
    print(f"✓ Created agent context for {session_id}")
    
    # Load context
    context = db.load_agent_context(session_id)
    assert context is not None, "Context should exist"
    assert context["current_agent"] == "coder", "Current agent should be coder"
    assert len(context["agent_history"]) == 2, "Should have 2 history entries"
    print(f"✓ Loaded context: current_agent={context['current_agent']}")
    
    # Get switch history
    switches = db.get_agent_switch_history(session_id)
    assert len(switches) == 2, "Should have 2 switches"
    print(f"✓ Retrieved {len(switches)} agent switches")
    
    for i, switch in enumerate(switches):
        print(f"  Switch {i+1}: {switch['from_agent']} -> {switch['to_agent']}")


def test_soft_delete(db: Database):
    """Test soft delete functionality"""
    print("\n=== Testing Soft Delete ===")
    
    session_id = "test_session_delete"
    
    # Create session
    messages = [{"role": "user", "content": "Test message"}]
    db.save_session(session_id, messages, datetime.utcnow())
    print(f"✓ Created session: {session_id}")
    
    # Verify it exists
    sessions = db.list_all_sessions(include_deleted=False)
    assert session_id in sessions, "Session should exist"
    
    # Soft delete
    deleted = db.delete_session(session_id, soft=True)
    assert deleted, "Delete should succeed"
    print(f"✓ Soft deleted session: {session_id}")
    
    # Verify it's not in active list
    sessions = db.list_all_sessions(include_deleted=False)
    assert session_id not in sessions, "Session should not be in active list"
    print("✓ Session not in active list")
    
    # Verify it's in deleted list
    all_sessions = db.list_all_sessions(include_deleted=True)
    assert session_id in all_sessions, "Session should be in deleted list"
    print("✓ Session in deleted list")


def test_cleanup(db: Database):
    """Test cleanup operations"""
    print("\n=== Testing Cleanup Operations ===")
    
    # Create old session
    old_session_id = "test_session_old"
    messages = [{"role": "user", "content": "Old message"}]
    
    # Save with old timestamp
    old_time = datetime.utcnow() - timedelta(hours=25)
    db.save_session(old_session_id, messages, old_time)
    print(f"✓ Created old session: {old_session_id}")
    
    # Run cleanup
    cleaned = db.cleanup_old_sessions(max_age_hours=24)
    print(f"✓ Cleaned up {cleaned} old sessions")
    
    # Verify old session is soft deleted
    sessions = db.list_all_sessions(include_deleted=False)
    assert old_session_id not in sessions, "Old session should be cleaned up"
    print("✓ Old session cleaned up successfully")


def test_backward_compatibility(db: Database):
    """Test backward compatibility with existing code"""
    print("\n=== Testing Backward Compatibility ===")
    
    session_id = "test_compat_session"
    
    # Test old-style message format
    messages = [
        {"role": "user", "content": "Test"},
        {"role": "assistant", "content": "Response", "tool_calls": [
            {"id": "call_123", "type": "function", "function": {"name": "test_tool", "arguments": "{}"}}
        ]},
        {"role": "tool", "content": "Result", "tool_call_id": "call_123", "name": "test_tool"}
    ]
    
    db.save_session(session_id, messages, datetime.utcnow())
    loaded = db.load_session(session_id)
    
    assert loaded is not None, "Session should load"
    assert len(loaded["messages"]) == 3, "Should have all messages"
    assert loaded["messages"][1].get("tool_calls") is not None, "Tool calls should be preserved"
    assert loaded["messages"][2].get("tool_call_id") == "call_123", "Tool call ID should be preserved"
    
    print("✓ Backward compatibility maintained")
    print("✓ Tool calls and tool responses work correctly")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Improved Database Structure")
    print("=" * 60)
    
    # Use test database
    db = Database(db_url="sqlite:///data/test_agent_runtime.db")
    
    try:
        # Run tests
        session_id = test_session_operations(db)
        test_message_pagination(db, session_id)
        test_session_stats(db, session_id)
        test_agent_context(db, session_id)
        test_soft_delete(db)
        test_cleanup(db)
        test_backward_compatibility(db)
        
        print("\n" + "=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
        
        # Show summary
        print("\n=== Database Summary ===")
        all_sessions = db.list_all_sessions(include_deleted=True)
        active_sessions = db.list_all_sessions(include_deleted=False)
        print(f"Total sessions: {len(all_sessions)}")
        print(f"Active sessions: {len(active_sessions)}")
        print(f"Deleted sessions: {len(all_sessions) - len(active_sessions)}")
        
        contexts = db.list_all_contexts()
        print(f"Agent contexts: {len(contexts)}")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
