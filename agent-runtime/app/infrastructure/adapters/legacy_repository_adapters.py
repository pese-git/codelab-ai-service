"""
Адаптеры для обратной совместимости legacy repositories.

Эти адаптеры реализуют legacy интерфейсы (SessionRepository, AgentContextRepository)
используя новые DDD repositories (ConversationRepository, AgentRepository).

Это позволяет существующим handlers работать без изменений,
пока идет постепенная миграция на новую архитектуру.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from app.domain.repositories.session_repository import SessionRepository
from app.domain.repositories.agent_context_repository import AgentContextRepository
from app.domain.entities.session import Session
from app.domain.entities.agent_context import AgentContext, AgentType

from app.domain.session_context.repositories.conversation_repository import ConversationRepository
from app.domain.session_context.entities.conversation import Conversation
from app.domain.session_context.value_objects.conversation_id import ConversationId
from app.domain.session_context.value_objects.message import Message

from app.domain.agent_context.repositories.agent_repository import AgentRepository
from app.domain.agent_context.entities.agent import Agent
from app.domain.agent_context.value_objects.agent_id import AgentId


class SessionRepositoryAdapter(SessionRepository):
    """
    Адаптер для SessionRepository, использующий ConversationRepository.
    
    Реализует legacy интерфейс SessionRepository через новый ConversationRepository,
    конвертируя между legacy Session и новым Conversation.
    
    Атрибуты:
        _conversation_repo: Новый repository для разговоров
    
    Пример:
        >>> conversation_repo = ConversationRepositoryImpl(db)
        >>> adapter = SessionRepositoryAdapter(conversation_repo)
        >>> session = await adapter.find_by_id("session-123")
    """
    
    def __init__(self, conversation_repo: ConversationRepository):
        """
        Инициализация адаптера.
        
        Args:
            conversation_repo: Новый repository для разговоров
        """
        self._conversation_repo = conversation_repo
    
    def _conversation_to_session(self, conversation: Conversation) -> Session:
        """
        Конвертировать Conversation в legacy Session.
        
        Args:
            conversation: Новая entity Conversation
            
        Returns:
            Legacy entity Session
        """
        # Конвертировать messages
        messages = []
        for msg in conversation.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "metadata": msg.metadata
            })
        
        # Создать legacy Session
        return Session(
            id=str(conversation.id),
            title=conversation.title,
            messages=messages,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            metadata=conversation.metadata
        )
    
    def _session_to_conversation(self, session: Session) -> Conversation:
        """
        Конвертировать legacy Session в Conversation.
        
        Args:
            session: Legacy entity Session
            
        Returns:
            Новая entity Conversation
        """
        # Конвертировать messages
        messages = []
        for msg in session.messages:
            messages.append(Message(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp", datetime.utcnow()),
                metadata=msg.get("metadata", {})
            ))
        
        # Создать Conversation
        return Conversation(
            id=ConversationId(session.id),
            title=session.title,
            messages=messages,
            created_at=session.created_at,
            updated_at=session.updated_at,
            metadata=session.metadata
        )
    
    async def find_by_id(self, session_id: str) -> Optional[Session]:
        """
        Найти сессию по ID.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Legacy Session если найдена, None иначе
        """
        conversation = await self._conversation_repo.find_by_id(
            ConversationId(session_id)
        )
        
        if not conversation:
            return None
        
        return self._conversation_to_session(conversation)
    
    async def find_active(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Session]:
        """
        Найти активные сессии.
        
        Args:
            limit: Максимальное количество
            offset: Смещение
            
        Returns:
            Список legacy Session
        """
        conversations = await self._conversation_repo.find_active(
            limit=limit,
            offset=offset
        )
        
        return [
            self._conversation_to_session(conv)
            for conv in conversations
        ]
    
    async def save(self, session: Session) -> Session:
        """
        Сохранить сессию.
        
        Args:
            session: Legacy Session для сохранения
            
        Returns:
            Сохраненная legacy Session
        """
        conversation = self._session_to_conversation(session)
        saved_conversation = await self._conversation_repo.save(conversation)
        return self._conversation_to_session(saved_conversation)
    
    async def delete(self, session_id: str) -> bool:
        """
        Удалить сессию.
        
        Args:
            session_id: ID сессии
            
        Returns:
            True если удалена, False иначе
        """
        return await self._conversation_repo.delete(ConversationId(session_id))
    
    async def count_active(self) -> int:
        """
        Подсчитать активные сессии.
        
        Returns:
            Количество активных сессий
        """
        return await self._conversation_repo.count_active()


class AgentContextRepositoryAdapter(AgentContextRepository):
    """
    Адаптер для AgentContextRepository, использующий AgentRepository.
    
    Реализует legacy интерфейс AgentContextRepository через новый AgentRepository,
    конвертируя между legacy AgentContext и новым Agent.
    
    Атрибуты:
        _agent_repo: Новый repository для агентов
    
    Пример:
        >>> agent_repo = AgentRepositoryImpl(db)
        >>> adapter = AgentContextRepositoryAdapter(agent_repo)
        >>> context = await adapter.find_by_session_id("session-123")
    """
    
    def __init__(self, agent_repo: AgentRepository):
        """
        Инициализация адаптера.
        
        Args:
            agent_repo: Новый repository для агентов
        """
        self._agent_repo = agent_repo
    
    def _agent_to_context(self, agent: Agent) -> AgentContext:
        """
        Конвертировать Agent в legacy AgentContext.
        
        Args:
            agent: Новая entity Agent
            
        Returns:
            Legacy entity AgentContext
        """
        return AgentContext(
            id=str(agent.id),
            session_id=agent.conversation_id,
            agent_type=AgentType(agent.capabilities.agent_type),
            state=agent.state,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            metadata=agent.metadata
        )
    
    def _context_to_agent(self, context: AgentContext) -> Agent:
        """
        Конвертировать legacy AgentContext в Agent.
        
        Args:
            context: Legacy entity AgentContext
            
        Returns:
            Новая entity Agent
        """
        from app.domain.agent_context.value_objects.agent_capabilities import AgentCapabilities
        
        return Agent(
            id=AgentId(context.id),
            conversation_id=context.session_id,
            capabilities=AgentCapabilities(
                agent_type=context.agent_type.value,
                can_execute_tools=True,
                can_switch_agents=True
            ),
            state=context.state,
            created_at=context.created_at,
            updated_at=context.updated_at,
            metadata=context.metadata
        )
    
    async def find_by_session_id(self, session_id: str) -> Optional[AgentContext]:
        """
        Найти контекст агента по ID сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Legacy AgentContext если найден, None иначе
        """
        agent = await self._agent_repo.find_by_conversation_id(session_id)
        
        if not agent:
            return None
        
        return self._agent_to_context(agent)
    
    async def get(self, id: str) -> Optional[AgentContext]:
        """
        Получить контекст по ID.
        
        Args:
            id: ID контекста
            
        Returns:
            Legacy AgentContext если найден, None иначе
        """
        agent = await self._agent_repo.find_by_id(AgentId(id))
        
        if not agent:
            return None
        
        return self._agent_to_context(agent)
    
    async def save(self, context: AgentContext) -> AgentContext:
        """
        Сохранить контекст агента.
        
        Args:
            context: Legacy AgentContext для сохранения
            
        Returns:
            Сохраненный legacy AgentContext
        """
        agent = self._context_to_agent(context)
        saved_agent = await self._agent_repo.save(agent)
        return self._agent_to_context(saved_agent)
    
    async def delete(self, id: str) -> bool:
        """
        Удалить контекст агента.
        
        Args:
            id: ID контекста
            
        Returns:
            True если удален, False иначе
        """
        return await self._agent_repo.delete(AgentId(id))
    
    async def find_all_by_session_id(self, session_id: str) -> List[AgentContext]:
        """
        Найти все контексты для сессии.
        
        Args:
            session_id: ID сессии
            
        Returns:
            Список legacy AgentContext
        """
        agents = await self._agent_repo.find_all_by_conversation_id(session_id)
        
        return [
            self._agent_to_context(agent)
            for agent in agents
        ]
