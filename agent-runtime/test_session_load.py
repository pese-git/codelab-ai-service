"""
Quick test to verify session loading works correctly
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.database import Database
from app.services.session_manager import SessionManager

def test_load_session():
    """Test loading an existing session"""
    db = Database()
    session_manager = SessionManager(db)
    
    # List all sessions
    sessions = db.list_all_sessions()
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
    session_data = db.load_session(test_session_id)
    if session_data:
        print(f"✓ Loaded from DB: {len(session_data['messages'])} messages")
        for i, msg in enumerate(session_data['messages']):
            print(f"  {i+1}. {msg['role']}: {msg['content'][:50]}...")
    else:
        print("✗ Failed to load from DB")
        return
    
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
    test_load_session()
