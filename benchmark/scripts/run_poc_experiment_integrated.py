#!/usr/bin/env python3
"""
POC Experiment Runner - интегрированный с реальным agent runtime.

Этот скрипт запускает все задачи из benchmark файла через реальный
multi-agent orchestrator и собирает метрики.

Usage:
    python scripts/run_poc_experiment_integrated.py --mode single-agent
    python scripts/run_poc_experiment_integrated.py --mode multi-agent
    python scripts/run_poc_experiment_integrated.py --mode both
"""
import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import UUID
import json

import yaml

# Add agent-runtime directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent-runtime"))

from app.core.config import AppConfig
from app.services.database import init_database, get_db, init_db
from app.services.metrics_collector import MetricsCollector
from app.services.multi_agent_orchestrator import multi_agent_orchestrator
from app.services.session_manager_async import session_manager
from app.services.agent_context_async import agent_context_manager
from app.agents.base_agent import AgentType
from app.models.schemas import StreamChunk

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("poc_runner_integrated")


class IntegratedPOCRunner:
    """
    Интегрированный runner для POC экспериментов.
    
    Использует реальный multi-agent orchestrator для выполнения задач
    и собирает реальные метрики.
    """
    
    def __init__(self, tasks_file: Path, mode: str):
        """
        Initialize POC runner.
        
        Args:
            tasks_file: Path to YAML file with benchmark tasks
            mode: Execution mode ('single-agent', 'multi-agent', or 'both')
        """
        self.tasks_file = tasks_file
        self.mode = mode
        self.tasks: List[Dict[str, Any]] = []
        
    def load_tasks(self) -> None:
        """Load tasks from YAML file."""
        logger.info(f"Loading tasks from {self.tasks_file}")
        
        if not self.tasks_file.exists():
            raise FileNotFoundError(f"Tasks file not found: {self.tasks_file}")
        
        with open(self.tasks_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data or 'tasks' not in data:
            raise ValueError("Invalid tasks file format. Expected 'tasks' key.")
        
        self.tasks = data['tasks']
        logger.info(f"Loaded {len(self.tasks)} tasks")
    
    async def run_experiment(self, mode: str) -> Dict[str, Any]:
        """
        Run experiment in specified mode.
        
        Args:
            mode: Execution mode ('single-agent' or 'multi-agent')
            
        Returns:
            Experiment summary statistics
        """
        logger.info(f"Starting experiment in {mode} mode")
        
        # Get database session using async context manager
        async for db in get_db():
            collector = MetricsCollector(db)
            
            # Start experiment
            config = {
                "llm_model": AppConfig.LLM_MODEL,
                "mode": mode,
                "tasks_file": str(self.tasks_file),
                "total_tasks": len(self.tasks),
                "started_at": datetime.now().isoformat()
            }
            
            experiment_id = await collector.start_experiment(mode=mode, config=config)
            logger.info(f"Started experiment: {experiment_id}")
            
            # Run each task
            successful_tasks = 0
            failed_tasks = 0
            
            for i, task in enumerate(self.tasks, 1):
                logger.info(f"Running task {i}/{len(self.tasks)}: {task['id']}")
                
                try:
                    success = await self.run_task_integrated(
                        collector, experiment_id, task, mode
                    )
                    if success:
                        successful_tasks += 1
                    else:
                        failed_tasks += 1
                except Exception as e:
                    logger.error(f"Error running task {task['id']}: {e}", exc_info=True)
                    failed_tasks += 1
            
            # Complete experiment
            await collector.complete_experiment(experiment_id)
            logger.info(f"Completed experiment: {experiment_id}")
            
            # Get summary
            summary = await collector.get_experiment_summary(experiment_id)
            summary['successful_tasks'] = successful_tasks
            summary['failed_tasks'] = failed_tasks
            
            return summary
    
    async def run_task_integrated(
        self,
        collector: MetricsCollector,
        experiment_id: UUID,
        task: Dict[str, Any],
        mode: str
    ) -> bool:
        """
        Run a single task through real agent runtime and collect metrics.
        
        Args:
            collector: MetricsCollector instance
            experiment_id: Parent experiment UUID
            task: Task definition from YAML
            mode: Execution mode
            
        Returns:
            True if task succeeded, False otherwise
        """
        task_id = task['id']
        task_category = task['category']
        task_type = task['type']
        
        # Start task execution
        task_execution_id = await collector.start_task(
            experiment_id=experiment_id,
            task_id=task_id,
            task_category=task_category,
            task_type=task_type,
            mode=mode
        )
        
        logger.info(f"Started task execution: {task_execution_id}")
        
        start_time = time.time()
        success = False
        failure_reason = None
        
        # Create unique session for this task
        session_id = f"benchmark_{task_id}_{int(time.time())}"
        
        try:
            # Execute task through real agent runtime
            success = await self.execute_task_real(
                collector, task_execution_id, task, mode, session_id
            )
            
            if not success:
                failure_reason = "Task execution failed"
        
        except Exception as e:
            logger.error(f"Task execution error: {e}", exc_info=True)
            success = False
            failure_reason = str(e)
        
        finally:
            # Complete task
            duration = time.time() - start_time
            metrics = {
                "duration_seconds": duration,
                "task_title": task.get('title', ''),
                "complexity_score": task.get('complexity_score', 0)
            }
            
            await collector.complete_task(
                task_execution_id=task_execution_id,
                success=success,
                failure_reason=failure_reason,
                metrics=metrics
            )
            
            logger.info(
                f"Completed task {task_id}: success={success}, "
                f"duration={duration:.2f}s"
            )
            
            # Cleanup session
            try:
                from app.services.session_manager_async import session_manager as async_session_mgr
                if async_session_mgr and async_session_mgr.exists(session_id):
                    await async_session_mgr.delete(session_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup session {session_id}: {e}")
        
        return success
    
    async def execute_task_real(
        self,
        collector: MetricsCollector,
        task_execution_id: UUID,
        task: Dict[str, Any],
        mode: str,
        session_id: str
    ) -> bool:
        """
        Execute task through real multi-agent orchestrator.
        
        Args:
            collector: MetricsCollector instance
            task_execution_id: Task execution UUID
            task: Task definition
            mode: Execution mode
            session_id: Session ID for this task
            
        Returns:
            True if task succeeded
        """
        # Get task description
        task_description = task.get('description', '')
        
        # Get initialized managers
        from app.services.session_manager_async import session_manager as async_session_mgr
        from app.services.agent_context_async import agent_context_manager as async_ctx_mgr
        
        if not async_session_mgr or not async_ctx_mgr:
            raise RuntimeError("Session or agent context manager not initialized")
        
        # Create session
        await async_session_mgr.get_or_create(session_id, system_prompt="")
        
        # Initialize agent context
        initial_agent = AgentType.ORCHESTRATOR if mode == "multi-agent" else AgentType.CODER
        await async_ctx_mgr.get_or_create(session_id, initial_agent=initial_agent)
        
        logger.info(f"Executing task {task['id']} with {mode} mode")
        logger.debug(f"Task description: {task_description}")
        
        # Track metrics
        llm_call_count = 0
        tool_call_count = 0
        agent_switches = []
        current_agent = initial_agent.value
        has_error = False
        response_text = ""
        
        try:
            # Process message through orchestrator
            async for chunk in multi_agent_orchestrator.process_message(
                session_id=session_id,
                message=task_description
            ):
                logger.debug(f"Received chunk: type={chunk.type}, is_final={chunk.is_final}")
                
                # Track different chunk types
                if chunk.type == "assistant_message":
                    response_text += chunk.content or ""
                    
                    # Record LLM call (approximate - one per message chunk)
                    if chunk.metadata:
                        llm_call_count += 1
                        await collector.record_llm_call(
                            task_execution_id=task_execution_id,
                            agent_type=current_agent,
                            input_tokens=chunk.metadata.get('input_tokens', 0),
                            output_tokens=chunk.metadata.get('output_tokens', 0),
                            model=chunk.metadata.get('model', AppConfig.LLM_MODEL),
                            duration_seconds=chunk.metadata.get('duration', 0)
                        )
                
                elif chunk.type == "tool_call":
                    tool_call_count += 1
                    tool_name = chunk.metadata.get('tool_name', 'unknown')
                    
                    logger.debug(f"Tool call: {tool_name}")
                    
                    # Record tool call
                    await collector.record_tool_call(
                        task_execution_id=task_execution_id,
                        tool_name=tool_name,
                        success=True,  # Will be updated if error occurs
                        duration_seconds=0.1  # Placeholder
                    )
                
                elif chunk.type == "agent_switched":
                    from_agent = chunk.metadata.get('from_agent', current_agent)
                    to_agent = chunk.metadata.get('to_agent', current_agent)
                    reason = chunk.metadata.get('reason', 'Unknown')
                    
                    logger.info(f"Agent switch: {from_agent} -> {to_agent}")
                    
                    # Record agent switch
                    await collector.record_agent_switch(
                        task_execution_id=task_execution_id,
                        from_agent=from_agent,
                        to_agent=to_agent,
                        reason=reason
                    )
                    
                    current_agent = to_agent
                    agent_switches.append({
                        'from': from_agent,
                        'to': to_agent,
                        'reason': reason
                    })
                
                elif chunk.type == "error":
                    has_error = True
                    logger.error(f"Task error: {chunk.content}")
                
                # Check if final
                if chunk.is_final:
                    logger.debug("Received final chunk")
                    break
            
            # Evaluate success based on response
            success = not has_error and len(response_text) > 0
            
            # Record quality evaluation
            await collector.record_quality_evaluation(
                task_execution_id=task_execution_id,
                evaluation_type="completion_check",
                score=1.0 if success else 0.0,
                passed=success,
                details={
                    "response_length": len(response_text),
                    "llm_calls": llm_call_count,
                    "tool_calls": tool_call_count,
                    "agent_switches": len(agent_switches)
                }
            )
            
            logger.info(
                f"Task {task['id']} completed: success={success}, "
                f"llm_calls={llm_call_count}, tool_calls={tool_call_count}, "
                f"agent_switches={len(agent_switches)}"
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing task {task['id']}: {e}", exc_info=True)
            return False
    
    async def run(self) -> None:
        """Run the POC experiment."""
        self.load_tasks()
        
        modes_to_run = []
        if self.mode == "both":
            modes_to_run = ["single-agent", "multi-agent"]
        else:
            modes_to_run = [self.mode]
        
        results = {}
        
        for mode in modes_to_run:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running experiment in {mode} mode")
            logger.info(f"{'='*60}\n")
            
            summary = await self.run_experiment(mode)
            results[mode] = summary
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Experiment {mode} completed")
            logger.info(f"{'='*60}")
            logger.info(f"Total tasks: {summary['total_tasks']}")
            logger.info(f"Successful: {summary['successful_tasks']}")
            logger.info(f"Failed: {summary['failed_tasks']}")
            logger.info(f"Success rate: {summary['success_rate']:.2%}")
            logger.info(f"Total input tokens: {summary['total_input_tokens']}")
            logger.info(f"Total output tokens: {summary['total_output_tokens']}")
            logger.info(f"Estimated cost: ${summary['estimated_cost_usd']:.4f}")
            logger.info(f"{'='*60}\n")
        
        # Print comparison if both modes were run
        if len(results) == 2:
            self.print_comparison(results)
    
    def print_comparison(self, results: Dict[str, Dict[str, Any]]) -> None:
        """
        Print comparison between single-agent and multi-agent results.
        
        Args:
            results: Dictionary with results for each mode
        """
        logger.info(f"\n{'='*60}")
        logger.info("COMPARISON: Single-Agent vs Multi-Agent")
        logger.info(f"{'='*60}\n")
        
        single = results.get("single-agent", {})
        multi = results.get("multi-agent", {})
        
        logger.info(f"{'Metric':<30} {'Single-Agent':<20} {'Multi-Agent':<20}")
        logger.info(f"{'-'*70}")
        
        logger.info(
            f"{'Success Rate':<30} "
            f"{single.get('success_rate', 0)*100:.1f}%{'':<18} "
            f"{multi.get('success_rate', 0)*100:.1f}%"
        )
        
        logger.info(
            f"{'Total Tokens':<30} "
            f"{single.get('total_input_tokens', 0) + single.get('total_output_tokens', 0):<20} "
            f"{multi.get('total_input_tokens', 0) + multi.get('total_output_tokens', 0):<20}"
        )
        
        logger.info(
            f"{'Estimated Cost (USD)':<30} "
            f"${single.get('estimated_cost_usd', 0):.4f}{'':<15} "
            f"${multi.get('estimated_cost_usd', 0):.4f}"
        )
        
        logger.info(f"{'='*60}\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run POC experiment with real agent runtime integration"
    )
    parser.add_argument(
        "--mode",
        choices=["single-agent", "multi-agent", "both"],
        default="both",
        help="Execution mode (default: both)"
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path(__file__).parent.parent / "poc_benchmark_tasks.yaml",
        help="Path to tasks YAML file (default: ../poc_benchmark_tasks.yaml)"
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL (default: from config)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of tasks to run (for testing)"
    )
    
    args = parser.parse_args()
    
    # Initialize database
    db_url = args.db_url or AppConfig.DB_URL
    logger.info(f"Initializing database: {db_url}")
    init_database(db_url)
    await init_db()
    logger.info("Database initialized")
    
    # Initialize session and agent context managers
    from app.services.session_manager_async import init_session_manager
    from app.services.agent_context_async import init_agent_context_manager
    
    await init_session_manager()
    await init_agent_context_manager()
    logger.info("Session and agent context managers initialized")
    
    # Run experiment
    runner = IntegratedPOCRunner(tasks_file=args.tasks, mode=args.mode)
    
    # Limit tasks if specified
    if args.limit:
        runner.load_tasks()
        runner.tasks = runner.tasks[:args.limit]
        logger.info(f"Limited to {args.limit} tasks")
    
    try:
        await runner.run()
        logger.info("POC experiment completed successfully")
    except Exception as e:
        logger.error(f"POC experiment failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Close database connections
        from app.services.database import close_db
        await close_db()
        logger.info("Database connections closed")


if __name__ == "__main__":
    asyncio.run(main())
