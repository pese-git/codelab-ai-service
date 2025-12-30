from functools import lru_cache
from app.services.session_manager import SessionManager
from app.services.token_buffer_manager import TokenBufferManager

# Временно Singletons через lru_cache (FastAPI DI-best practice)

@lru_cache
def get_session_manager() -> SessionManager:
    return SessionManager()

@lru_cache
def get_token_buffer_manager() -> TokenBufferManager:
    return TokenBufferManager()
