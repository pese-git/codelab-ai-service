#!/usr/bin/env python3
"""
POC Experiment Runner - HTTP client version.

Работает как настоящий IDE клиент, общаясь с agent-runtime через REST API.
Это правильный подход для полноценного тестирования с tool execution.

Usage:
    python scripts/run_poc_experiment_http.py --mode multi-agent --task-id task_001
"""
import argparse
import asyncio
import httpx
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from uuid import UUID
import yaml

# Add agent-runtime directory to path for imports (only for metrics)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent-runtime"))

from app.core.config import AppConfig
from app.services.database import init_database, get_db, init_db
from app.services.metrics_collector import MetricsCollector

# Import validators and executors
from task_validator import TaskValidator
from mock_tool_executor import MockToolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("poc_runner_http")


class HTTPPOCRunner:
    """
    HTTP-based POC runner that acts as IDE client.
    
    Communicates with agent-runtime via REST API,
    executes tools locally, and validates results.
    """
    
    def __init__(
        self,
        tasks_file: Path,
        mode: str,
        agent_runtime_url: str = "http://localhost:8003",
        enable_validation: bool = False
    ):
        """
        Initialize HTTP POC runner.
        
        Args:
            tasks_file: Path to YAML file with benchmark tasks
            mode: Execution mode ('single-agent' or 'multi-agent')
            agent_runtime_url: Agent runtime service URL
            enable_validation: Enable auto_check validation
        """
        self.tasks_file = tasks_file
        self.mode = mode
        self.agent_runtime_url = agent_runtime_url
        self.tasks: List[Dict[str, Any]] = []
        self.enable_validation = enable_validation
        self.validator: Optional[TaskValidator] = None
        self.tool_executor: Optional[MockToolExecutor] = None
        
        # Initialize validator and tool executor if enabled
        if self.enable_validation:
            project_path = Path(__file__).parent.parent / "test_project"
            if project_path.exists():
                self.validator = TaskValidator(project_path)
                self.tool_executor = MockToolExecutor(project_path)
                logger.info(f"Validation enabled with project: {project_path}")
            else:
                logger.warning(f"Test project not found: {project_path}")
                self.enable_validation = False
    
    def load_tasks(self) -> None:
        """Load tasks from YAML file."""
        logger.info(f"Loading tasks from {self.tasks_file}")
        
        with open(self.tasks_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self.tasks = data.get('tasks', [])
        logger.info(f"Loaded {len(self.tasks)} tasks")
    
    async def create_session(self) -> str:
        """
        Create new session via REST API.
        
        Returns:
            Session ID
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.agent_runtime_url}/api/v1/sessions",
                headers={"X-Internal-API-Key": AppConfig.INTERNAL_API_KEY}
            )
            response.raise_for_status()
            data = response.json()
            session_id = data['session_id']
            logger.info(f"Created session: {session_id}")
            return session_id
    
    async def send_message(
        self,
        session_id: str,
        message: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send message to agent via SSE stream.
        
        Args:
            session_id: Session ID
            message: User message
            
        Yields:
            Stream chunks
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.agent_runtime_url}/api/v1/agent/message/stream",
                json={
                    "session_id": session_id,
                    "message": {
                        "type": "user_message",
                        "content": message
                    }
                },
                headers={"X-Internal-API-Key": AppConfig.INTERNAL_API_KEY}
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        try:
                            chunk = json.loads(data_str)
                            yield chunk
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse SSE data: {data_str}")
    
    async def send_tool_result(
        self,
        session_id: str,
        call_id: str,
        tool_name: str,
        result: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send tool result back to agent.
        
        Args:
            session_id: Session ID
            call_id: Tool call ID
            tool_name: Tool name
            result: Tool execution result
            
        Yields:
            Stream chunks
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.agent_runtime_url}/api/v1/agent/message/stream",
                json={
                    "session_id": session_id,
                    "message": {
                        "type": "tool_result",
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "result": result
                    }
                },
                headers={"X-Internal-API-Key": AppConfig.INTERNAL_API_KEY}
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            chunk = json.loads(data_str)
                            yield chunk
                        except json.JSONDecodeError:
                            pass
    
    async def execute_task_http(
        self,
        task: Dict[str, Any],
        collector: MetricsCollector,
        task_execution_id: UUID
    ) -> bool:
        """
        Execute task via HTTP API with full tool execution loop.
        
        Args:
            task: Task definition
            collector: Metrics collector
            task_execution_id: Task execution ID
            
        Returns:
            True if task succeeded
        """
        task_description = task.get('description', '')
        
        # Create session
        session_id = await self.create_session()
        
        # Track metrics
        llm_calls = 0
        tool_calls = 0
        agent_switches = 0
        has_error = False
        response_text = ""
        
        try:
            # Send initial message
            logger.info(f"Sending task description to agent")
            
            async for chunk in self.send_message(session_id, task_description):
                chunk_type = chunk.get('type')
                
                if chunk_type == 'assistant_message':
                    response_text += chunk.get('text', '')
                    llm_calls += 1
                
                elif chunk_type == 'tool_call':
                    tool_calls += 1
                    tool_name = chunk.get('tool_name')
                    call_id = chunk.get('call_id')
                    arguments = chunk.get('arguments', {})
                    
                    logger.info(f"Tool call: {tool_name}")
                    
                    # Execute tool
                    if self.tool_executor:
                        tool_result = await self.tool_executor.execute_tool(tool_name, arguments)
                        logger.info(f"Tool executed: {tool_name}, success={tool_result.get('success')}")
                        
                        # Send result back
                        async for result_chunk in self.send_tool_result(
                            session_id, call_id, tool_name, tool_result
                        ):
                            # Process continuation chunks
                            if result_chunk.get('type') == 'assistant_message':
                                response_text += result_chunk.get('text', '')
                            elif result_chunk.get('type') == 'tool_call':
                                # Another tool call - would need recursive handling
                                logger.warning("Nested tool calls not fully supported yet")
                
                elif chunk_type == 'agent_switched':
                    agent_switches += 1
                    logger.info(f"Agent switched: {chunk.get('from_agent')} -> {chunk.get('to_agent')}")
                
                elif chunk_type == 'error':
                    has_error = True
                    logger.error(f"Error: {chunk.get('error')}")
            
            # Validate if enabled
            success = not has_error and len(response_text) > 0
            
            if self.enable_validation and self.validator:
                validation = await self.validator.validate_task(task)
                logger.info(f"Validation: {validation['passed_checks']}/{validation['total_checks']} passed")
                if validation['total_checks'] > 0:
                    success = validation['success_rate'] >= 0.5
            
            return success
            
        except Exception as e:
            logger.error(f"Task execution error: {e}", exc_info=True)
            return False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run POC experiment via HTTP API (like IDE client)"
    )
    parser.add_argument(
        "--mode",
        choices=["single-agent", "multi-agent"],
        default="multi-agent",
        help="Execution mode"
    )
    parser.add_argument(
        "--task-id",
        type=str,
        required=True,
        help="Task ID to run"
    )
    parser.add_argument(
        "--agent-runtime-url",
        type=str,
        default="http://localhost:8003",
        help="Agent runtime URL"
    )
    parser.add_argument(
        "--enable-validation",
        action="store_true",
        help="Enable validation"
    )
    
    args = parser.parse_args()
    
    # Load tasks
    tasks_file = Path(__file__).parent.parent / "poc_benchmark_tasks.yaml"
    runner = HTTPPOCRunner(
        tasks_file=tasks_file,
        mode=args.mode,
        agent_runtime_url=args.agent_runtime_url,
        enable_validation=args.enable_validation
    )
    runner.load_tasks()
    
    # Find task
    task = next((t for t in runner.tasks if t['id'] == args.task_id), None)
    if not task:
        logger.error(f"Task not found: {args.task_id}")
        sys.exit(1)
    
    # Initialize database for metrics
    init_database(AppConfig.DB_URL)
    await init_db()
    
    # Run task
    async for db in get_db():
        collector = MetricsCollector(db)
        
        # Start experiment
        experiment_id = await collector.start_experiment(
            mode=args.mode,
            config={"task_id": args.task_id}
        )
        
        # Start task
        task_execution_id = await collector.start_task(
            experiment_id=experiment_id,
            task_id=task['id'],
            task_category=task['category'],
            task_type=task['type'],
            mode=args.mode
        )
        
        # Execute
        success = await runner.execute_task_http(task, collector, task_execution_id)
        
        # Complete
        await collector.complete_task(task_execution_id, success=success)
        await collector.complete_experiment(experiment_id)
        
        logger.info(f"Task {args.task_id}: {'SUCCESS' if success else 'FAILED'}")


if __name__ == "__main__":
    asyncio.run(main())
