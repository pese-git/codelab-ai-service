#!/usr/bin/env python3
"""
POC Experiment Runner - автоматический запуск benchmark задач.

Этот скрипт запускает все задачи из benchmark файла и собирает метрики
для сравнения single-agent и multi-agent режимов.

Usage:
    python scripts/run_poc_experiment.py --mode single-agent --tasks poc_benchmark_tasks.yaml
    python scripts/run_poc_experiment.py --mode multi-agent --tasks poc_benchmark_tasks.yaml
    python scripts/run_poc_experiment.py --mode both --tasks poc_benchmark_tasks.yaml
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

import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import AppConfig
from app.services.database import init_database, get_db, init_db
from app.services.metrics_collector import MetricsCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("poc_runner")


class POCExperimentRunner:
    """
    Автоматический runner для POC экспериментов.
    
    Загружает задачи из YAML файла и выполняет их в указанном режиме,
    собирая метрики через MetricsCollector.
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
        self.experiment_id: Optional[UUID] = None
        
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
        
        # Get database session
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
                    success = await self.run_task(collector, experiment_id, task, mode)
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
    
    async def run_task(
        self,
        collector: MetricsCollector,
        experiment_id: UUID,
        task: Dict[str, Any],
        mode: str
    ) -> bool:
        """
        Run a single task and collect metrics.
        
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
        
        try:
            # Simulate task execution
            # В реальной реализации здесь будет вызов agent runtime API
            success = await self.simulate_task_execution(
                collector, task_execution_id, task, mode
            )
            
            if not success:
                failure_reason = "Task execution failed (simulated)"
        
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
        
        return success
    
    async def simulate_task_execution(
        self,
        collector: MetricsCollector,
        task_execution_id: UUID,
        task: Dict[str, Any],
        mode: str
    ) -> bool:
        """
        Simulate task execution with metrics collection.
        
        В реальной реализации это будет заменено на вызов agent runtime API.
        
        Args:
            collector: MetricsCollector instance
            task_execution_id: Task execution UUID
            task: Task definition
            mode: Execution mode
            
        Returns:
            True if task succeeded (simulated)
        """
        # Simulate LLM calls
        num_llm_calls = 2 if task['category'] == 'simple' else 5
        
        for i in range(num_llm_calls):
            agent_type = "single-agent" if mode == "single-agent" else "orchestrator"
            
            if mode == "multi-agent" and i > 0:
                # Simulate agent switch
                expected_agent = task.get('expected_agent', 'coder').lower()
                await collector.record_agent_switch(
                    task_execution_id=task_execution_id,
                    from_agent="orchestrator" if i == 1 else expected_agent,
                    to_agent=expected_agent if i == 1 else "orchestrator",
                    reason="Task routing" if i == 1 else "Task completion"
                )
                agent_type = expected_agent if i == 1 else "orchestrator"
            
            # Simulate LLM call
            await collector.record_llm_call(
                task_execution_id=task_execution_id,
                agent_type=agent_type,
                input_tokens=500 + i * 100,
                output_tokens=200 + i * 50,
                model=AppConfig.LLM_MODEL,
                duration_seconds=1.5 + i * 0.5
            )
            
            # Simulate tool calls
            if i > 0:
                await collector.record_tool_call(
                    task_execution_id=task_execution_id,
                    tool_name="read_file" if i % 2 == 0 else "write_file",
                    success=True,
                    duration_seconds=0.1 + i * 0.05
                )
        
        # Simulate quality evaluation
        await collector.record_quality_evaluation(
            task_execution_id=task_execution_id,
            evaluation_type="syntax_check",
            score=0.95,
            passed=True,
            details={"checks_passed": 10, "checks_failed": 0}
        )
        
        # Simulate success (90% success rate for simple tasks, 70% for others)
        import random
        success_rate = 0.9 if task['category'] == 'simple' else 0.7
        success = random.random() < success_rate
        
        # Simulate hallucination detection (10% chance)
        if random.random() < 0.1:
            await collector.record_hallucination(
                task_execution_id=task_execution_id,
                hallucination_type="import",
                description="Non-existent import detected: import 'package:fake/fake.dart'"
            )
        
        return success
    
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
            f"{single.get('success_rate', 0):.2%:<20} "
            f"{multi.get('success_rate', 0):.2%:<20}"
        )
        
        logger.info(
            f"{'Total Tokens':<30} "
            f"{single.get('total_input_tokens', 0) + single.get('total_output_tokens', 0):<20} "
            f"{multi.get('total_input_tokens', 0) + multi.get('total_output_tokens', 0):<20}"
        )
        
        logger.info(
            f"{'Estimated Cost (USD)':<30} "
            f"${single.get('estimated_cost_usd', 0):.4f:<19} "
            f"${multi.get('estimated_cost_usd', 0):.4f:<19}"
        )
        
        logger.info(f"{'='*60}\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run POC experiment for single-agent vs multi-agent comparison"
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
        default=Path("poc_benchmark_tasks.yaml"),
        help="Path to tasks YAML file (default: poc_benchmark_tasks.yaml)"
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL (default: from config)"
    )
    
    args = parser.parse_args()
    
    # Initialize database
    db_url = args.db_url or AppConfig.DB_URL
    logger.info(f"Initializing database: {db_url}")
    init_database(db_url)
    await init_db()
    logger.info("Database initialized")
    
    # Run experiment
    runner = POCExperimentRunner(tasks_file=args.tasks, mode=args.mode)
    
    try:
        await runner.run()
        logger.info("POC experiment completed successfully")
    except Exception as e:
        logger.error(f"POC experiment failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
