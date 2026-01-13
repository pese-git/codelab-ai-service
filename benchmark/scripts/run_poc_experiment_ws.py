#!/usr/bin/env python3
"""
POC Experiment Runner - WebSocket client version.

Работает через Gateway WebSocket API как настоящий IDE клиент.
Это самый простой и надежный способ для полноценного тестирования.

Usage:
    python scripts/run_poc_experiment_ws.py --task-id task_001 --enable-validation
"""
import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import UUID
import yaml
import websockets

# IMPORTANT: Load .env BEFORE importing AppConfig
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / "agent-runtime" / ".env")

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
logger = logging.getLogger("poc_runner_ws")


class WebSocketPOCRunner:
    """
    WebSocket-based POC runner that acts as IDE client.
    
    Communicates with Gateway via WebSocket,
    executes tools locally, and validates results.
    """
    
    def __init__(
        self,
        tasks_file: Path,
        gateway_ws_url: str = "ws://localhost:8000/ws/benchmark",
        enable_validation: bool = False
    ):
        """
        Initialize WebSocket POC runner.
        
        Args:
            tasks_file: Path to YAML file with benchmark tasks
            gateway_ws_url: Gateway WebSocket URL
            enable_validation: Enable auto_check validation
        """
        self.tasks_file = tasks_file
        self.gateway_ws_url = gateway_ws_url
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
    
    async def execute_task_ws(
        self,
        task: Dict[str, Any],
        collector: MetricsCollector,
        task_execution_id: UUID
    ) -> bool:
        """
        Execute task via WebSocket with full tool execution loop.
        
        Args:
            task: Task definition
            collector: Metrics collector
            task_execution_id: Task execution ID
            
        Returns:
            True if task succeeded
        """
        task_description = task.get('description', '')
        
        # Track metrics
        llm_calls = 0
        tool_calls = 0
        agent_switches = 0
        has_error = False
        response_text = ""
        
        try:
            async with websockets.connect(self.gateway_ws_url) as websocket:
                logger.info(f"Connected to Gateway WebSocket")
                
                # Send initial message
                await websocket.send(json.dumps({
                    "type": "user_message",
                    "content": task_description,
                    "role": "user"
                }))
                
                logger.info(f"Sent task description")
                
                # Process responses
                while True:
                    try:
                        data = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        msg = json.loads(data)
                        msg_type = msg.get("type")
                        
                        logger.debug(f"Received: {msg_type}")
                        
                        if msg_type == "assistant_message":
                            token = msg.get("token", "")
                            response_text += token
                            llm_calls += 1
                            
                            if msg.get("is_final"):
                                logger.info("Received final message")
                                break
                        
                        elif msg_type == "tool_call":
                            tool_calls += 1
                            call_id = msg.get("call_id")
                            tool_name = msg.get("tool_name")
                            arguments = msg.get("arguments", {})
                            
                            logger.info(f"Tool call: {tool_name} (call_id={call_id})")
                            
                            # Execute tool
                            if self.tool_executor:
                                tool_result = await self.tool_executor.execute_tool(tool_name, arguments)
                                logger.info(f"Tool executed: {tool_name}, success={tool_result.get('success')}")
                                
                                # Send tool result back
                                await websocket.send(json.dumps({
                                    "type": "tool_result",
                                    "call_id": call_id,
                                    "result": tool_result
                                }))
                                
                                logger.info(f"Sent tool result for {tool_name}")
                            else:
                                # Send empty result if no executor
                                await websocket.send(json.dumps({
                                    "type": "tool_result",
                                    "call_id": call_id,
                                    "result": {"success": False, "error": "No tool executor"}
                                }))
                        
                        elif msg_type == "agent_switched":
                            agent_switches += 1
                            from_agent = msg.get("from_agent")
                            to_agent = msg.get("to_agent")
                            logger.info(f"Agent switched: {from_agent} -> {to_agent}")
                        
                        elif msg_type == "error":
                            has_error = True
                            error_msg = msg.get("content", msg.get("error", "Unknown error"))
                            logger.error(f"Error: {error_msg}")
                            break
                    
                    except asyncio.TimeoutError:
                        logger.warning("Timeout waiting for response")
                        break
                    except websockets.ConnectionClosed:
                        logger.info("WebSocket connection closed")
                        break
            
            # Validate if enabled
            success = not has_error and len(response_text) > 0
            
            if self.enable_validation and self.validator:
                validation = await self.validator.validate_task(task)
                logger.info(
                    f"Validation: {validation['passed_checks']}/{validation['total_checks']} passed "
                    f"({validation['success_rate']:.0%})"
                )
                if validation['total_checks'] > 0:
                    success = validation['success_rate'] >= 0.5
            
            return success
            
        except Exception as e:
            logger.error(f"Task execution error: {e}", exc_info=True)
            return False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run POC experiment via WebSocket (like IDE client)"
    )
    parser.add_argument(
        "--task-id",
        type=str,
        required=True,
        help="Task ID to run"
    )
    parser.add_argument(
        "--gateway-ws-url",
        type=str,
        default="ws://localhost:8000/ws/benchmark",
        help="Gateway WebSocket URL"
    )
    parser.add_argument(
        "--enable-validation",
        action="store_true",
        help="Enable validation"
    )
    
    args = parser.parse_args()
    
    # Load tasks
    tasks_file = Path(__file__).parent.parent / "poc_benchmark_tasks.yaml"
    runner = WebSocketPOCRunner(
        tasks_file=tasks_file,
        gateway_ws_url=args.gateway_ws_url,
        enable_validation=args.enable_validation
    )
    runner.load_tasks()
    
    # Find task
    task = next((t for t in runner.tasks if t['id'] == args.task_id), None)
    if not task:
        logger.error(f"Task not found: {args.task_id}")
        sys.exit(1)
    
    logger.info(f"Running task: {task['id']} - {task['title']}")
    
    # Initialize database for metrics
    init_database(AppConfig.DB_URL)
    await init_db()
    
    # Run task
    async for db in get_db():
        collector = MetricsCollector(db)
        
        # Start experiment
        experiment_id = await collector.start_experiment(
            mode="multi-agent",
            config={"task_id": args.task_id, "mode": "websocket"}
        )
        
        # Start task
        task_execution_id = await collector.start_task(
            experiment_id=experiment_id,
            task_id=task['id'],
            task_category=task['category'],
            task_type=task['type'],
            mode="multi-agent"
        )
        
        # Execute
        start_time = time.time()
        success = await runner.execute_task_ws(task, collector, task_execution_id)
        duration = time.time() - start_time
        
        # Complete
        await collector.complete_task(
            task_execution_id,
            success=success,
            metrics={"duration_seconds": duration}
        )
        await collector.complete_experiment(experiment_id)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Task {args.task_id}: {'✅ SUCCESS' if success else '❌ FAILED'}")
        logger.info(f"Duration: {duration:.2f}s")
        logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
