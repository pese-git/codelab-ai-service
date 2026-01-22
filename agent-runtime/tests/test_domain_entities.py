"""
Тесты для доменных сущностей.

Проверяет корректность работы Message, Session и AgentContext.
"""

import pytest
import uuid
from datetime import datetime, timezone

from app.domain.entities.message import Message
from app.domain.entities.session import Session
from app.domain.entities.agent_context import AgentContext, AgentType, AgentSwitch
from app.core.errors import (
    MessageValidationError,
    AgentSwitchError
)


# ==================== Тесты Message ====================

class TestMessage:
    """Тесты для сущности Message"""
    
    def test_create_user_message(self):
        """Тест создания пользовательского сообщения"""
        msg = Message(
            id="msg-1",
            role="user",
            content="Привет, создай новый файл"
        )
        
        assert msg.id == "msg-1"
        assert msg.role == "user"
        assert msg.content == "Привет, создай новый файл"
        assert msg.is_user_message()
        assert not msg.is_assistant_message()
        assert not msg.has_tool_calls()
    
    def test_create_assistant_message_with_tool_calls(self):
        """Тест создания сообщения ассистента с вызовами инструментов"""
        msg = Message(
            id="msg-2",
            role="assistant",
            content="",
            tool_calls=[{
                "id": "call-1",
                "tool_name": "write_file",
                "arguments": {"path": "test.py", "content": "print('hello')"}
            }]
        )
        
        assert msg.is_assistant_message()
        assert msg.has_tool_calls()
        assert len(msg.tool_calls) == 1
    
    def test_create_tool_message(self):
        """Тест создания сообщения от инструмента"""
        msg = Message(
            id="msg-3",
            role="tool",
            content='{"status": "success"}',
            name="write_file",
            tool_call_id="call-1"
        )
        
        assert msg.is_tool_message()
        assert msg.name == "write_file"
        assert msg.tool_call_id == "call-1"
    
    def test_message_to_llm_format(self):
        """Тест преобразования в формат LLM"""
        msg = Message(
            id="msg-1",
            role="user",
            content="Привет"
        )
        
        llm_format = msg.to_llm_format()
        
        assert llm_format["role"] == "user"
        assert llm_format["content"] == "Привет"
        assert "id" not in llm_format  # ID не передается в LLM
    
    def test_message_from_llm_format(self):
        """Тест создания из формата LLM"""
        llm_data = {
            "role": "assistant",
            "content": "Конечно, создам файл"
        }
        
        msg = Message.from_llm_format(llm_data, "msg-2")
        
        assert msg.id == "msg-2"
        assert msg.role == "assistant"
        assert msg.content == "Конечно, создам файл"
    
    def test_get_content_length(self):
        """Тест получения длины содержимого"""
        msg = Message(
            id="msg-1",
            role="user",
            content="Привет, мир!"
        )
        
        assert msg.get_content_length() == len("Привет, мир!")


# ==================== Тесты Session ====================

class TestSession:
    """Тесты для сущности Session"""
    
    def test_create_session(self):
        """Тест создания сессии"""
        session = Session(id="session-1")
        
        assert session.id == "session-1"
        assert session.is_active
        assert session.is_empty()
        assert session.get_message_count() == 0
    
    def test_add_message(self):
        """Тест добавления сообщения"""
        session = Session(id="session-1")
        msg = Message(
            id="msg-1",
            role="user",
            content="Привет"
        )
        
        session.add_message(msg)
        
        assert session.get_message_count() == 1
        assert not session.is_empty()
        assert session.messages[0].id == "msg-1"
    
    def test_auto_set_title_from_first_message(self):
        """Тест автоматической установки заголовка"""
        session = Session(id="session-1")
        
        assert session.title is None
        
        msg = Message(
            id="msg-1",
            role="user",
            content="Создай новый Flutter виджет для профиля пользователя"
        )
        session.add_message(msg)
        
        assert session.title is not None
        assert "Создай новый Flutter виджет" in session.title
    
    def test_get_recent_messages(self):
        """Тест получения последних сообщений"""
        session = Session(id="session-1")
        
        # Добавить 10 сообщений
        for i in range(10):
            msg = Message(
                id=f"msg-{i}",
                role="user",
                content=f"Сообщение {i}"
            )
            session.add_message(msg)
        
        # Получить последние 5
        recent = session.get_recent_messages(limit=5)
        
        assert len(recent) == 5
        assert recent[0].id == "msg-5"
        assert recent[-1].id == "msg-9"
    
    def test_get_messages_by_role(self):
        """Тест получения сообщений по роли"""
        session = Session(id="session-1")
        
        # Добавить сообщения разных ролей
        session.add_message(Message(id="msg-1", role="user", content="Q1"))
        session.add_message(Message(id="msg-2", role="assistant", content="A1"))
        session.add_message(Message(id="msg-3", role="user", content="Q2"))
        
        user_messages = session.get_messages_by_role("user")
        
        assert len(user_messages) == 2
        assert all(msg.role == "user" for msg in user_messages)
    
    def test_deactivate_session(self):
        """Тест деактивации сессии"""
        session = Session(id="session-1")
        
        assert session.is_active
        
        session.deactivate(reason="User logged out")
        
        assert not session.is_active
        assert session.metadata["deactivation_reason"] == "User logged out"
    
    def test_cannot_add_message_to_inactive_session(self):
        """Тест: нельзя добавить сообщение в неактивную сессию"""
        session = Session(id="session-1")
        session.deactivate()
        
        msg = Message(id="msg-1", role="user", content="Привет")
        
        with pytest.raises(ValueError, match="неактивную сессию"):
            session.add_message(msg)
    
    def test_max_messages_limit(self):
        """Тест ограничения на количество сообщений"""
        session = Session(id="session-1", max_messages=5)
        
        # Добавить 5 сообщений - должно работать
        for i in range(5):
            msg = Message(id=f"msg-{i}", role="user", content=f"Msg {i}")
            session.add_message(msg)
        
        # Попытка добавить 6-е сообщение - должна вызвать ошибку
        msg = Message(id="msg-6", role="user", content="Too many")
        
        with pytest.raises(MessageValidationError):
            session.add_message(msg)
    
    def test_get_history_for_llm(self):
        """Тест получения истории для LLM"""
        session = Session(id="session-1")
        
        session.add_message(Message(id="msg-1", role="user", content="Q1"))
        session.add_message(Message(id="msg-2", role="assistant", content="A1"))
        
        history = session.get_history_for_llm()
        
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert "id" not in history[0]  # ID не передается в LLM


# ==================== Тесты AgentContext ====================

class TestAgentContext:
    """Тесты для сущности AgentContext"""
    
    def test_create_context(self):
        """Тест создания контекста агента"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1"
        )
        
        assert context.id == "ctx-1"
        assert context.session_id == "session-1"
        assert context.current_agent == AgentType.ORCHESTRATOR
        assert context.switch_count == 0
    
    def test_switch_agent(self):
        """Тест переключения агента"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1",
            current_agent=AgentType.ORCHESTRATOR
        )
        
        switch = context.switch_to(
            target_agent=AgentType.CODER,
            reason="Coding task detected"
        )
        
        assert context.current_agent == AgentType.CODER
        assert context.switch_count == 1
        assert len(context.switch_history) == 1
        assert switch.from_agent == AgentType.ORCHESTRATOR
        assert switch.to_agent == AgentType.CODER
    
    def test_cannot_switch_to_same_agent(self):
        """Тест: нельзя переключиться на того же агента"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1",
            current_agent=AgentType.CODER
        )
        
        with pytest.raises(AgentSwitchError, match="уже активен"):
            context.switch_to(
                target_agent=AgentType.CODER,
                reason="Test"
            )
    
    def test_max_switches_limit(self):
        """Тест ограничения на количество переключений"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1",
            max_switches=3
        )
        
        # 3 переключения - должно работать
        context.switch_to(AgentType.CODER, "Switch 1")
        context.switch_to(AgentType.ARCHITECT, "Switch 2")
        context.switch_to(AgentType.DEBUG, "Switch 3")
        
        # 4-е переключение - должно вызвать ошибку
        with pytest.raises(AgentSwitchError, match="Превышен лимит"):
            context.switch_to(AgentType.ASK, "Switch 4")
    
    def test_can_switch_to(self):
        """Тест проверки возможности переключения"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1",
            current_agent=AgentType.ORCHESTRATOR
        )
        
        # Можно переключиться на другого агента
        assert context.can_switch_to(AgentType.CODER)
        
        # Нельзя переключиться на того же агента
        assert not context.can_switch_to(AgentType.ORCHESTRATOR)
    
    def test_get_switch_history(self):
        """Тест получения истории переключений"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1"
        )
        
        context.switch_to(AgentType.CODER, "Coding task")
        context.switch_to(AgentType.DEBUG, "Debug issue")
        
        history = context.get_switch_history()
        
        assert len(history) == 2
        assert history[0]["from"] == "orchestrator"
        assert history[0]["to"] == "coder"
        assert history[1]["from"] == "coder"
        assert history[1]["to"] == "debug"
    
    def test_reset_to_orchestrator(self):
        """Тест сброса к Orchestrator"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1",
            current_agent=AgentType.CODER
        )
        
        context.reset_to_orchestrator(reason="New task")
        
        assert context.current_agent == AgentType.ORCHESTRATOR
        assert context.switch_count == 1
    
    def test_add_and_get_metadata(self):
        """Тест добавления и получения метаданных"""
        context = AgentContext(
            id="ctx-1",
            session_id="session-1"
        )
        
        context.add_metadata("user_preference", "verbose")
        context.add_metadata("language", "python")
        
        assert context.get_metadata("user_preference") == "verbose"
        assert context.get_metadata("language") == "python"
        assert context.get_metadata("nonexistent", "default") == "default"


# ==================== Тесты доменных событий ====================

class TestDomainEvents:
    """Тесты для доменных событий"""
    
    def test_session_created_event(self):
        """Тест события создания сессии"""
        from app.domain.events.session_events import SessionCreated
        
        event = SessionCreated(
            aggregate_id="session-1",
            session_id="session-1",
            created_by="user"
        )
        
        assert event.session_id == "session-1"
        assert event.created_by == "user"
        assert event.get_event_name() == "SessionCreated"
    
    def test_message_received_event(self):
        """Тест события получения сообщения"""
        from app.domain.events.session_events import MessageReceived
        
        event = MessageReceived(
            aggregate_id="session-1",
            session_id="session-1",
            message_id="msg-1",
            role="user",
            content_length=100
        )
        
        assert event.message_id == "msg-1"
        assert event.role == "user"
        assert event.content_length == 100
    
    def test_agent_switched_event(self):
        """Тест события переключения агента"""
        from app.domain.events.agent_events import AgentSwitched
        
        event = AgentSwitched(
            aggregate_id="session-1",
            session_id="session-1",
            from_agent="orchestrator",
            to_agent="coder",
            reason="Coding task",
            switch_count=1
        )
        
        assert event.from_agent == "orchestrator"
        assert event.to_agent == "coder"
        assert event.switch_count == 1
    
    def test_task_completed_event(self):
        """Тест события завершения задачи"""
        from app.domain.events.agent_events import TaskCompleted
        
        event = TaskCompleted(
            aggregate_id="session-1",
            session_id="session-1",
            agent_type="coder",
            success=True,
            result_summary="Created widget",
            duration_seconds=15.5
        )
        
        assert event.success is True
        assert event.duration_seconds == 15.5
