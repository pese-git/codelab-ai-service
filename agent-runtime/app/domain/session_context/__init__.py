"""
Session Context - Bounded Context для управления conversations.

Этот bounded context отвечает за:
- Управление жизненным циклом conversations
- Работу с сообщениями и историей
- Snapshot и восстановление состояния
- Очистку tool messages для изоляции контекста

Архитектура:
- Value Objects: ConversationId, MessageContent, MessageCollection
- Entities: Conversation
- Domain Services: ConversationSnapshotService, ToolMessageCleanupService
- Events: ConversationStarted, MessageAdded, etc.
- Repository: ConversationRepository interface
"""

# Value Objects
from .value_objects import (
    ConversationId,
    MessageContent,
    MessageCollection,
)

# Entities
from .entities import Conversation

# Domain Services
from .services import (
    ConversationSnapshotService,
    ToolMessageCleanupService,
)

# Events
from .events import (
    ConversationStarted,
    MessageAdded,
    ConversationDeactivated,
    ConversationActivated,
    MessagesCleared,
    ToolMessagesCleared,
)

# Repositories
from .repositories import ConversationRepository

__all__ = [
    # Value Objects
    "ConversationId",
    "MessageContent",
    "MessageCollection",
    
    # Entities
    "Conversation",
    
    # Domain Services
    "ConversationSnapshotService",
    "ToolMessageCleanupService",
    
    # Events
    "ConversationStarted",
    "MessageAdded",
    "ConversationDeactivated",
    "ConversationActivated",
    "MessagesCleared",
    "ToolMessagesCleared",
    
    # Repositories
    "ConversationRepository",
]
