"""
Тесты для прикладного слоя (Application Layer).

Проверяет корректность работы Commands, Queries и DTO.
"""

import pytest
from datetime import datetime, timezone

from app.application.commands import (
    CreateSessionCommand,
    AddMessageCommand,
    SwitchAgentCommand
)
from app.application.queries import (
    GetSessionQuery,
    ListSessionsQuery,
    GetAgentContextQuery
)
from app.application.dto import (
    SessionDTO,
    SessionListItemDTO,
    MessageDTO,
    AgentContextDTO,
    AgentSwitchDTO
)
from app.domain.entities import Message, Session, AgentContext, AgentType


# ==================== Тесты Commands ====================

class TestCommands:
    """Тесты для команд"""
    
    def test_create_session_command(self):
        """Тест создания команды CreateSession"""
        command = CreateSessionCommand(session_id="session-1")
        
        assert command.session_id == "session-1"
        
        # Команды неизменяемы
        with pytest.raises(Exception):
            command.session_id = "session-2"
    
    def test_create_session_command_without_id(self):
        """Тест создания команды без ID (автогенерация)"""
        command = CreateSessionCommand()
        
        assert command.session_id is None
    
    def test_add_message_command(self):
        """Тест создания команды AddMessage"""
        command = AddMessageCommand(
            session_id="session-1",
            role="user",
            content="Привет!"
        )
        
        assert command.session_id == "session-1"
        assert command.role == "user"
        assert command.content == "Привет!"
    
    def test_switch_agent_command(self):
        """Тест создания команды SwitchAgent"""
        command = SwitchAgentCommand(
            session_id="session-1",
            target_agent="coder",
            reason="Coding task detected"
        )
        
        assert command.session_id == "session-1"
        assert command.target_agent == "coder"
        assert command.reason == "Coding task detected"


# ==================== Тесты Queries ====================

class TestQueries:
    """Тесты для запросов"""
    
    def test_get_session_query(self):
        """Тест создания запроса GetSession"""
        query = GetSessionQuery(
            session_id="session-1",
            include_messages=True
        )
        
        assert query.session_id == "session-1"
        assert query.include_messages is True
        
        # Запросы неизменяемы
        with pytest.raises(Exception):
            query.session_id = "session-2"
    
    def test_list_sessions_query(self):
        """Тест создания запроса ListSessions"""
        query = ListSessionsQuery(
            limit=10,
            offset=0,
            active_only=True
        )
        
        assert query.limit == 10
        assert query.offset == 0
        assert query.active_only is True
    
    def test_list_sessions_query_defaults(self):
        """Тест значений по умолчанию для ListSessions"""
        query = ListSessionsQuery()
        
        assert query.limit == 100
        assert query.offset == 0
        assert query.active_only is True
    
    def test_get_agent_context_query(self):
        """Тест создания запроса GetAgentContext"""
        query = GetAgentContextQuery(
            session_id="session-1",
            include_history=True
        )
        
        assert query.session_id == "session-1"
        assert query.include_history is True


# ==================== Тесты DTO ====================

class TestDTO:
    """Тесты для Data Transfer Objects"""
    
    def test_message_dto_from_entity(self):
        """Тест создания MessageDTO из сущности"""
        message = Message(
            id="msg-1",
            role="user",
            content="Привет!"
        )
        
        dto = MessageDTO.from_entity(message)
        
        assert dto.id == "msg-1"
        assert dto.role == "user"
        assert dto.content == "Привет!"
    
    def test_message_dto_to_llm_format(self):
        """Тест преобразования MessageDTO в формат LLM"""
        dto = MessageDTO(
            id="msg-1",
            role="user",
            content="Привет!",
            created_at=datetime.now(timezone.utc)
        )
        
        llm_format = dto.to_llm_format()
        
        assert llm_format["role"] == "user"
        assert llm_format["content"] == "Привет!"
        assert "id" not in llm_format  # ID не передается в LLM
    
    def test_session_dto_from_entity(self):
        """Тест создания SessionDTO из сущности"""
        session = Session(id="session-1")
        session.add_message(Message(id="msg-1", role="user", content="Hi"))
        
        dto = SessionDTO.from_entity(session, include_messages=False)
        
        assert dto.id == "session-1"
        assert dto.message_count == 1
        assert dto.is_active is True
        assert dto.messages is None  # Не включены
    
    def test_session_dto_with_messages(self):
        """Тест SessionDTO с включенными сообщениями"""
        session = Session(id="session-1")
        session.add_message(Message(id="msg-1", role="user", content="Hi"))
        
        dto = SessionDTO.from_entity(session, include_messages=True)
        
        assert dto.messages is not None
        assert len(dto.messages) == 1
        assert dto.messages[0].id == "msg-1"
    
    def test_session_list_item_dto(self):
        """Тест создания SessionListItemDTO"""
        session = Session(id="session-1", title="Test Session")
        
        dto = SessionListItemDTO.from_entity(session, current_agent="coder")
        
        assert dto.id == "session-1"
        assert dto.title == "Test Session"
        assert dto.current_agent == "coder"
    
    def test_agent_context_dto_from_entity(self):
        """Тест создания AgentContextDTO из сущности"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1",
            current_agent=AgentType.CODER
        )
        
        dto = AgentContextDTO.from_entity(context, include_history=False)
        
        assert dto.id == "ctx-1"
        assert dto.session_id == "session-1"
        assert dto.current_agent == "coder"
        assert dto.switch_count == 0
        assert dto.switch_history is None  # Не включена
    
    def test_agent_context_dto_with_history(self):
        """Тест AgentContextDTO с историей переключений"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1"
        )
        context.switch_to(AgentType.CODER, "Coding task")
        
        dto = AgentContextDTO.from_entity(context, include_history=True)
        
        assert dto.switch_history is not None
        assert len(dto.switch_history) == 1
        assert dto.switch_history[0].to_agent == "coder"
    
    def test_agent_switch_dto_from_entity(self):
        """Тест создания AgentSwitchDTO из сущности"""
        context = AgentContext(id="ctx-1", session_id="session-1")
        switch = context.switch_to(
            AgentType.CODER,
            "Coding task",
            confidence="high"
        )
        
        dto = AgentSwitchDTO.from_entity(switch)
        
        assert dto.from_agent == "orchestrator"
        assert dto.to_agent == "coder"
        assert dto.reason == "Coding task"
        assert dto.confidence == "high"
