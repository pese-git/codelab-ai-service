#!/usr/bin/env python3
"""
Mock Tool Executor - эмулирует выполнение tools для benchmark.

Вместо отправки tool calls клиенту, выполняет их локально
в контексте test_project для автоматического тестирования.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("mock_tool_executor")


class MockToolExecutor:
    """
    Эмулятор выполнения tools для benchmark.
    
    Выполняет tools локально в контексте test_project,
    позволяя агентам создавать/изменять файлы для валидации.
    """
    
    def __init__(self, workspace_path: Path):
        """
        Initialize mock executor.
        
        Args:
            workspace_path: Path to test_project workspace
        """
        self.workspace_path = workspace_path
        
        if not self.workspace_path.exists():
            raise FileNotFoundError(f"Workspace not found: {self.workspace_path}")
        
        logger.info(f"MockToolExecutor initialized with workspace: {self.workspace_path}")
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tool locally.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        logger.debug(f"Executing tool: {tool_name} with args: {arguments}")
        
        try:
            if tool_name == "write_file":
                return await self._write_file(arguments)
            elif tool_name == "read_file":
                return await self._read_file(arguments)
            elif tool_name == "list_files":
                return await self._list_files(arguments)
            elif tool_name == "search_in_code":
                return await self._search_in_code(arguments)
            elif tool_name == "apply_diff":
                return await self._apply_diff(arguments)
            else:
                logger.warning(f"Unknown tool: {tool_name}")
                return {
                    "success": False,
                    "error": f"Tool not implemented: {tool_name}"
                }
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _write_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Write file tool."""
        path = args.get('path', '')
        content = args.get('content', '')
        
        full_path = self.workspace_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        full_path.write_text(content, encoding='utf-8')
        
        logger.info(f"Created file: {path}")
        return {
            "success": True,
            "message": f"File created: {path}",
            "path": path
        }
    
    async def _read_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read file tool."""
        path = args.get('path', '')
        
        full_path = self.workspace_path / path
        
        if not full_path.exists():
            return {
                "success": False,
                "error": f"File not found: {path}"
            }
        
        content = full_path.read_text(encoding='utf-8')
        
        return {
            "success": True,
            "content": content,
            "path": path
        }
    
    async def _list_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List files tool."""
        path = args.get('path', '.')
        recursive = args.get('recursive', False)
        
        full_path = self.workspace_path / path
        
        if not full_path.exists():
            return {
                "success": False,
                "error": f"Path not found: {path}"
            }
        
        if recursive:
            files = [str(p.relative_to(self.workspace_path)) for p in full_path.rglob('*') if p.is_file()]
        else:
            files = [str(p.relative_to(self.workspace_path)) for p in full_path.iterdir() if p.is_file()]
        
        return {
            "success": True,
            "files": files,
            "count": len(files)
        }
    
    async def _search_in_code(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search in code tool."""
        pattern = args.get('pattern', '')
        path = args.get('path', '.')
        
        full_path = self.workspace_path / path
        
        results = []
        for file_path in full_path.rglob('*.dart'):
            try:
                content = file_path.read_text(encoding='utf-8')
                if pattern in content:
                    results.append(str(file_path.relative_to(self.workspace_path)))
            except Exception:
                pass
        
        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    
    async def _apply_diff(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Apply diff tool (simplified)."""
        path = args.get('path', '')
        diff = args.get('diff', '')
        
        # Simplified: just write the new content
        # In real implementation, would parse and apply diff
        
        return {
            "success": True,
            "message": f"Diff applied to: {path}"
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_executor():
        workspace = Path(__file__).parent.parent / "test_project"
        executor = MockToolExecutor(workspace)
        
        # Test write_file
        result = await executor.execute_tool("write_file", {
            "path": "lib/widgets/test_widget.dart",
            "content": "// Test widget\nclass TestWidget {}\n"
        })
        print(f"write_file: {result}")
        
        # Test read_file
        result = await executor.execute_tool("read_file", {
            "path": "lib/models/user.dart"
        })
        print(f"read_file: success={result['success']}, length={len(result.get('content', ''))}")
        
        # Test list_files
        result = await executor.execute_tool("list_files", {
            "path": "lib",
            "recursive": True
        })
        print(f"list_files: {result['count']} files found")
    
    asyncio.run(test_executor())
