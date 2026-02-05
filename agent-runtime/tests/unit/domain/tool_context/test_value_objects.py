"""
Unit тесты для Value Objects Tool Context.

Покрытие:
- ToolName
- ToolCallId
- ToolArguments
- ToolResult
- ToolCategory
- ToolExecutionMode
- ToolPermission
"""

import pytest
import json

from app.domain.tool_context.value_objects import (
    ToolName,
    ToolCallId,
    ToolArguments,
    ToolResult,
    ToolCategory,
    ToolExecutionMode,
    ToolPermission
)


# ===== ToolName Tests =====

class TestToolName:
    """Тесты для ToolName."""
    
    def test_create_valid_tool_name(self):
        """Тест создания валидного имени инструмента."""
        tool_name = ToolName(value="read_file")
        assert str(tool_name) == "read_file"
    
    def test_from_string(self):
        """Тест создания из строки."""
        tool_name = ToolName.from_string("write_file")
        assert str(tool_name) == "write_file"
    
    def test_empty_name_raises_error(self):
        """Тест что пустое имя вызывает ошибку."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ToolName(value="")
    
    def test_too_long_name_raises_error(self):
        """Тест что слишком длинное имя вызывает ошибку."""
        long_name = "a" * 101
        with pytest.raises(ValueError, match="too long"):
            ToolName(value=long_name)
    
    def test_invalid_format_raises_error(self):
        """Тест что невалидный формат вызывает ошибку."""
        with pytest.raises(ValueError, match="Invalid tool name format"):
            ToolName(value="ReadFile")  # CamelCase не разрешен
    
    def test_invalid_format_with_spaces(self):
        """Тест что имя с пробелами вызывает ошибку."""
        with pytest.raises(ValueError, match="Invalid tool name format"):
            ToolName(value="read file")
    
    def test_is_local_tool_for_echo(self):
        """Тест что echo является локальным инструментом."""
        tool_name = ToolName.from_string("echo")
        assert tool_name.is_local_tool() is True
        assert tool_name.is_ide_tool() is False
    
    def test_is_local_tool_for_calculator(self):
        """Тест что calculator является локальным инструментом."""
        tool_name = ToolName.from_string("calculator")
        assert tool_name.is_local_tool() is True
    
    def test_is_local_tool_for_switch_mode(self):
        """Тест что switch_mode является локальным инструментом."""
        tool_name = ToolName.from_string("switch_mode")
        assert tool_name.is_local_tool() is True
    
    def test_is_ide_tool_for_read_file(self):
        """Тест что read_file является IDE инструментом."""
        tool_name = ToolName.from_string("read_file")
        assert tool_name.is_ide_tool() is True
        assert tool_name.is_local_tool() is False
    
    def test_equality(self):
        """Тест равенства."""
        name1 = ToolName.from_string("read_file")
        name2 = ToolName.from_string("read_file")
        assert name1 == name2
    
    def test_repr(self):
        """Тест отладочного представления."""
        tool_name = ToolName.from_string("read_file")
        assert repr(tool_name) == "ToolName('read_file')"


# ===== ToolCallId Tests =====

class TestToolCallId:
    """Тесты для ToolCallId."""
    
    def test_generate_creates_valid_id(self):
        """Тест генерации валидного ID."""
        call_id = ToolCallId.generate()
        assert str(call_id).startswith("call_")
    
    def test_generate_creates_unique_ids(self):
        """Тест что генерация создает уникальные ID."""
        id1 = ToolCallId.generate()
        id2 = ToolCallId.generate()
        assert id1 != id2
    
    def test_from_string_with_call_format(self):
        """Тест создания из строки с форматом call_xxx."""
        call_id = ToolCallId.from_string("call_abc123")
        assert str(call_id) == "call_abc123"
    
    def test_from_string_with_uuid_format(self):
        """Тест создания из строки с UUID форматом."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        call_id = ToolCallId.from_string(uuid_str)
        assert str(call_id) == uuid_str
    
    def test_empty_id_raises_error(self):
        """Тест что пустой ID вызывает ошибку."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ToolCallId(value="")
    
    def test_too_long_id_raises_error(self):
        """Тест что слишком длинный ID вызывает ошибку."""
        long_id = "call_" + "a" * 300
        with pytest.raises(ValueError, match="too long"):
            ToolCallId(value=long_id)
    
    def test_invalid_format_raises_error(self):
        """Тест что невалидный формат вызывает ошибку."""
        with pytest.raises(ValueError, match="Invalid tool call ID format"):
            ToolCallId(value="invalid-format")
    
    def test_hash_works(self):
        """Тест что хеширование работает."""
        id1 = ToolCallId.from_string("call_123")
        id2 = ToolCallId.from_string("call_123")
        assert hash(id1) == hash(id2)
    
    def test_can_use_in_set(self):
        """Тест что можно использовать в множестве."""
        id1 = ToolCallId.from_string("call_123")
        id2 = ToolCallId.from_string("call_456")
        id_set = {id1, id2}
        assert len(id_set) == 2


# ===== ToolArguments Tests =====

class TestToolArguments:
    """Тесты для ToolArguments."""
    
    def test_from_dict(self):
        """Тест создания из словаря."""
        args = ToolArguments.from_dict({"path": "test.py", "content": "hello"})
        assert args.get("path") == "test.py"
        assert args.get("content") == "hello"
    
    def test_from_json(self):
        """Тест создания из JSON строки."""
        json_str = '{"path": "test.py", "recursive": true}'
        args = ToolArguments.from_json(json_str)
        assert args.get("path") == "test.py"
        assert args.get("recursive") is True
    
    def test_from_json_invalid_raises_error(self):
        """Тест что невалидный JSON вызывает ошибку."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            ToolArguments.from_json("not a json")
    
    def test_from_json_non_object_raises_error(self):
        """Тест что JSON не-объект вызывает ошибку."""
        with pytest.raises(ValueError, match="must be an object"):
            ToolArguments.from_json('["array"]')
    
    def test_empty_creates_empty_arguments(self):
        """Тест создания пустых аргументов."""
        args = ToolArguments.empty()
        assert len(args.to_dict()) == 0
    
    def test_get_with_default(self):
        """Тест получения значения с default."""
        args = ToolArguments.from_dict({"path": "test.py"})
        assert args.get("missing", "default") == "default"
    
    def test_has_returns_true_for_existing(self):
        """Тест что has возвращает True для существующего ключа."""
        args = ToolArguments.from_dict({"path": "test.py"})
        assert args.has("path") is True
    
    def test_has_returns_false_for_missing(self):
        """Тест что has возвращает False для отсутствующего ключа."""
        args = ToolArguments.from_dict({"path": "test.py"})
        assert args.has("missing") is False
    
    def test_to_dict_returns_copy(self):
        """Тест что to_dict возвращает копию."""
        args = ToolArguments.from_dict({"path": "test.py"})
        data = args.to_dict()
        assert data == {"path": "test.py"}
    
    def test_to_json_returns_valid_json(self):
        """Тест что to_json возвращает валидный JSON."""
        args = ToolArguments.from_dict({"path": "test.py"})
        json_str = args.to_json()
        parsed = json.loads(json_str)
        assert parsed == {"path": "test.py"}
    
    def test_validate_against_schema_success(self):
        """Тест успешной валидации против схемы."""
        args = ToolArguments.from_dict({"path": "test.py"})
        schema = {
            "required": ["path"],
            "properties": {"path": {"type": "string"}}
        }
        is_valid, error = args.validate_against_schema(schema)
        assert is_valid is True
        assert error is None
    
    def test_validate_against_schema_missing_required(self):
        """Тест валидации с отсутствующим обязательным полем."""
        args = ToolArguments.from_dict({"content": "hello"})
        schema = {"required": ["path"]}
        is_valid, error = args.validate_against_schema(schema)
        assert is_valid is False
        assert "Missing required field" in error
    
    def test_validate_against_schema_wrong_type(self):
        """Тест валидации с неправильным типом."""
        args = ToolArguments.from_dict({"path": 123})
        schema = {
            "properties": {"path": {"type": "string"}}
        }
        is_valid, error = args.validate_against_schema(schema)
        assert is_valid is False
        assert "Invalid type" in error
    
    def test_too_large_arguments_raises_error(self):
        """Тест что слишком большие аргументы вызывают ошибку."""
        large_content = "x" * (100 * 1024 + 1)
        with pytest.raises(ValueError, match="too large"):
            ToolArguments.from_dict({"content": large_content})


# ===== ToolResult Tests =====

class TestToolResult:
    """Тесты для ToolResult."""
    
    def test_success_creates_successful_result(self):
        """Тест создания успешного результата."""
        result = ToolResult.success("Operation completed")
        assert result.is_success() is True
        assert result.get_content() == "Operation completed"
        assert result.is_error is False
    
    def test_error_creates_error_result(self):
        """Тест создания результата с ошибкой."""
        result = ToolResult.error("File not found")
        assert result.is_success() is False
        assert result.get_content() == "File not found"
        assert result.is_error is True
    
    def test_success_with_metadata(self):
        """Тест создания успешного результата с метаданными."""
        result = ToolResult.success("OK", metadata={"duration_ms": 150})
        assert result.get_metadata("duration_ms") == 150
    
    def test_error_with_metadata(self):
        """Тест создания ошибки с метаданными."""
        result = ToolResult.error("Failed", metadata={"code": 404})
        assert result.get_metadata("code") == 404
    
    def test_get_metadata_with_default(self):
        """Тест получения метаданных с default."""
        result = ToolResult.success("OK")
        assert result.get_metadata("missing", "default") == "default"
    
    def test_has_metadata_returns_true_for_existing(self):
        """Тест что has_metadata возвращает True для существующего ключа."""
        result = ToolResult.success("OK", metadata={"key": "value"})
        assert result.has_metadata("key") is True
    
    def test_has_metadata_returns_false_for_missing(self):
        """Тест что has_metadata возвращает False для отсутствующего ключа."""
        result = ToolResult.success("OK")
        assert result.has_metadata("missing") is False
    
    def test_truncate_short_content(self):
        """Тест усечения короткого контента."""
        result = ToolResult.success("Short")
        assert result.truncate(100) == "Short"
    
    def test_truncate_long_content(self):
        """Тест усечения длинного контента."""
        result = ToolResult.success("A" * 200)
        truncated = result.truncate(50)
        assert len(truncated) == 53  # 50 + "..."
        assert truncated.endswith("...")
    
    def test_too_large_content_raises_error(self):
        """Тест что слишком большой контент вызывает ошибку."""
        large_content = "x" * (1024 * 1024 + 1)
        with pytest.raises(ValueError, match="too large"):
            ToolResult.success(large_content)


# ===== ToolCategory Tests =====

class TestToolCategory:
    """Тесты для ToolCategory."""
    
    def test_file_system_factory(self):
        """Тест фабричного метода file_system."""
        category = ToolCategory.file_system()
        assert str(category) == "FILE_SYSTEM"
    
    def test_command_factory(self):
        """Тест фабричного метода command."""
        category = ToolCategory.command()
        assert str(category) == "COMMAND"
    
    def test_search_factory(self):
        """Тест фабричного метода search."""
        category = ToolCategory.search()
        assert str(category) == "SEARCH"
    
    def test_agent_factory(self):
        """Тест фабричного метода agent."""
        category = ToolCategory.agent()
        assert str(category) == "AGENT"
    
    def test_utility_factory(self):
        """Тест фабричного метода utility."""
        category = ToolCategory.utility()
        assert str(category) == "UTILITY"
    
    def test_from_string(self):
        """Тест создания из строки."""
        category = ToolCategory.from_string("file_system")
        assert str(category) == "FILE_SYSTEM"
    
    def test_invalid_category_raises_error(self):
        """Тест что невалидная категория вызывает ошибку."""
        with pytest.raises(ValueError, match="Invalid tool category"):
            ToolCategory(value="INVALID")
    
    def test_file_system_is_dangerous(self):
        """Тест что FILE_SYSTEM опасная категория."""
        category = ToolCategory.file_system()
        assert category.is_dangerous() is True
    
    def test_command_is_dangerous(self):
        """Тест что COMMAND опасная категория."""
        category = ToolCategory.command()
        assert category.is_dangerous() is True
    
    def test_utility_is_not_dangerous(self):
        """Тест что UTILITY не опасная категория."""
        category = ToolCategory.utility()
        assert category.is_dangerous() is False
    
    def test_file_system_requires_approval(self):
        """Тест что FILE_SYSTEM требует одобрения."""
        category = ToolCategory.file_system()
        assert category.requires_approval() is True
    
    def test_search_does_not_require_approval(self):
        """Тест что SEARCH не требует одобрения."""
        category = ToolCategory.search()
        assert category.requires_approval() is False
    
    def test_equality(self):
        """Тест равенства."""
        cat1 = ToolCategory.file_system()
        cat2 = ToolCategory.file_system()
        assert cat1 == cat2


# ===== ToolExecutionMode Tests =====

class TestToolExecutionMode:
    """Тесты для ToolExecutionMode."""
    
    def test_local_factory(self):
        """Тест фабричного метода local."""
        mode = ToolExecutionMode.local()
        assert str(mode) == "LOCAL"
        assert mode.is_local() is True
    
    def test_ide_factory(self):
        """Тест фабричного метода ide."""
        mode = ToolExecutionMode.ide()
        assert str(mode) == "IDE"
        assert mode.is_ide() is True
    
    def test_remote_factory(self):
        """Тест фабричного метода remote."""
        mode = ToolExecutionMode.remote()
        assert str(mode) == "REMOTE"
        assert mode.is_remote() is True
    
    def test_from_string(self):
        """Тест создания из строки."""
        mode = ToolExecutionMode.from_string("local")
        assert str(mode) == "LOCAL"
    
    def test_invalid_mode_raises_error(self):
        """Тест что невалидный режим вызывает ошибку."""
        with pytest.raises(ValueError, match="Invalid execution mode"):
            ToolExecutionMode(value="INVALID")
    
    def test_local_is_not_ide(self):
        """Тест что LOCAL не является IDE."""
        mode = ToolExecutionMode.local()
        assert mode.is_ide() is False
        assert mode.is_remote() is False
    
    def test_equality(self):
        """Тест равенства."""
        mode1 = ToolExecutionMode.local()
        mode2 = ToolExecutionMode.local()
        assert mode1 == mode2


# ===== ToolPermission Tests =====

class TestToolPermission:
    """Тесты для ToolPermission."""
    
    def test_read_only_factory(self):
        """Тест фабричного метода read_only."""
        perm = ToolPermission.read_only()
        assert str(perm) == "READ_ONLY"
    
    def test_read_write_factory(self):
        """Тест фабричного метода read_write."""
        perm = ToolPermission.read_write()
        assert str(perm) == "READ_WRITE"
    
    def test_execute_factory(self):
        """Тест фабричного метода execute."""
        perm = ToolPermission.execute()
        assert str(perm) == "EXECUTE"
    
    def test_admin_factory(self):
        """Тест фабричного метода admin."""
        perm = ToolPermission.admin()
        assert str(perm) == "ADMIN"
    
    def test_from_string(self):
        """Тест создания из строки."""
        perm = ToolPermission.from_string("read_write")
        assert str(perm) == "READ_WRITE"
    
    def test_invalid_permission_raises_error(self):
        """Тест что невалидный уровень вызывает ошибку."""
        with pytest.raises(ValueError, match="Invalid permission level"):
            ToolPermission(level="INVALID")
    
    def test_read_write_allows_read_only(self):
        """Тест что READ_WRITE разрешает READ_ONLY."""
        read_write = ToolPermission.read_write()
        read_only = ToolPermission.read_only()
        assert read_write.allows(read_only) is True
    
    def test_read_only_does_not_allow_read_write(self):
        """Тест что READ_ONLY не разрешает READ_WRITE."""
        read_only = ToolPermission.read_only()
        read_write = ToolPermission.read_write()
        assert read_only.allows(read_write) is False
    
    def test_execute_allows_read_write(self):
        """Тест что EXECUTE разрешает READ_WRITE."""
        execute = ToolPermission.execute()
        read_write = ToolPermission.read_write()
        assert execute.allows(read_write) is True
    
    def test_admin_allows_all(self):
        """Тест что ADMIN разрешает все уровни."""
        admin = ToolPermission.admin()
        assert admin.allows(ToolPermission.read_only()) is True
        assert admin.allows(ToolPermission.read_write()) is True
        assert admin.allows(ToolPermission.execute()) is True
    
    def test_get_level_number(self):
        """Тест получения числового уровня."""
        assert ToolPermission.read_only().get_level_number() == 1
        assert ToolPermission.read_write().get_level_number() == 2
        assert ToolPermission.execute().get_level_number() == 3
        assert ToolPermission.admin().get_level_number() == 4
    
    def test_comparison_operators(self):
        """Тест операторов сравнения."""
        read_only = ToolPermission.read_only()
        read_write = ToolPermission.read_write()
        execute = ToolPermission.execute()
        
        assert read_only < read_write
        assert read_only <= read_write
        assert execute > read_write
        assert execute >= read_write
    
    def test_equality(self):
        """Тест равенства."""
        perm1 = ToolPermission.read_only()
        perm2 = ToolPermission.read_only()
        assert perm1 == perm2
