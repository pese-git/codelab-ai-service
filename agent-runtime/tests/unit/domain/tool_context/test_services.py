"""
Unit тесты для Domain Services Tool Context.

Покрытие:
- ToolValidator
"""

import pytest

from app.domain.tool_context.services import ToolValidator
from app.domain.tool_context.entities import ToolCall, ToolSpecification
from app.domain.tool_context.value_objects import (
    ToolName,
    ToolArguments,
    ToolCategory,
    ToolExecutionMode,
    ToolPermission
)


# ===== ToolValidator Tests =====

class TestToolValidator:
    """Тесты для ToolValidator service."""
    
    @pytest.fixture
    def validator(self):
        """Fixture для validator."""
        return ToolValidator()
    
    @pytest.fixture
    def sample_spec(self):
        """Fixture для примера спецификации."""
        return ToolSpecification.create(
            name=ToolName.from_string("read_file"),
            description="Read file content",
            parameters={
                "required": ["path"],
                "properties": {
                    "path": {"type": "string"},
                    "encoding": {"type": "string"}
                }
            },
            category=ToolCategory.file_system(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.read_only()
        )
    
    def test_validate_tool_call_success(self, validator, sample_spec):
        """Тест успешной валидации вызова."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("read_file"),
            arguments=ToolArguments.from_dict({"path": "test.py"})
        )
        
        is_valid, error = validator.validate_tool_call(tool_call, sample_spec)
        assert is_valid is True
        assert error is None
    
    def test_validate_tool_call_name_mismatch(self, validator, sample_spec):
        """Тест валидации с несовпадением имени."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("write_file"),
            arguments=ToolArguments.from_dict({"path": "test.py"})
        )
        
        is_valid, error = validator.validate_tool_call(tool_call, sample_spec)
        assert is_valid is False
        assert "mismatch" in error
    
    def test_validate_tool_call_missing_required_field(self, validator, sample_spec):
        """Тест валидации с отсутствующим обязательным полем."""
        tool_call = ToolCall.create(
            tool_name=ToolName.from_string("read_file"),
            arguments=ToolArguments.from_dict({"encoding": "utf-8"})  # path отсутствует
        )
        
        is_valid, error = validator.validate_tool_call(tool_call, sample_spec)
        assert is_valid is False
        assert "Invalid arguments" in error
    
    def test_validate_arguments_success(self, validator):
        """Тест успешной валидации аргументов."""
        args = ToolArguments.from_dict({"path": "test.py", "encoding": "utf-8"})
        schema = {
            "required": ["path"],
            "properties": {
                "path": {"type": "string"},
                "encoding": {"type": "string"}
            }
        }
        
        is_valid, errors = validator.validate_arguments(args, schema)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_arguments_missing_required(self, validator):
        """Тест валидации с отсутствующим обязательным полем."""
        args = ToolArguments.from_dict({"encoding": "utf-8"})
        schema = {"required": ["path"]}
        
        is_valid, errors = validator.validate_arguments(args, schema)
        assert is_valid is False
        assert len(errors) > 0
    
    def test_validate_permissions_allowed(self, validator, sample_spec):
        """Тест валидации разрешенных прав."""
        user_permission = ToolPermission.read_write()
        
        has_access = validator.validate_permissions(sample_spec, user_permission)
        assert has_access is True
    
    def test_validate_permissions_denied(self, validator):
        """Тест валидации запрещенных прав."""
        spec = ToolSpecification.create(
            name=ToolName.from_string("execute_command"),
            description="Execute command",
            parameters={},
            category=ToolCategory.command(),
            execution_mode=ToolExecutionMode.ide(),
            required_permission=ToolPermission.execute()
        )
        
        user_permission = ToolPermission.read_only()
        
        has_access = validator.validate_permissions(spec, user_permission)
        assert has_access is False
    
    def test_validate_required_fields_success(self, validator):
        """Тест успешной валидации обязательных полей."""
        args = ToolArguments.from_dict({"path": "test.py", "content": "hello"})
        required = ["path", "content"]
        
        is_valid, missing = validator.validate_required_fields(args, required)
        assert is_valid is True
        assert len(missing) == 0
    
    def test_validate_required_fields_missing(self, validator):
        """Тест валидации с отсутствующими полями."""
        args = ToolArguments.from_dict({"path": "test.py"})
        required = ["path", "content", "encoding"]
        
        is_valid, missing = validator.validate_required_fields(args, required)
        assert is_valid is False
        assert "content" in missing
        assert "encoding" in missing
    
    def test_validate_field_types_success(self, validator):
        """Тест успешной валидации типов полей."""
        args = ToolArguments.from_dict({
            "path": "test.py",
            "recursive": True,
            "max_depth": 5
        })
        field_types = {
            "path": str,
            "recursive": bool,
            "max_depth": int
        }
        
        is_valid, errors = validator.validate_field_types(args, field_types)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_field_types_wrong_type(self, validator):
        """Тест валидации с неправильным типом."""
        args = ToolArguments.from_dict({"path": 123})  # должна быть строка
        field_types = {"path": str}
        
        is_valid, errors = validator.validate_field_types(args, field_types)
        assert is_valid is False
        assert len(errors) > 0
        assert "expected str" in errors[0]
