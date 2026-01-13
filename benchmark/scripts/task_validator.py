#!/usr/bin/env python3
"""
Task Validator - автоматическая проверка выполнения benchmark задач.

Реализует auto_check валидаторы из poc_benchmark_tasks.yaml:
- file_exists: проверка существования файла
- syntax_valid: проверка синтаксиса Dart кода
- contains_text: проверка наличия текста в файле
- test_passes: запуск тестов
"""
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("task_validator")


class TaskValidator:
    """
    Валидатор для автоматической проверки выполнения задач.
    
    Использует auto_check спецификацию из YAML для проверки результатов.
    """
    
    def __init__(self, project_path: Path):
        """
        Initialize validator.
        
        Args:
            project_path: Path to Flutter test project
        """
        self.project_path = project_path
        
        if not self.project_path.exists():
            raise FileNotFoundError(f"Project path not found: {self.project_path}")
        
        logger.info(f"TaskValidator initialized with project: {self.project_path}")
    
    async def validate_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate task execution using auto_check rules.
        
        Args:
            task: Task definition from YAML
            
        Returns:
            Validation result with passed checks and details
        """
        task_id = task.get('id', 'unknown')
        auto_checks = task.get('auto_check', [])
        
        if not auto_checks:
            logger.warning(f"No auto_check rules for task {task_id}")
            return {
                "task_id": task_id,
                "total_checks": 0,
                "passed_checks": 0,
                "failed_checks": 0,
                "success_rate": 0.0,
                "details": []
            }
        
        logger.info(f"Validating task {task_id} with {len(auto_checks)} checks")
        
        results = []
        passed = 0
        failed = 0
        
        for check in auto_checks:
            check_type = check.get('type')
            params = check.get('params', {})
            
            try:
                result = await self._run_check(check_type, params)
                results.append({
                    "type": check_type,
                    "params": params,
                    "passed": result['passed'],
                    "message": result.get('message', '')
                })
                
                if result['passed']:
                    passed += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Check {check_type} failed with error: {e}")
                results.append({
                    "type": check_type,
                    "params": params,
                    "passed": False,
                    "message": f"Error: {str(e)}"
                })
                failed += 1
        
        success_rate = passed / len(auto_checks) if auto_checks else 0.0
        
        return {
            "task_id": task_id,
            "total_checks": len(auto_checks),
            "passed_checks": passed,
            "failed_checks": failed,
            "success_rate": success_rate,
            "details": results
        }
    
    async def _run_check(self, check_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run specific check type.
        
        Args:
            check_type: Type of check (file_exists, syntax_valid, etc.)
            params: Check parameters
            
        Returns:
            Check result with passed status and message
        """
        if check_type == "file_exists":
            return await self._check_file_exists(params)
        elif check_type == "syntax_valid":
            return await self._check_syntax_valid(params)
        elif check_type == "contains_text":
            return await self._check_contains_text(params)
        elif check_type == "test_passes":
            return await self._check_test_passes(params)
        else:
            logger.warning(f"Unknown check type: {check_type}")
            return {
                "passed": False,
                "message": f"Unknown check type: {check_type}"
            }
    
    async def _check_file_exists(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if file exists.
        
        Args:
            params: {"path": "relative/path/to/file.dart"}
            
        Returns:
            Check result
        """
        file_path = params.get('path', '')
        full_path = self.project_path / file_path
        
        exists = full_path.exists()
        
        return {
            "passed": exists,
            "message": f"File {'exists' if exists else 'not found'}: {file_path}"
        }
    
    async def _check_syntax_valid(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if Dart file has valid syntax using dart analyze.
        
        Args:
            params: {"path": "relative/path/to/file.dart"}
            
        Returns:
            Check result
        """
        file_path = params.get('path', '')
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return {
                "passed": False,
                "message": f"File not found: {file_path}"
            }
        
        try:
            # Run dart analyze on specific file
            result = subprocess.run(
                ['dart', 'analyze', str(full_path)],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Check if no errors (warnings are ok)
            has_errors = 'error' in result.stdout.lower() or result.returncode != 0
            
            return {
                "passed": not has_errors,
                "message": f"Syntax {'valid' if not has_errors else 'invalid'}: {file_path}",
                "details": result.stdout if has_errors else None
            }
            
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "message": f"Syntax check timed out: {file_path}"
            }
        except Exception as e:
            return {
                "passed": False,
                "message": f"Syntax check error: {str(e)}"
            }
    
    async def _check_contains_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if file contains specific text.
        
        Args:
            params: {"path": "relative/path/to/file.dart", "text": "search text"}
            
        Returns:
            Check result
        """
        file_path = params.get('path', '')
        search_text = params.get('text', '')
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return {
                "passed": False,
                "message": f"File not found: {file_path}"
            }
        
        try:
            content = full_path.read_text(encoding='utf-8')
            contains = search_text in content
            
            return {
                "passed": contains,
                "message": f"Text {'found' if contains else 'not found'} in {file_path}: '{search_text}'"
            }
        except Exception as e:
            return {
                "passed": False,
                "message": f"Error reading file: {str(e)}"
            }
    
    async def _check_test_passes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if tests pass using flutter test.
        
        Args:
            params: {"pattern": "test_file_pattern.dart"}
            
        Returns:
            Check result
        """
        pattern = params.get('pattern', '*')
        
        try:
            # Run flutter test
            result = subprocess.run(
                ['flutter', 'test', '--no-pub', pattern],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Check if all tests passed
            tests_passed = result.returncode == 0 and 'All tests passed' in result.stdout
            
            return {
                "passed": tests_passed,
                "message": f"Tests {'passed' if tests_passed else 'failed'}: {pattern}",
                "details": result.stdout if not tests_passed else None
            }
            
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "message": f"Tests timed out: {pattern}"
            }
        except Exception as e:
            return {
                "passed": False,
                "message": f"Test execution error: {str(e)}"
            }
    
    def get_project_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the test project.
        
        Returns:
            Project statistics
        """
        lib_path = self.project_path / "lib"
        test_path = self.project_path / "test"
        docs_path = self.project_path / "docs"
        
        stats = {
            "project_path": str(self.project_path),
            "lib_files": len(list(lib_path.rglob("*.dart"))) if lib_path.exists() else 0,
            "test_files": len(list(test_path.rglob("*.dart"))) if test_path.exists() else 0,
            "doc_files": len(list(docs_path.rglob("*.md"))) if docs_path.exists() else 0,
            "total_files": len(list(self.project_path.rglob("*"))) if self.project_path.exists() else 0
        }
        
        return stats


# Example usage
if __name__ == "__main__":
    import yaml
    
    async def test_validator():
        # Load tasks
        tasks_file = Path(__file__).parent.parent / "poc_benchmark_tasks.yaml"
        with open(tasks_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        tasks = data['tasks']
        
        # Initialize validator
        project_path = Path(__file__).parent.parent / "test_project"
        validator = TaskValidator(project_path)
        
        # Get project stats
        stats = validator.get_project_stats()
        print(f"\nProject stats: {stats}")
        
        # Validate first task
        task = tasks[0]
        print(f"\nValidating task: {task['id']}")
        result = await validator.validate_task(task)
        print(f"Result: {result}")
    
    asyncio.run(test_validator())
