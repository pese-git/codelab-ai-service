"""
Unit тесты для Entities Tool Context.

Покрытие:
- ToolCall
- ToolSpecification
- ToolExecution
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from app.domain.tool_context.entities import (
    ToolCall,
    ToolSpecification,
    ToolExecution
)
from app.domain.tool_context.value_objects import (
    ToolName,
    ToolCallId,
    ToolArguments,
    ToolResult,
    ToolCategory,
    ToolExecutionMode,
    ToolPermission
)


# ===== ToolCall Tests =====

class TestToolCall:
    """Тесты для ToolCall entity."""
    
    def test_create_tool_call(self):
        """Тест создания вызова инструмента."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("read_file"),
            arguments=ToolArguments.from_dict({"path": "test.py"})
        )
        
        assert tool_call.tool_name == ToolName.from_string("read_file")
        assert tool_call.arguments.get("path") == "test.py"
        assert tool_call.approved is False
    
    def test_create_with_custom_id(self):
        """Тест создания с пользовательским ID."""
        custom_id = ToolCallId.from_string("call_custom123")
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("write_file"),
            arguments=ToolArguments.from_dict({"path": "test.py", "content": "hello"}),
            call_id=custom_id
        )
        
        assert tool_call.id == custom_id
    
    def test_create_with_requires_approval(self):
        """Тест создания с флагом requires_approval."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("execute_command"),
            arguments=ToolArguments.from_dict({"command": "ls"}),
            requires_approval=True
        )
        
        assert tool_call.requires_approval is True
    
    def test_create_generates_domain_event(self):
        """Тест что создание генерирует Domain Event."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("read_file"),
            arguments=ToolArguments.empty()
        )
        
        events = tool_call.domain_events
        assert len(events) == 1
        assert events[0].__class__.__name__ == "ToolCallCreated"
    
    def test_validate_success(self):
        """Тест успешной валидации."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("read_file"),
            arguments=ToolArguments.from_dict({"path": "test.py"})
        )
        
        spec = ToolSpecification.create(
            name=ToolName.from_string("read_file"),
            description="Read file",
            parameters={"required": ["path"], "properties": {"path": {"type": "string"}}},
            category=ToolCategory.file_system(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.read_only()
        )
        
        is_valid, error = tool_call.validate(spec)
        assert is_valid is True
        assert error is None
    
    def test_validate_name_mismatch(self):
        """Тест валидации с несовпадением имени."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("read_file"),
            arguments=ToolArguments.empty()
        )
        
        spec = ToolSpecification.create(
            name=ToolName.from_string("write_file"),
            description="Write file",
            parameters={},
            category=ToolCategory.file_system(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.read_write()
        )
        
        is_valid, error = tool_call.validate(spec)
        assert is_valid is False
        assert "mismatch" in error
    
    def test_mark_approved_success(self):
        """Тест успешного одобрения."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("write_file"),
            arguments=ToolArguments.empty(),
            requires_approval=True
        )
        
        tool_call.mark_approved()
        assert tool_call.approved is True
    
    def test_mark_approved_without_requires_approval_raises_error(self):
        """Тест что одобрение без requires_approval вызывает ошибку."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("read_file"),
            arguments=ToolArguments.empty(),
            requires_approval=False
        )
        
        with pytest.raises(ValueError, match="does not require approval"):
            tool_call.mark_approved()
    
    def test_mark_approved_twice_raises_error(self):
        """Тест что повторное одобрение вызывает ошибку."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("write_file"),
            arguments=ToolArguments.empty(),
            requires_approval=True
        )
        
        tool_call.mark_approved()
        with pytest.raises(ValueError, match="already approved"):
            tool_call.mark_approved()
    
    def test_mark_rejected(self):
        """Тест отклонения вызова."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("execute_command"),
            arguments=ToolArguments.empty(),
            requires_approval=True
        )
        
        tool_call.mark_rejected("User denied")
        events = tool_call.domain_events
        assert any(e.__class__.__name__ == "ToolCallRejected" for e in events)
    
    def test_to_llm_format(self):
        """Тест преобразования в LLM формат."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("read_file"),
            arguments=ToolArguments.from_dict({"path": "test.py"}),
            call_id=ToolCallId.from_string("call_123")
        )
        
        llm_format = tool_call.to_llm_format()
        assert llm_format["id"] == "call_123"
        assert llm_format["type"] == "function"
        assert llm_format["function"]["name"] == "read_file"
    
    def test_to_dict(self):
        """Тест преобразования в словарь."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("write_file"),
            arguments=ToolArguments.from_dict({"path": "test.py", "content": "hello"})
        )
        
        data = tool_call.to_dict()
        assert data["tool_name"] == "write_file"
        assert data["arguments"]["path"] == "test.py"
        assert "created_at" in data


# ===== ToolSpecification Tests =====

class TestToolSpecification:
    """Тесты для ToolSpecification entity."""
    
    def test_create_specification(self):
        """Тест создания спецификации."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("read_file"),
            description="Read file content",
            parameters={"required": ["path"]},
            category=ToolCategory.file_system(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.read_only()
        )
        
        assert spec.name == ToolName.from_string("read_file")
        assert spec.description == "Read file content"
        assert spec.category == ToolCategory.file_system()
    
    def test_create_generates_domain_event(self):
        """Тест что создание генерирует Domain Event."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("write_file"),
            description="Write file",
            parameters={},
            category=ToolCategory.file_system(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.read_write()
        )
        
        events = spec.domain_events
        assert len(events) == 1
        assert events[0].__class__.__name__ == "ToolSpecificationCreated"
    
    def test_validate_arguments_success(self):
        """Тест успешной валидации аргументов."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("read_file"),
            description="Read file",
            parameters={"required": ["path"], "properties": {"path": {"type": "string"}}},
            category=ToolCategory.file_system(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.read_only()
        )
        
        args = ToolArguments.from_dict({"path": "test.py"})
        is_valid, error = spec.validate_arguments(args)
        assert is_valid is True
    
    def test_to_openai_format(self):
        """Тест преобразования в OpenAI формат."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("echo"),
            description="Echo text",
            parameters={"required": ["text"]},
            category=ToolCategory.utility(),
            execution_mode=ToolExecutionMode.local(),
            required_permission=ToolPermission.read_only()
        )
        
        openai_format = spec.to_openai_format()
        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "echo"
        assert openai_format["function"]["description"] == "Echo text"
    
    def test_is_dangerous_for_file_system(self):
        """Тест что FILE_SYSTEM опасный."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("write_file"),
            description="Write file",
            parameters={},
            category=ToolCategory.file_system(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.read_write()
        )
        
        assert spec.is_dangerous() is True
    
    def test_is_not_dangerous_for_utility(self):
        """Тест что UTILITY не опасный."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("echo"),
            description="Echo",
            parameters={},
            category=ToolCategory.utility(),
            execution_mode=ToolExecutionMode.local(),
            required_permission=ToolPermission.read_only()
        )
        
        assert spec.is_dangerous() is False
    
    def test_requires_approval_for_command(self):
        """Тест что COMMAND требует одобрения."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("execute_command"),
            description="Execute command",
            parameters={},
            category=ToolCategory.command(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.execute()
        )
        
        assert spec.requires_approval() is True
    
    def test_is_local_tool(self):
        """Тест проверки локального инструмента."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("calculator"),
            description="Calculator",
            parameters={},
            category=ToolCategory.utility(),
            execution_mode=ToolExecutionMode.local(),
            required_permission=ToolPermission.read_only()
        )
        
        assert spec.is_local_tool() is True
        assert spec.is_ide_tool() is False
    
    def test_is_ide_tool(self):
        """Тест проверки IDE инструмента."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("read_file"),
            description="Read file",
            parameters={},
            category=ToolCategory.file_system(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.read_only()
        )
        
        assert spec.is_ide_tool() is True
        assert spec.is_local_tool() is False
    
    def test_update_description(self):
        """Тест обновления описания."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("echo"),
            description="Old description",
            parameters={},
            category=ToolCategory.utility(),
            execution_mode=ToolExecutionMode.local(),
            required_permission=ToolPermission.read_only()
        )
        
        spec.update_description("New description")
        assert spec.description == "New description"
    
    def test_update_parameters(self):
        """Тест обновления параметров."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("echo"),
            description="Echo",
            parameters={"required": ["text"]},
            category=ToolCategory.utility(),
            execution_mode=ToolExecutionMode.local(),
            required_permission=ToolPermission.read_only()
        )
        
        new_params = {"required": ["text", "repeat"]}
        spec.update_parameters(new_params)
        assert spec.parameters == new_params


# ===== ToolExecution Tests =====

class TestToolExecution:
    """Тесты для ToolExecution entity."""
    
    @pytest.fixture
    def sample_tool_call(self):
        """Fixture для примера вызова инструмента."""
        return ToolCall.create(
            tool_name=ToolName.from_string("read_file"),
            arguments=ToolArguments.from_dict({"path": "test.py"})
        )
    
    def test_start_execution(self, sample_tool_call):
        """Тест начала выполнения."""
        execution = ToolExecution.start(sample_tool_call)
        
        assert execution.id == sample_tool_call.id
        assert execution.tool_call == sample_tool_call
        assert execution.result is None
        assert execution.is_running() is True
    
    def test_start_generates_domain_event(self, sample_tool_call):
        """Тест что start генерирует Domain Event."""
        execution = ToolExecution.start(sample_tool_call)
        
        events = execution.domain_events
        assert len(events) == 1
        assert events[0].__class__.__name__ == "ToolExecutionStarted"
    
    def test_complete_with_success(self, sample_tool_call):
        """Тест успешного завершения."""
        execution = ToolExecution.start(sample_tool_call)
        result = ToolResult.success("File content")
        
        execution.complete(result)
        
        assert execution.is_completed() is True
        assert execution.is_successful() is True
        assert execution.is_failed() is False
        assert execution.result == result
    
    def test_complete_with_error_result(self, sample_tool_call):
        """Тест завершения с результатом-ошибкой."""
        execution = ToolExecution.start(sample_tool_call)
        result = ToolResult.error("File not found")
        
        execution.complete(result)
        
        assert execution.is_completed() is True
        assert execution.error == "File not found"
    
    def test_complete_twice_raises_error(self, sample_tool_call):
        """Тест что повторное завершение вызывает ошибку."""
        execution = ToolExecution.start(sample_tool_call)
        execution.complete(ToolResult.success("OK"))
        
        with pytest.raises(ValueError, match="already completed"):
            execution.complete(ToolResult.success("OK again"))
    
    def test_fail_execution(self, sample_tool_call):
        """Тест завершения с ошибкой."""
        execution = ToolExecution.start(sample_tool_call)
        
        execution.fail("Tool not found")
        
        assert execution.is_failed() is True
        assert execution.is_successful() is False
        assert execution.error == "Tool not found"
    
    def test_fail_generates_domain_event(self, sample_tool_call):
        """Тест что fail генерирует Domain Event."""
        execution = ToolExecution.start(sample_tool_call)
        execution.fail("Error")
        
        events = execution.domain_events
        assert any(e.__class__.__name__ == "ToolExecutionFailed" for e in events)
    
    def test_get_duration_ms_when_running(self, sample_tool_call):
        """Тест получения длительности когда выполняется."""
        execution = ToolExecution.start(sample_tool_call)
        assert execution.get_duration_ms() is None
    
    def test_get_duration_ms_when_completed(self, sample_tool_call):
        """Тест получения длительности после завершения."""
        execution = ToolExecution.start(sample_tool_call)
        execution.complete(ToolResult.success("OK"))
        
        duration = execution.get_duration_ms()
        assert duration is not None
        assert duration >= 0
    
    def test_get_result_content_when_running(self, sample_tool_call):
        """Тест получения контента когда выполняется."""
        execution = ToolExecution.start(sample_tool_call)
        assert execution.get_result_content() is None
    
    def test_get_result_content_when_completed(self, sample_tool_call):
        """Тест получения контента после завершения."""
        execution = ToolExecution.start(sample_tool_call)
        execution.complete(ToolResult.success("File content"))
        
        assert execution.get_result_content() == "File content"
    
    def test_to_dict(self, sample_tool_call):
        """Тест преобразования в словарь."""
        execution = ToolExecution.start(sample_tool_call)
        execution.complete(ToolResult.success("OK"))
        
        data = execution.to_dict()
        assert data["tool_name"] == "read_file"
        assert data["result"] == "OK"
        assert data["is_error"] is False
        assert "duration_ms" in data
