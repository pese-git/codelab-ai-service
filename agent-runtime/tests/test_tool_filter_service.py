"""
Unit тесты для ToolFilterService.

Тестирует фильтрацию инструментов по разрешенным.
"""

import pytest
from unittest.mock import Mock

from app.domain.services.tool_filter_service import ToolFilterService
from app.domain.services.tool_registry import ToolRegistry


class TestToolFilterService:
    """Тесты для ToolFilterService"""
    
    @pytest.fixture
    def mock_tool_registry(self):
        """Mock tool registry с тестовыми инструментами"""
        registry = Mock(spec=ToolRegistry)
        registry.get_all_tools.return_value = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read file content"
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write file content"
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Execute shell command"
                }
            }
        ]
        return registry
    
    @pytest.fixture
    def filter_service(self, mock_tool_registry):
        """Создать filter service с mock зависимостями"""
        return ToolFilterService(tool_registry=mock_tool_registry)
    
    def test_filter_tools_all_when_none(self, filter_service, mock_tool_registry):
        """Тест: None = все инструменты"""
        # Act
        tools = filter_service.filter_tools(allowed_tools=None)
        
        # Assert
        assert len(tools) == 3
        mock_tool_registry.get_all_tools.assert_called_once()
    
    def test_filter_tools_by_allowed_list(self, filter_service):
        """Тест фильтрации по разрешенным инструментам"""
        # Act
        tools = filter_service.filter_tools(allowed_tools=["read_file", "write_file"])
        
        # Assert
        assert len(tools) == 2
        tool_names = [t["function"]["name"] for t in tools]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "execute_command" not in tool_names
    
    def test_filter_tools_empty_list(self, filter_service):
        """Тест фильтрации с пустым списком разрешенных"""
        # Act
        tools = filter_service.filter_tools(allowed_tools=[])
        
        # Assert
        assert len(tools) == 0
    
    def test_filter_tools_unknown_tool(self, filter_service, caplog):
        """Тест предупреждения о неизвестных инструментах"""
        # Act
        tools = filter_service.filter_tools(
            allowed_tools=["read_file", "unknown_tool"]
        )
        
        # Assert
        assert len(tools) == 1  # Только read_file
        assert "unknown_tool" in caplog.text
    
    def test_get_tool_names(self, filter_service):
        """Тест получения списка имен инструментов"""
        # Act
        names = filter_service.get_tool_names(allowed_tools=["read_file", "write_file"])
        
        # Assert
        assert names == ["read_file", "write_file"]
    
    def test_is_tool_allowed_when_none(self, filter_service):
        """Тест: None = все разрешены"""
        # Act & Assert
        assert filter_service.is_tool_allowed("read_file", allowed_tools=None) == True
        assert filter_service.is_tool_allowed("write_file", allowed_tools=None) == True
        assert filter_service.is_tool_allowed("unknown", allowed_tools=None) == True
    
    def test_is_tool_allowed_in_list(self, filter_service):
        """Тест проверки разрешения инструмента"""
        # Arrange
        allowed = ["read_file", "write_file"]
        
        # Act & Assert
        assert filter_service.is_tool_allowed("read_file", allowed) == True
        assert filter_service.is_tool_allowed("write_file", allowed) == True
        assert filter_service.is_tool_allowed("execute_command", allowed) == False
    
    def test_validate_tool_access_valid(self, filter_service):
        """Тест валидации доступа к существующему разрешенному инструменту"""
        # Act
        is_valid, error = filter_service.validate_tool_access(
            tool_name="read_file",
            allowed_tools=["read_file", "write_file"]
        )
        
        # Assert
        assert is_valid == True
        assert error is None
    
    def test_validate_tool_access_not_in_registry(self, filter_service):
        """Тест валидации несуществующего инструмента"""
        # Act
        is_valid, error = filter_service.validate_tool_access(
            tool_name="unknown_tool",
            allowed_tools=["read_file"]
        )
        
        # Assert
        assert is_valid == False
        assert "does not exist" in error
    
    def test_validate_tool_access_not_allowed(self, filter_service):
        """Тест валидации неразрешенного инструмента"""
        # Act
        is_valid, error = filter_service.validate_tool_access(
            tool_name="execute_command",
            allowed_tools=["read_file", "write_file"]
        )
        
        # Assert
        assert is_valid == False
        assert "not allowed" in error
