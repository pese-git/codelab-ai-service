"""
Quick test to verify session loading works correctly with async interface
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.database import get_database_service, get_db
from app.services.session_manager_async import AsyncSessionManager


async def test_load_session():
    """Test loading an existing session"""
    db_service = get_database_service()
    session_manager = AsyncSessionManager()
    await session_manager.initialize()
    
    # List all sessions
    async for db in get_db():
        sessions = await db_service.list_all_sessions(db)
        print(f"Found {len(sessions)} sessions:")
        for sid in sessions:
            print(f"  - {sid}")
        
        if not sessions:
            print("\nNo sessions found in database!")
            return
        
        # Test loading first session
        test_session_id = sessions[0]
        print(f"\nTesting session: {test_session_id}")
        
        # Load from database
        session_data = await db_service.load_session(db, test_session_id)
        if session_data:
            print(f"✓ Loaded from DB: {len(session_data['messages'])} messages")
            for i, msg in enumerate(session_data['messages']):
                content = msg.get('content', '')
                if content:
                    print(f"  {i+1}. {msg['role']}: {content[:50]}...")
                else:
                    print(f"  {i+1}. {msg['role']}: [no content]")
        else:
            print("✗ Failed to load from DB")
            return
        
        break
    
    # Load from session manager
    session_state = session_manager.get(test_session_id)
    if session_state:
        print(f"✓ Loaded from SessionManager: {len(session_state.messages)} messages")
    else:
        print("✗ Failed to load from SessionManager")
        return
    
    # Get history
    history = session_manager.get_history(test_session_id)
    print(f"✓ Got history: {len(history)} messages")
    
    print("\n✓ Session loading works correctly!")


if __name__ == "__main__":
    asyncio.run(test_load_session())
